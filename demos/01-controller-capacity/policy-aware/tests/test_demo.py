"""Workflow gates use captured results and exact source state, not happy history."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

import demo
from evidence import materialize_packet, validate_packet


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "demo"
    workspaces = root / "workspaces"
    path = workspaces / "practice"
    (path / "app").mkdir(parents=True)
    (path / "tests").mkdir()
    (path / "app/validator.py").write_text("def validate(zones):\n    limit = 20\n    return len(zones) <= limit\n")
    (path / "app/devices.json").write_text('{"DEV-101": {"model": "PRO", "firmware": "3.4.0"}}\n')
    (path / "tests/test_existing.py").write_text("def test_initial():\n    assert True\n")
    monkeypatch.setattr(demo, "ROOT", root)
    monkeypatch.setattr(demo, "WORKSPACES", workspaces)
    monkeypatch.setattr(demo, "RUNS", root / "artifacts/runs")
    monkeypatch.setattr(demo, "REPLAYS", root / "replays")
    monkeypatch.setattr(demo, "knowledge_hashes", lambda: {})
    demo.write_json(path / "workspace.json", {"name": path.name, "state": "seed", "runs": {}, "initial_hashes": demo.hashes(demo.tree_snapshot(path)), "knowledge_hashes": {}})
    return path


def decision_packet(workspace, code_spans=None, established=True):
    evidence = {"ticket_id": "AG-1423", "sources": {}}
    code = (workspace / "app/validator.py").read_text()
    registry = (workspace / "app/devices.json").read_text()
    demo.capture(evidence, "app/validator.py", code, code_spans or [[1, 3]], "code")
    demo.capture(evidence, "app/devices.json", registry, [[1, 1]], "registry", {"devices": {"DEV-101": {"controller_id": "DEV-101", "model": "PRO", "firmware": "3.4.0"}}})
    policy = "# Approved policy\nEligible Pro firmware 3.2.0 or later permits 50 zones.\n"
    if established:
        demo.capture(evidence, "knowledge/capacity-policy.md", policy, [[1, 2]], "knowledge")
    packet = {
        "ticket_id": "AG-1423",
        "device": {"controller_id": "DEV-101", "model": "PRO", "firmware": "3.4.0", "citations": ["registry"]},
        "policy": {"status": "established" if established else "unknown", "text": "Eligible Pro permits 50 zones." if established else "Unknown: approved policy is unavailable.", "citations": ["policy"] if established else []},
        "diagnosis": {"classification": "investigate_mismatch" if established else "insufficient_evidence", "text": "Current code applies a global limit of 20 zones.", "citations": ["code"]},
        "starting_files": [{"path": "app/validator.py", "line_start": 1, "line_end": 3, "reason": "This implements the observed limit.", "citations": ["code"]}],
        "execution_path": {"text": "Validator compares zone count with the limit.", "citations": ["code"]},
        "history": [], "owner": {"text": "Unknown: owner not established.", "citations": []},
        "next_action": {"text": "Reproduce this observed response before changing code.", "citations": ["code"]},
        "unknowns": ["What support procedure is approved?"],
        "citations": [
            {"id": "code", "source": "app/validator.py", "line_start": 1, "line_end": 3},
            {"id": "registry", "source": "app/devices.json", "line_start": 1, "line_end": 1},
        ] + ([{"id": "policy", "source": "knowledge/capacity-policy.md", "line_start": 1, "line_end": 2}] if established else []),
    }
    return packet, evidence


def successful_trace(raw=None):
    result = {"is_error": False, "result": "Completed scoped task"}
    if raw is not None:
        result["structured_output"] = raw
    return {"result": result, "errors": [], "format_errors": [], "tools": [], "model": "actual-model"}


def execution(marker="first", timed_out=False):
    return {"lines": [marker], "exit_code": 0, "timed_out": timed_out, "elapsed_seconds": 1, "stderr": ""}


def client_mock(monkeypatch):
    monkeypatch.setattr(demo, "client_preflight", lambda: {"authenticated": True, "executable": "claude"})
    monkeypatch.setattr(demo, "client_command", lambda *args, **kwargs: ["not-executed"])


def ticket():
    text = "AG-1423: DEV-101 rejects 30 zones.\n"
    return {"status": "ok", "ticket_id": "AG-1423", "source": "knowledge/jira/AG-1423.md", "content": text, "numbered_content": "1: " + text, "metadata": {}}


def test_incomplete_repair_cannot_reuse_a_first_draft_that_becomes_valid(workspace, monkeypatch):
    client_mock(monkeypatch)
    monkeypatch.setattr(demo, "local_probe", lambda *args: {"ticket": ticket()})
    raw, captured = decision_packet(workspace, established=False)
    calls = []
    def execute(*args):
        calls.append(args)
        return execution("first" if len(calls) == 1 else "repair")
    monkeypatch.setattr(demo, "execute_client", execute)
    def trace(lines, path, evidence, phase, context):
        partial = deepcopy(captured)
        partial["sources"]["app/validator.py"]["spans"] = [[2, 2]] if lines == ["first"] else [[1, 3]]
        evidence["sources"].update(partial["sources"])
        value = successful_trace(raw) if lines == ["first"] else successful_trace()
        if lines != ["first"]:
            value["result"] = None
        return value
    monkeypatch.setattr(demo, "collect_trace", trace)
    bundle = demo.investigate(workspace, "AG-1423", context="repo", timeout=90)
    assert len(calls) == 2
    assert bundle["packet"] is None
    assert bundle["raw_packet"] is None
    assert bundle["metadata"]["status"] == "failed"
    assert validate_packet(bundle["metadata"]["first_pass_packet"], bundle["evidence"])["status"] == "valid"
    assert any("successful final result" in error for error in bundle["metadata"]["problems"])


def test_length_warning_does_not_make_a_second_model_request(workspace, monkeypatch):
    client_mock(monkeypatch)
    monkeypatch.setattr(demo, "local_probe", lambda *args: {"ticket": ticket()})
    raw, captured = decision_packet(workspace, established=False)
    raw["diagnosis"]["text"] = " ".join(["fact"] * 350)
    calls = []
    monkeypatch.setattr(demo, "execute_client", lambda *args: calls.append(args) or execution())
    def trace(lines, path, evidence, phase, context):
        evidence["sources"].update(captured["sources"])
        return successful_trace(raw)
    monkeypatch.setattr(demo, "collect_trace", trace)
    bundle = demo.investigate(workspace, "AG-1423", context="repo")
    assert bundle["metadata"]["status"] == "success"
    assert len(calls) == 1
    assert bundle["metadata"]["validation"]["word_count"] > 300


def test_capture_keeps_both_device_lookups_for_literal_fact_checks(workspace):
    records = {
        "DEV-101": {"model": "PRO", "firmware": "3.4.0"},
        "DEV-102": {"model": "PRO", "firmware": "3.1.0"},
    }
    (workspace / "app/devices.json").write_text(json.dumps(records) + "\n")
    packet, evidence = decision_packet(workspace)
    content = (workspace / "app/devices.json").read_text()
    for controller_id, record in records.items():
        normalized = {"controller_id": controller_id, **record}
        demo.capture(evidence, "app/devices.json", content, [[1, 1]], "registry", {"device": normalized, "devices": {controller_id: normalized}})
    metadata = evidence["sources"]["app/devices.json"]["metadata"]
    assert set(metadata["devices"]) == {"DEV-101", "DEV-102"}
    assert validate_packet(packet, evidence)["status"] == "valid"
    packet["device"].update(controller_id="DEV-102", firmware="3.1.0")
    assert validate_packet(packet, evidence)["status"] == "valid"


@pytest.mark.parametrize("failure", ["denial", "timeout"])
def test_failed_first_invocation_does_not_trigger_repair(workspace, monkeypatch, failure):
    client_mock(monkeypatch)
    monkeypatch.setattr(demo, "local_probe", lambda *args: {"ticket": ticket()})
    raw, captured = decision_packet(workspace, code_spans=[[2, 2]], established=False)
    calls = []
    monkeypatch.setattr(demo, "execute_client", lambda *args: calls.append(args) or execution(timed_out=failure == "timeout"))
    def trace(lines, path, evidence, phase, context):
        evidence["sources"].update(captured["sources"])
        value = successful_trace(raw)
        value["errors"] = ["Permission denial: Read"] if failure == "denial" else []
        return value
    monkeypatch.setattr(demo, "collect_trace", trace)
    bundle = demo.investigate(workspace, "AG-1423", context="repo")
    assert len(calls) == 1
    assert bundle["metadata"]["status"] != "success"
    assert bundle["packet"] is None


def red_result(detail="assert 400 == 201", *, error=False, skipped=False, observed=400):
    return {"exit_code": 1, "output": detail,
            "cases": [{"name": "test_reported_30_zones", "failed": not error and not skipped, "error": error, "skipped": skipped, "detail": detail}],
            "passed": 0, "failed": int(not error and not skipped), "errors": int(error), "skipped": int(skipped)}


def mock_reproduction(workspace, monkeypatch, tests, observation=None, mutate_app=False):
    packet, evidence = decision_packet(workspace)
    monkeypatch.setattr(demo, "handoff", lambda path: {"packet": materialize_packet(packet, evidence)})
    client_mock(monkeypatch)
    def execute(*args):
        (workspace / "tests/test_reported_case.py").write_text(
            "from app.api import create_schedule\n\ndef test_reported_30_zones():\n"
            "    response = create_schedule({'controller_id': 'DEV-101', 'zones': list(range(1, 31))})\n"
            "    assert response.status_code == 201\n")
        if mutate_app:
            (workspace / "app/validator.py").write_text("limit = 50\n")
        return execution()
    monkeypatch.setattr(demo, "execute_client", execute)
    monkeypatch.setattr(demo, "collect_trace", lambda *args: successful_trace())
    monkeypatch.setattr(demo, "run_pytest", lambda *args: deepcopy(tests))
    monkeypatch.setattr(demo, "capacity_probe", lambda *args: observation or {"status_code": 400, "body": {"code": "zone_limit_exceeded"}})


def test_reproduction_records_a_real_capacity_status_mismatch(workspace, monkeypatch):
    mock_reproduction(workspace, monkeypatch, red_result())
    bundle = demo.coding(workspace, "reproduce")
    assert bundle["metadata"]["status"] == "success"
    assert bundle["test_results"]["observed_response"]["status_code"] == 400
    assert bundle["metadata"]["source_hashes_before"]["app/validator.py"] == bundle["metadata"]["source_hashes_after"]["app/validator.py"]


@pytest.mark.parametrize("tests,observation", [
    (red_result("ModuleNotFoundError: app", error=True), None),
    (red_result("assert 1 == 2"), None),
    (red_result("assert 1 == 2\n# expected 201 actual 400"), None),
    (red_result(skipped=True), None),
    (red_result(), {"status_code": 400, "body": {"code": "unknown_controller"}}),
    (red_result(), {"status_code": 201, "body": {"id": 1}}),
])
def test_unrelated_errors_or_statuses_do_not_satisfy_red_gate(workspace, monkeypatch, tests, observation):
    mock_reproduction(workspace, monkeypatch, tests, observation)
    assert demo.coding(workspace, "reproduce")["metadata"]["status"] != "success"


def test_reproduction_cannot_change_application_even_with_expected_red_result(workspace, monkeypatch):
    mock_reproduction(workspace, monkeypatch, red_result(), mutate_app=True)
    bundle = demo.coding(workspace, "reproduce")
    assert bundle["metadata"]["status"] != "success"
    assert any("Protected" in error for error in bundle["metadata"]["problems"])


@pytest.mark.parametrize("red_status,changed", [("failed", False), ("success", True)])
def test_fix_requires_successful_red_result_for_exact_current_source(workspace, monkeypatch, red_status, changed):
    packet, evidence = decision_packet(workspace)
    monkeypatch.setattr(demo, "handoff", lambda path: {"packet": materialize_packet(packet, evidence)})
    (workspace / "tests/test_reported_case.py").write_text("def test_reported_30_zones():\n    assert False\n")
    snapshot = demo.hashes(demo.tree_snapshot(workspace))
    monkeypatch.setattr(demo, "latest", lambda *args: {"metadata": {"status": red_status, "source_hashes_after": snapshot}})
    if changed:
        (workspace / "tests/test_reported_case.py").write_text("def test_reported_30_zones():\n    assert True\n")
    calls = []
    monkeypatch.setattr(demo, "execute_client", lambda *args: calls.append(args) or execution())
    bundle = demo.coding(workspace, "fix")
    assert bundle["metadata"]["status"] == "failed"
    assert not calls
    assert any("captured failing regression" in problem for problem in bundle["metadata"]["problems"])


def record(workspace, phase, before, after, status="success", packet=None, evidence=None, ticket_id="AG-1423"):
    return demo.save_bundle(workspace, {
        "metadata": {"phase": phase, "status": status, "ticket_id": ticket_id, "agent_run": phase != "verify", "model": "actual-model" if phase != "verify" else None,
                     "claim_review": "pending", "problems": [] if status == "success" else ["Recorded failure"],
                     "source_hashes_before": demo.hashes(before), "source_hashes_after": demo.hashes(after)},
        "packet": packet, "evidence": evidence or {"sources": {}}, "tools": [],
        "source_snapshot_before": before, "source_snapshot_after": after,
        "test_results": red_result() if phase == "reproduce" else {},
    })


def complete_history(workspace):
    original = demo.tree_snapshot(workspace)
    packet, evidence = decision_packet(workspace)
    record(workspace, "investigate", original, original, packet=materialize_packet(packet, evidence), evidence=evidence)
    (workspace / "tests/test_reported_case.py").write_text(
        "from app.api import create_schedule\n\ndef test_reported_30_zones():\n"
        "    response = create_schedule({'controller_id': 'DEV-101', 'zones': list(range(1, 31))})\n"
        "    assert response.status_code == 201\n")
    red = demo.tree_snapshot(workspace)
    record(workspace, "reproduce", original, red)
    (workspace / "app/validator.py").write_text("def validate(zones):\n    limit = 50\n    return len(zones) <= limit\n")
    fixed = demo.tree_snapshot(workspace)
    record(workspace, "fix", red, fixed)
    record(workspace, "verify", fixed, fixed)
    return fixed


def passing_verification(monkeypatch):
    monkeypatch.setattr(demo, "run_pytest", lambda *args: {"exit_code": 0, "cases": [{"name": "actual_test"}], "skipped": 0, "output": "passed"})
    monkeypatch.setattr(demo.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=json.dumps({"status": "passed", "passed": 18, "failed": 0, "cases": []}), stderr=""))


def test_report_complete_when_latest_results_match_current_state(workspace):
    complete_history(workspace)
    assert demo.report(workspace)["readiness"]["workflow_complete"] is True


@pytest.mark.parametrize("phase", ["investigate", "reproduce", "fix", "verify"])
def test_report_latest_failure_supersedes_historic_success(workspace, phase):
    current = complete_history(workspace)
    record(workspace, phase, current, current, status="failed")
    assert demo.report(workspace)["readiness"]["workflow_complete"] is False


def test_report_ag1424_success_cannot_mask_latest_ag1423_failure(workspace):
    current = complete_history(workspace)
    record(workspace, "investigate", current, current, status="failed", ticket_id="AG-1423")
    record(workspace, "investigate", current, current, ticket_id="AG-1424")
    assert demo.report(workspace)["readiness"]["workflow_complete"] is False


def test_report_current_source_must_match_last_verified_state(workspace):
    complete_history(workspace)
    (workspace / "app/validator.py").write_text("limit = 999\n")
    assert demo.report(workspace)["readiness"]["workflow_complete"] is False


def test_report_out_of_order_old_verification_cannot_complete_a_new_fix(workspace):
    current = complete_history(workspace)
    record(workspace, "fix", current, current)
    assert demo.report(workspace)["readiness"]["workflow_complete"] is False


def test_later_investigation_cannot_replace_handoff_for_historic_patch(workspace):
    current = complete_history(workspace)
    packet, evidence = decision_packet(workspace)
    record(workspace, "investigate", current, current, packet=materialize_packet(packet, evidence), evidence=evidence)
    assert demo.report(workspace)["readiness"]["workflow_complete"] is False


def test_new_fix_with_same_old_hashes_still_needs_later_verification(workspace):
    current = complete_history(workspace)
    old_fix = demo.latest(workspace, "fix")
    record(workspace, "fix", old_fix["source_snapshot_before"], current)
    assert demo.report(workspace)["readiness"]["workflow_complete"] is False


def test_verify_detects_reported_regression_changed_after_fix(workspace, monkeypatch):
    complete_history(workspace)
    (workspace / "tests/test_reported_case.py").write_text("def test_reported_30_zones():\n    pass\n")
    passing_verification(monkeypatch)
    bundle = demo.verify(workspace)
    assert bundle["metadata"]["status"] == "failed"
    assert any("regression" in problem.lower() or "reported" in problem.lower() or "changed" in problem.lower() for problem in bundle["metadata"]["problems"])


@pytest.mark.parametrize("output", ["null", "[]", '{"unknown":"shape"}', "not JSON"])
def test_failed_checker_output_records_latest_failed_verify(workspace, monkeypatch, output):
    complete_history(workspace)
    passing_verification(monkeypatch)
    monkeypatch.setattr(demo.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=output, stderr=""))
    bundle = demo.verify(workspace)
    assert bundle["metadata"]["status"] == "failed"
    assert demo.latest(workspace, "verify")["metadata"]["run_id"] == bundle["metadata"]["run_id"]
    assert demo.report(workspace)["readiness"]["workflow_complete"] is False


def test_checker_timeout_is_saved_as_failed_verify(workspace, monkeypatch):
    complete_history(workspace)
    passing_verification(monkeypatch)
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 30)
    monkeypatch.setattr(demo.subprocess, "run", timeout)
    bundle = demo.verify(workspace)
    assert bundle["metadata"]["status"] == "failed"
    assert demo.latest(workspace, "verify")["metadata"]["run_id"] == bundle["metadata"]["run_id"]
    assert demo.report(workspace)["readiness"]["workflow_complete"] is False


def test_export_refuses_stale_or_failed_workflow(workspace):
    current = complete_history(workspace)
    record(workspace, "fix", current, current, status="failed")
    with pytest.raises(ValueError, match="complete"):
        demo.export(workspace, "meeting")
    assert not (demo.REPLAYS / "meeting").exists()


@pytest.mark.parametrize("mutation", [
    lambda run: run["evidence"]["sources"]["app/validator.py"].update(content="forged\n"),
    lambda run: run["evidence"]["sources"]["app/validator.py"].update(sha256="0" * 64),
    lambda run: run["packet"]["citations"][0].update(source="../secret.py"),
])
def test_public_export_rechecks_captured_evidence_and_paths(workspace, mutation):
    complete_history(workspace)
    session = demo.report(workspace)
    mutation(session["runs"][0])
    with pytest.raises(ValueError, match="verification"):
        demo.portable(session, workspace)


def test_public_export_has_no_machine_paths_or_raw_trace_fields(workspace):
    complete_history(workspace)
    session = demo.report(workspace)
    portable = demo.portable(session, workspace)
    serialized = json.dumps(portable)
    assert str(workspace) not in serialized
    assert str(demo.ROOT) not in serialized
    assert "trace.jsonl" not in serialized
    assert "client-stderr" not in serialized


def test_bundle_replay_does_not_depend_on_current_checkout(workspace):
    current = complete_history(workspace)
    session = demo.report(workspace)
    run = session["runs"][0]
    (workspace / "app/validator.py").write_text("unrelated future code\n")
    replay = demo.replay(run["metadata"]["run_id"])
    assert replay["packet"]["citations"][0]["excerpt"].startswith("def validate")
    assert validate_packet(replay["packet"], replay["evidence"])["status"] == "valid"


def baseline_ready(workspace, monkeypatch, mutate=None):
    client_mock(monkeypatch)
    monkeypatch.setattr(demo, "SOURCES", {"AG-1423": "ticket.md"})
    (demo.ROOT / "ticket.md").write_text("# AG-1423\n\n## Reported behavior\n\nDEV-101 rejects 30 zones.\n\n"
        "## Reproduction\n\nSubmit 30 zones.\n\n## Triage request\n\nUse the approved requirements.\n")
    isolated = []
    prompts = []
    def execute(command, prompt, cwd, timeout):
        prompts.append(prompt)
        isolated.append(cwd)
        assert not (cwd / "CLAUDE.md").exists() and not (cwd / "workspace.json").exists() and (cwd / ".git").is_dir()
        if mutate:
            mutate(cwd)
        return execution()
    monkeypatch.setattr(demo, "execute_client", execute)
    monkeypatch.setattr(demo, "collect_trace", lambda *args: successful_trace())
    monkeypatch.setattr(demo, "run_pytest", lambda *args: {"exit_code": 0, "cases": [{"name": "t"}], "passed": 1, "failed": 0, "errors": 0, "skipped": 0, "output": ""})
    monkeypatch.setattr(demo, "capacity_probe", lambda path, controller="DEV-101": {"status_code": 201, "body": {"controller_id": controller}})
    return prompts, isolated


def test_baseline_gets_only_the_ticket_and_records_its_patch(workspace, monkeypatch):
    prompts, isolated = baseline_ready(workspace, monkeypatch, lambda cwd: (cwd / "app/validator.py").write_text("limit = 50\n"))
    bundle = demo.baseline(workspace)
    assert bundle["metadata"]["status"] == "success", bundle["metadata"]["problems"]
    assert bundle["metadata"]["context"] == "repo"
    assert "DEV-101 rejects 30 zones" in prompts[0] and "Submit 30 zones" in prompts[0] and "approved" not in prompts[0]
    assert "+limit = 50" in bundle["patch"] and (workspace / "app/validator.py").read_text() == "limit = 50\n"
    assert set(bundle["probes"]) == {"DEV-101", "DEV-102"}
    assert not isolated[0].exists() and not workspace.resolve().is_relative_to(isolated[0])


def test_baseline_ticket_style_sends_the_full_ticket(workspace, monkeypatch):
    prompts, _ = baseline_ready(workspace, monkeypatch)
    demo.baseline(workspace, style="ticket")
    assert "Use the approved requirements." in prompts[0]


def test_baseline_recall_style_adds_the_engineers_incomplete_memory(workspace, monkeypatch):
    prompts, _ = baseline_ready(workspace, monkeypatch)
    demo.baseline(workspace, style="recall")
    assert "Pro controllers support up to 50 zones" in prompts[0] and "firmware" not in prompts[0]


def test_baseline_reports_registry_edits(workspace, monkeypatch):
    baseline_ready(workspace, monkeypatch, lambda cwd: (cwd / "app/devices.json").write_text("{}\n"))
    bundle = demo.baseline(workspace)
    assert bundle["metadata"]["status"] == "partial"
    assert "Agent changed the device registry; the original was restored" in bundle["metadata"]["problems"]
    assert (workspace / "app/devices.json").read_text() != "{}\n"


def test_baseline_requires_untouched_seed(workspace, monkeypatch):
    prompts, _ = baseline_ready(workspace, monkeypatch)
    (workspace / "app/validator.py").write_text("limit = 50\n")
    bundle = demo.baseline(workspace)
    assert bundle["metadata"]["status"] == "failed" and not prompts
