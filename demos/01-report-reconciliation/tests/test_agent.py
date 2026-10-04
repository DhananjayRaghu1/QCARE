import json
import sys

import pytest

import agent
import demo
from catalog import cases, documents, get_document
from evaluation import score


def event(role, *blocks):
    return json.dumps({"type": role, "message": {"content": list(blocks)}})


def use(name="get_document", tool_id="t1"):
    return {"type": "tool_use", "id": tool_id, "name": "mcp__reconciliation__" + name, "input": {}}


def tool_result(content, tool_id="t1", error=False):
    return {"type": "tool_result", "tool_use_id": tool_id, "is_error": error, "content": json.dumps(content)}


def test_claimed_or_searched_sources_are_not_observed_evidence():
    doc = get_document("FEED-ATLAS-1")
    # An assistant claiming a source is not a successful full-document retrieval.
    assert agent.parse_trace(event("assistant", {"type": "text", "text": json.dumps(doc)}), "retrieval")["sources"] == []
    search = "\n".join([event("assistant", use("search_knowledge")),
                          event("user", tool_result({"source_id": "FEED-ATLAS-1", "excerpt": "signed"}))])
    assert agent.parse_trace(search, "retrieval")["sources"] == []
    full = "\n".join([event("assistant", use()), event("user", tool_result(doc))])
    assert agent.parse_trace(full, "retrieval")["sources"] == ["FEED-ATLAS-1"]
    doc["document"]["body"] = "tampered"
    changed = "\n".join([event("assistant", use()), event("user", tool_result(doc))])
    assert agent.parse_trace(changed, "retrieval")["sources"] == []


def test_tool_errors_and_unexpected_tools_fail_instead_of_disappearing():
    failed = "\n".join([event("assistant", use()), event("user", tool_result(get_document("FEED-ATLAS-1"), error=True))])
    parsed = agent.parse_trace(failed, "retrieval")
    assert parsed["errors"] and not parsed["sources"]
    calc = "\n".join([event("assistant", use("reconcile_report")), event("user", tool_result(get_document("FEED-ATLAS-1")))])
    assert agent.parse_trace(calc, "retrieval")["errors"]
    assert agent.parse_trace(calc, "workflow")["sources"] == ["FEED-ATLAS-1"]


def test_all_conditions_have_same_case_and_available_document_universe():
    for condition in agent.CONDITIONS:
        text = agent.prompt("DH-301", condition)
        assert '"amount_cents": -20000' in text
        assert "acceptance/expected.json" not in text
    assert all(doc["body"] in agent.prompt("DH-301", "provided") for doc in documents().values())
    assert agent.parse_trace("", "provided")["sources"] == sorted(documents())


def test_client_tools_are_scoped_and_calculator_is_only_in_workflow():
    for condition in agent.CONDITIONS:
        command = agent.client_command(condition)
        assert command[command.index("--tools") + 1] == ""
        assert command[command.index("--setting-sources") + 1] == ""
        assert "--strict-mcp-config" in command
        config = json.loads(command[command.index("--mcp-config") + 1])["mcpServers"]
        if condition == "provided":
            assert config == {}
        else:
            assert ("--without-calculator" in config["reconciliation"]["args"]) == (condition == "retrieval")
            allowed = command[command.index("--allowedTools") + 1]
            assert ("reconcile_report" in allowed) == (condition == "workflow")
            assert "Bash" not in allowed


def test_blocked_authentication_never_starts_a_model(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("must not invoke a model")
    monkeypatch.setattr(agent.subprocess, "Popen", forbidden)
    result = agent.run_agent("DH-301", "workflow", client={"authenticated": False})
    assert result["status"] == "blocked"
    assert result["agent_run"] is False
    assert result["elapsed_seconds"] is None
    assert not result["acceptance"]["passed"]


def test_fixed_schedule_covers_all_conditions_without_cherry_picking():
    schedule = agent.plan(repeats=3)
    assert schedule == agent.plan(repeats=3)
    trials = schedule["trials"]
    assert len(trials) == 90
    for case_id in cases():
        selected = [trial for trial in trials if trial["case_id"] == case_id]
        assert {trial["condition"] for trial in selected} == set(agent.CONDITIONS)
        # Each condition is first once for each case across the three repeats.
        assert {selected[index]["condition"] for index in (0, 3, 6)} == set(agent.CONDITIONS)


def test_summary_includes_failed_attempt_time_and_does_not_estimate_productivity():
    runs = [{"condition": "workflow", "agent_run": True, "status": "completed", "models": ["model-a"],
             "acceptance": {"passed": True}, "elapsed_seconds": 10},
            {"condition": "workflow", "agent_run": True, "status": "failed", "models": ["model-b"],
             "acceptance": {"passed": False}, "elapsed_seconds": 90}]
    result = agent.summarize(runs)
    assert result["conditions"]["workflow"]["total_attempt_seconds"] == 100
    assert result["conditions"]["workflow"]["median_attempt_seconds"] == 50
    assert result["same_model_verified"] is False
    assert result["productivity_estimate"] is None


def test_blocked_benchmark_preserves_plan_without_inventing_trials(monkeypatch, tmp_path):
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    monkeypatch.setattr(agent, "preflight", lambda: {"authenticated": False})
    assert demo.benchmark("blocked-run") == 3
    result = json.loads((tmp_path / "artifacts/blocked-run/results.json").read_text())
    assert result["status"] == "blocked"
    assert result["runs"] == []
    assert result["model_requests_attempted"] == 0
    assert len(result["plan"]["trials"]) == 30
    with pytest.raises(FileExistsError):
        demo.benchmark("blocked-run")


def test_missing_total_is_not_a_valid_abstention():
    packet = {"case_id": "DH-304", "decision": "insufficient_evidence", "problem_rows": [],
              "sources": ["REPORT-STD-SEP", "FEED-ATLAS-3-DRAFT"]}
    assert score(packet, "DH-304")["checks"]["total"] is False


def test_actual_subprocess_timeout_is_preserved_as_failure(monkeypatch, tmp_path):
    # Real process execution, synthetic client stub, never a model request.
    monkeypatch.setattr(agent, "ROOT", tmp_path)
    monkeypatch.setattr(agent, "protocol_hash", lambda: "test-stub")
    monkeypatch.setattr(agent, "client_command", lambda *args: [sys.executable, "-c", "import time; time.sleep(30)"])
    result = agent.run_agent("DH-301", "workflow", timeout=0.05, client={"authenticated": True})
    assert result["status"] == "failed"
    assert any("timed out" in error for error in result["errors"])
    assert result["elapsed_seconds"] is not None
    assert not result["acceptance"]["passed"]
    assert len(list(tmp_path.glob("artifacts/agent-*/result.json"))) == 1


def test_failure_to_launch_client_preserves_a_failed_record(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "ROOT", tmp_path)
    monkeypatch.setattr(agent, "protocol_hash", lambda: "test-stub")
    monkeypatch.setattr(agent, "client_command", lambda *args: [str(tmp_path / "missing-client")])
    result = agent.run_agent("DH-301", "workflow", client={"authenticated": True})
    assert result["status"] == "failed"
    assert result["agent_run"] is False
    assert result["elapsed_seconds"] is None
    assert len(list(tmp_path.glob("artifacts/agent-*/result.json"))) == 1
