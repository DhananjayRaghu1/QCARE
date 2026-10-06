import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from catalog import digest
from claude_session import Session, run_session, session_command
import context_mcp
import engineering_workflow as workflow
from live_server import LiveServer
import portfolio
import sandbox
from workflow_runner import WorkflowRun

# Stubs stand in for Claude. They exercise the graph, gate and records, not model quality.
REFERENCE = (portfolio.BASE / "export/reference.py").read_text()
PASSING = """import unittest
from app.exporter import export_csv


class Settlement(unittest.TestCase):
    def test_refund_keeps_fee(self):
        row = dict(invoice_id="N-1", customer="NORTHSTAR", invoice_at="2026-09-01T00:00:00+00:00",
                   settled_at="2026-09-15T12:00:00+00:00", status="REFUNDED", gross_cents=5000, fee_cents=150, currency="USD")
        self.assertIn("N-1,2026-09-15,-5000", export_csv([row], "NORTHSTAR", "2026-09"))
"""
FAILING = PASSING.replace("-5000", "-4850")
ROLES = {"delta": "You are the requirements analyst for Jira DH-401, re-checking", "analyze": "You are the requirements analyst",
         "implement": "You are the engineer implementing", "review": "You are an independent reviewer"}
NO_PR = {"requested": False, "source_id": "", "quote": ""}


def requirement(key, text, source, quote, authority="approved"):
    return {"id": key, "text": text, "source_id": source, "quote": quote, "authority": authority, "acceptance": "an input gives the expected row"}


def analysis(blocking=False):
    return {"plain_summary": "Northstar needs settlements by New York date; refunds keep the fee.",
        "requirements": [
            requirement("R1", "Use the New York settlement month", "EXPORT-NS-1", "Select the reporting month by settled_at converted to America/New_York"),
            requirement("R2", "Refunds do not return fees", "FIN-SETTLEMENT-2", "For REFUNDED rows, net_cents = -gross_cents"),
            requirement("R3", "Tests stay in the standard library", "", "", "inferred")],
        "conflicts": [{"id": "C1", "summary": "A draft proposes UTC", "status": "blocking" if blocking else "resolved",
                       "sides": [{"source_id": "EXPORT-NS-2-DRAFT", "says": "UTC"}, {"source_id": "EXPORT-NS-1", "says": "New York"}],
                       "resolution": "The draft is not approved.", "owner": "Reporting Product"}],
        "current_behavior": ["Exports invoices by invoice_at."],
        "questions": [{"id": "Q1", "question": "UTC or New York?", "why": "The note contradicts the agreement.", "owner": "Reporting Product",
                       "recommended_option": "approved", "conflict_ids": ["C1"], "options": [
                           {"id": "approved", "label": "Follow the approved agreement", "consequence": "New York month."},
                           {"id": "override", "label": "Use UTC anyway", "consequence": "Needs sign-off."}]}] if blocking else [],
        "out_of_scope": [], "ready_to_build": not blocking, "pull_request": dict(NO_PR)}


def delta(blocking=False, **extra):
    base = {"summary": "Added one test requirement.", "added": [requirement("R4", "Test a December refund", "developer-note", "December refund", "developer")],
            "changed": [], "removed": [], "conflicts": [], "questions": analysis(True)["questions"] if blocking else [],
            "ready_to_build": not blocking}
    if blocking:
        base["conflicts"] = [dict(analysis(True)["conflicts"][0])]
    return base | extra


def report():
    return {"summary": "Added the settlement export.", "assumptions": [], "not_done": [],
            "changes": [{"file": "app/exporter.py", "change": "Northstar settlement export", "requirement_ids": ["R1", "R2"]}]}


def review(findings=(), status="met", ids=("R1", "R2", "R3", "R4")):
    return {"verdict": "changes_required" if findings or status != "met" else "approve", "summary": "Checked.", "findings": list(findings),
            "requirements": [{"id": key, "status": status, "evidence": "ran test_refund_keeps_fee"} for key in ids],
            "verified_claims": [{"claim": "Tests pass", "verified": True, "how": "Ran them."}],
            "summary_for_business": "Built as agreed.", "summary_for_engineers": ["Settlement branch."], "risks": []}


MEDIUM = {"id": "F1", "severity": "medium", "category": "bug", "requirement_ids": ["R2"], "location": "app/exporter.py",
          "evidence": "fee_cents=True is accepted", "suggested_fix": "reject booleans"}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class FakeClaude:
    def __init__(self, analyses=None, deltas=None, builds=None, reviews=None, pushes=None, on_build=None):
        self.calls, self.commands = [], []
        self.pushes = list(pushes or [True])
        self.on_build = on_build
        self.review_remotes = []
        self.queues = {"analyze": list(analyses or [analysis()]), "delta": list(deltas or [delta()]),
                       "implement": list(builds or [(REFERENCE, PASSING, {})]), "review": list(reviews or [review()])}

    def take(self, role):
        queue = self.queues[role]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def command(self, tools, schema, model, budget, **options):
        self.commands.append({"tools": tools, "schema": schema["title"], **options})
        return ["stub"]

    def __call__(self, command, prompt, cwd, *, timeout, cancel, emit, record_dir):
        role = next(key for key, start in ROLES.items() if prompt.startswith(start))
        self.calls.append((role, prompt))
        session = Session(cost_usd=0.01, models=["stub"], elapsed_seconds=0.01)
        if role in ("analyze", "delta"):
            emit("lookup", tool_id="t1", system="confluence", text="Opened Confluence page EXPORT-NS-1", input={})
            session.fetched = {key: context_mcp.get_record(key)["sha256"] for key in ("EXPORT-NS-1", "FIN-SETTLEMENT-2")}
        elif role == "implement":
            exporter, tests, extra = self.take(role)
            Path(cwd, "app/exporter.py").write_text(exporter)
            Path(cwd, "tests/test_settlement_export.py").write_text(tests)
            for relative, content in extra.items():
                Path(cwd, relative).write_text(content)
            if (self.pushes.pop(0) if len(self.pushes) > 1 else self.pushes[0]):
                git(cwd, "add", "-A")
                git(cwd, "commit", "-q", "--allow-empty", "-m", "DH-401: stub change")
                git(cwd, "push", "-q", "origin", "HEAD")
            if self.on_build:
                self.on_build(cwd)
            session.output = report()
            return session
        elif role == "review":
            Path(cwd, "app/exporter.py").write_text("raise SystemExit('reviewer edits must be discarded')\n")
            self.review_remotes.append(git(cwd, "remote"))
        session.output = self.take(role)
        return session


def make_run(tmp_path, fake, note="", **options):
    options.setdefault("remote", sandbox.local_remote(tmp_path / "origin.git"))
    settings = workflow.Settings(record_dir=tmp_path / "record", session=fake, command=fake.command, **options)
    run = WorkflowRun(note, settings=settings, preflight=lambda: {"authenticated": True})
    run.directory = tmp_path / "record"
    return run


def wait(run, *statuses):
    deadline = time.monotonic() + 30
    while run.status not in statuses and time.monotonic() < deadline:
        time.sleep(0.02)
    assert run.status in statuses, (run.status, run.events[-4:])
    return run.snapshot()


def roles(fake):
    return [role for role, _ in fake.calls]


def test_graph_outline_matches_the_designed_loop():
    outline = workflow.graph_outline()
    edges = {(edge["source"], edge["target"]) for edge in outline["edges"]}
    assert [node["id"] for node in outline["nodes"]] == list(workflow.STEPS)
    assert {("analyze", "ask_developer"), ("ask_developer", "analyze"), ("ask_developer", "implement"), ("check_requirements", "implement"),
            ("developer_review", "analyze"), ("developer_review", "finalize")} <= edges
    assert "check_requirements" not in outline["limits"]
    assert outline["ticket"]["links"] == [{"type": "relates to", "id": "DH-411"}]
    assert len(outline["sources"]) == 23
    assert {"DH-501", "OPS-USAGE-1004"} <= outline["sources"].keys()


def test_happy_path_pauses_for_review_then_approves_without_applying(tmp_path):
    fake = FakeClaude()
    run = make_run(tmp_path, fake)
    run.start()
    snapshot = wait(run, "waiting_for_developer")
    payload = snapshot["pending"]["payload"]
    assert payload["kind"] == "review"
    summary = payload["summary"]
    assert summary["outcome"] == "accepted" and summary["tests"]["passed"] and summary["context"] is True
    assert summary["citations"] == {"verified": 2, "checkable": 2, "inferred": 1}
    assert [row["citation"] for row in summary["trace"]] == ["verified", "verified", "inferred"]
    assert [row["status"] for row in summary["trace"]] == ["met", "met", "met"]
    assert summary["business"] == "Built as agreed."
    assert "app/exporter.py" in summary["files"] and "raise SystemExit" not in summary["diff"]
    grading = next(event for event in run.events if event["kind"] == "grading")
    assert grading["passed"] and grading["hidden_passed"] == grading["hidden_total"] == 12
    # The requirements check is code: three model sessions, not four.
    assert roles(fake) == ["analyze", "implement", "review"]
    check = next(event for event in run.events if event["kind"] == "step_finished" and event["node"] == "check_requirements")
    assert check["output"]["decision"] == "accept" and "metric" not in check
    assert not any("export_checks" in prompt or "hidden acceptance" in prompt for _, prompt in fake.calls)
    run.respond(snapshot["pending"]["id"], {"action": "approve"})
    wait(run, "completed")
    assert run.result["outcome"] == "approved" and run.result["applied"] is False
    assert (tmp_path / "record/final.patch").read_text() == summary["diff"]
    assert not Path(run.graph.get_state(run.config).values["workspace"]).exists()
    assert (portfolio.BASE / "export/app/exporter.py").read_text() != REFERENCE
    origin = tmp_path / "origin.git"
    branch = summary["git"]["branch"]
    assert branch == "dh-401/workflow-record" and summary["git"]["commits"][0]["subject"] == "DH-401: stub change"
    assert git(origin, "rev-parse", branch) == run.result["git"]["head"]
    assert git(origin, "rev-parse", "main") == summary["git"]["base"]
    assert fake.review_remotes == [""]
    assert any(event["kind"] == "handoff" and event["git"]["branch"] == branch for event in run.events)
    saved = json.loads((tmp_path / "record/events.json").read_text())
    assert saved[-1]["kind"] == "finished" and "thinking" not in json.dumps(saved)


def test_recommended_decision_is_applied_without_another_model_call(tmp_path):
    fake = FakeClaude(analyses=[analysis(blocking=True)])
    run = make_run(tmp_path, fake, note="Use UTC to keep it simple")
    run.start()
    snapshot = wait(run, "waiting_for_developer")
    payload = snapshot["pending"]["payload"]
    assert payload["kind"] == "questions" and payload["sources"]["EXPORT-NS-2-DRAFT"]["status"] == "draft"
    assert [option["id"] for option in payload["questions"][0]["options"]] == ["approved", "override", workflow.UNKNOWN]
    with pytest.raises(ValueError):
        run.respond(snapshot["pending"]["id"], {"action": "approve"})
    run.respond(snapshot["pending"]["id"], {"action": "answer", "choices": {"Q1": "approved"}})
    wait(run, "waiting_for_developer")
    assert roles(fake) == ["analyze", "implement", "review"]
    summary = run.pending["payload"]["summary"]
    assert summary["decisions"] == ["UTC or New York? → Follow the approved agreement"]
    assert summary["conflicts"][0]["status"] == "resolved" and "developer's decision" in summary["conflicts"][0]["resolution"]
    assert "UTC or New York? → Follow the approved agreement" in fake.calls[1][1]


def test_i_dont_know_is_recorded_as_an_assumption(tmp_path):
    fake = FakeClaude(analyses=[analysis(blocking=True)])
    run = make_run(tmp_path, fake)
    run.start()
    snapshot = wait(run, "waiting_for_developer")
    run.respond(snapshot["pending"]["id"], {"action": "answer", "choices": {"Q1": workflow.UNKNOWN}})
    wait(run, "waiting_for_developer")
    assert roles(fake) == ["analyze", "implement", "review"]
    assert "best judgment" in run.pending["payload"]["summary"]["decisions"][0]


def test_an_override_or_note_gets_a_short_delta_recheck(tmp_path):
    override = requirement("R1", "Use UTC", "developer-note", "Use UTC anyway", "developer")
    fake = FakeClaude(analyses=[analysis(blocking=True)], deltas=[delta(changed=[override], added=[])],
                      reviews=[review(ids=("R1", "R2", "R3"))])
    run = make_run(tmp_path, fake, note="Use UTC to keep it simple")
    run.start()
    snapshot = wait(run, "waiting_for_developer")
    run.respond(snapshot["pending"]["id"], {"action": "answer", "choices": {"Q1": "override"}})
    wait(run, "waiting_for_developer")
    assert roles(fake) == ["analyze", "delta", "implement", "review"]
    assert "UTC or New York? → Use UTC anyway" in fake.calls[1][1]
    assert fake.commands[1]["schema"] == "RequirementsDelta"
    trace = run.pending["payload"]["summary"]["trace"]
    assert trace[0]["text"] == "Use UTC" and trace[0]["authority"] == "developer"


def test_answers_are_capped_before_building(tmp_path):
    fake = FakeClaude(analyses=[analysis(blocking=True)], deltas=[delta(blocking=True)], reviews=[review(ids=("R1", "R2", "R3", "R4"))])
    run = make_run(tmp_path, fake)
    run.start()
    for _ in range(2):
        snapshot = wait(run, "waiting_for_developer")
        assert snapshot["pending"]["payload"]["kind"] == "questions"
        run.respond(snapshot["pending"]["id"], {"action": "answer", "choices": {"Q1": "override"}})
        time.sleep(0.2)
    wait(run, "waiting_for_developer")
    assert run.pending["payload"]["kind"] == "review"
    assert any(event["kind"] == "route" and "recorded as assumptions" in event["reason"] for event in run.events)


def test_failing_tests_send_the_change_back_and_explain_the_next_round(tmp_path):
    fake = FakeClaude(builds=[(REFERENCE, FAILING, {}), (REFERENCE, PASSING, {})])
    run = make_run(tmp_path, fake)
    run.start()
    wait(run, "waiting_for_developer")
    route = next(event for event in run.events if event["kind"] == "route" and event["node"] == "check_requirements")
    assert route["to"] == "implement" and "1 test failing" in route["reason"]
    prompts = [prompt for role, prompt in fake.calls if role == "implement"]
    assert len(prompts) == 2 and "Why you are working on this again (round 2)" in prompts[1] and "test_refund_keeps_fee" in prompts[1]
    assert [item["decision"] for item in run.pending["payload"]["summary"]["rounds"]] == ["revise", "accept"]


@pytest.mark.parametrize("first_review, reason", [(review(findings=[MEDIUM]), "high or medium review finding"),
                                                  (review(status="unclear"), "requirements not confirmed as met")])
def test_the_gate_is_stricter_than_a_model_accept(tmp_path, first_review, reason):
    fake = FakeClaude(reviews=[first_review, review()])
    run = make_run(tmp_path, fake)
    run.start()
    wait(run, "waiting_for_developer")
    rounds = run.pending["payload"]["summary"]["rounds"]
    assert rounds[0]["decision"] == "revise" and any(reason in item for item in rounds[0]["guard"])
    assert rounds[1]["decision"] == "accept"


def test_round_cap_hands_over_to_the_developer(tmp_path):
    fake = FakeClaude(reviews=[review(status="unmet")])
    run = make_run(tmp_path, fake, max_rounds=2)
    run.start()
    wait(run, "waiting_for_developer")
    assert run.pending["payload"]["outcome"] == "needs_help"
    assert roles(fake).count("implement") == 2


def test_developer_instruction_is_rechecked_then_built(tmp_path):
    fake = FakeClaude()
    run = make_run(tmp_path, fake)
    run.start()
    snapshot = wait(run, "waiting_for_developer")
    with pytest.raises(ValueError):
        run.respond(snapshot["pending"]["id"], {"action": "revise", "message": "  "})
    run.respond(snapshot["pending"]["id"], {"action": "revise", "message": "Also test a December refund."})
    wait(run, "waiting_for_developer")
    assert roles(fake)[3:] == ["delta", "implement", "review"]
    assert "Also test a December refund." in fake.calls[3][1]
    assert "Developer instruction after reviewing your previous result" in fake.calls[4][1]
    assert [row["id"] for row in run.pending["payload"]["summary"]["trace"]] == ["R1", "R2", "R3", "R4"]
    assert not any("hidden acceptance" in prompt for _, prompt in fake.calls)


def test_protected_inputs_are_restored_and_block_acceptance(tmp_path):
    fake = FakeClaude(builds=[(REFERENCE, PASSING, {"issue.json": "{}"}), (REFERENCE, PASSING, {})])
    run = make_run(tmp_path, fake)
    run.start()
    wait(run, "waiting_for_developer")
    assert any(event["kind"] == "note" and "restored them in the working copy: issue.json" in event["text"] for event in run.events)
    assert run.pending["payload"]["summary"]["rounds"][0]["guard"] == ["protected inputs were modified (restored in the working copy; commit the restore)"]


def test_context_off_is_the_same_workflow_without_business_records(tmp_path):
    fake = FakeClaude()
    run = make_run(tmp_path, fake, context=False)
    run.start()
    wait(run, "waiting_for_developer")
    assert all(command["context"] is False for command in fake.commands)
    analyze_prompt = fake.calls[0][1]
    assert "There is no access to Jira, Confluence" in analyze_prompt and "DH-411" not in analyze_prompt and '"links"' not in analyze_prompt
    assert "from the ticket and the code only" in fake.calls[1][1]
    assert not any("Followed the ticket" in event.get("text", "") for event in run.events)
    assert run.pending["payload"]["summary"]["context"] is False
    assert run.pending["payload"]["summary"]["git"]["branch"] == "dh-401/control-record"
    on = FakeClaude()
    run_on = make_run(tmp_path / "on", on)
    run_on.start()
    wait(run_on, "waiting_for_developer")
    assert all(command["context"] is True for command in on.commands) and "DH-411" in on.calls[0][1]


def test_pull_request_decision_is_locked_across_rechecks(tmp_path, monkeypatch):
    requested = analysis()
    requested["pull_request"] = {"requested": True, "source_id": "developer-note", "quote": "open a PR"}
    monkeypatch.setattr(sandbox, "find_pr", lambda repo, branch: {"number": 3, "url": "u", "isDraft": True, "state": "OPEN", "title": "t"})
    fake = FakeClaude(analyses=[requested])
    run = make_run(tmp_path, fake, note="Please open a PR", repo="me/sandbox")
    run.start()
    snapshot = wait(run, "waiting_for_developer")
    run.respond(snapshot["pending"]["id"], {"action": "revise", "message": "Also test a December refund."})
    wait(run, "waiting_for_developer")
    assert run.graph.get_state(run.config).values["pr_request"]["open"] is True
    assert run.pending["payload"]["summary"]["outcome"] == "accepted"


def test_find_pr_ignores_closed_pull_requests(monkeypatch):
    rows = [{"number": 1, "state": "CLOSED", "isDraft": True, "url": "a", "title": "t"}]
    monkeypatch.setattr(sandbox, "run", lambda *args, **kwargs: json.dumps(rows))
    assert sandbox.find_pr("me/sandbox", "b") is None
    rows.append({"number": 2, "state": "OPEN", "isDraft": True, "url": "b", "title": "t"})
    assert sandbox.find_pr("me/sandbox", "b")["number"] == 2


def test_stop_while_waiting_cleans_up(tmp_path):
    run = make_run(tmp_path, FakeClaude(analyses=[analysis(blocking=True)]))
    run.start()
    wait(run, "waiting_for_developer")
    workspace = run.graph.get_state(run.config).values["workspace"]
    run.stop()
    assert run.status == "cancelled" and not Path(workspace).exists()
    kinds = [event["kind"] for event in run.events]
    assert kinds[-1] == "finished" and kinds.index("waiting") < kinds.index("finished")
    with pytest.raises(ValueError):
        run.respond("anything", {"action": "answer"})


def test_citation_check_requires_an_opened_record_and_exact_words():
    ns1 = context_mcp.get_record("EXPORT-NS-1")
    state = {"developer_notes": [{"stage": "intake", "text": "Use UTC to keep it simple"}], "original_files": portfolio.inputs("DH-401", False)}
    quote = "Select the reporting month by settled_at converted to America/New_York"
    requirements = [
        {"id": "A", "source_id": "EXPORT-NS-1", "quote": quote, "authority": "approved"},
        {"id": "B", "source_id": "FIN-SETTLEMENT-2", "quote": "For REFUNDED rows, net_cents = -gross_cents", "authority": "approved"},
        {"id": "C", "source_id": "EXPORT-NS-1", "quote": "Refund the processing fee", "authority": "approved"},
        {"id": "D", "source_id": "developer-note", "quote": "use utc", "authority": "developer"},
        {"id": "E", "source_id": "app/exporter.py:7", "quote": 'writer.writerow(["invoice_id", "amount_cents"])', "authority": "approved"},
        {"id": "F", "source_id": "", "quote": "", "authority": "inferred"},
        {"id": "G", "source_id": "NOPE-1", "quote": "x", "authority": "approved"}]
    result = workflow.verify_citations({"requirements": requirements}, {"EXPORT-NS-1": ns1["sha256"]}, state)
    assert [item["status"] for item in result["results"]] == ["verified", "not_read", "not_found", "verified", "verified", "inferred", "unknown_source"]
    assert (result["verified"], result["checkable"], result["inferred"]) == (3, 6, 1)


def test_connector_serves_provenance_without_calculator_rules():
    corpus = context_mcp.records()
    assert len(corpus) == 23 and not any("rules" in record or "kind" in record for record in corpus.values())
    issue = context_mcp.get_record("DH-401", "jira")
    assert issue["document"]["links"][0]["id"] == "DH-411" and issue["sha256"] == digest(issue["document"])
    assert issue["document"]["body"] == json.loads((portfolio.BASE / "export/issue.json").read_text())["request"]
    assert "use jira_get_issue" in context_mcp.get_record("DH-411", "confluence")["note"]
    assert context_mcp.get_record("NOPE")["status"] == "not_found"
    found = context_mcp.search("confluence", "Northstar settlement refund fee")
    assert [item["source_id"] for item in found["results"][:3]] == ["EXPORT-NS-1", "FIN-SETTLEMENT-2", "EXPORT-NS-2-DRAFT"]
    assert all(corpus[item["source_id"]]["system"] == "confluence" for item in found["results"])
    assert context_mcp.describe_call("jira_search", {"query": "export"}) == 'Searched Jira for "export"'
    assert context_mcp.describe_result(found).startswith("5 candidates: EXPORT-NS-1 (approved)")


def test_raw_comparison_inputs_are_unchanged_by_the_workflow_fixture():
    assert sorted(portfolio.inputs("DH-401", False)) == ["README.md", "app/__init__.py", "app/exporter.py", "issue.json", "sample.json", "tests/test_existing.py"]
    assert "links" not in json.loads(portfolio.inputs("DH-401", True)["issue.json"])


def test_session_command_keeps_isolation_and_only_adds_the_context_server():
    command = session_command(["Read"], {"type": "object"}, "claude-opus-5-5", 1.0, system_prompt="role")
    assert "--restricted" in command and "--safe-mode" not in command
    servers = json.loads(command[command.index("--mcp-config") + 1])["mcpServers"]
    assert list(servers) == ["context"] and servers["context"]["args"][0].endswith("context_mcp.py")
    assert command[command.index("--allowedTools") + 1] == "Read," + ",".join(f"mcp__context__{name}" for name in context_mcp.TOOLS)
    assert command[command.index("--model") + 1] == "claude-opus-5-5"
    bare = session_command([], {"type": "object"}, None, 0.5, context=False)
    assert "--allowedTools" not in bare and json.loads(bare[bare.index("--mcp-config") + 1]) == {"mcpServers": {}}
    assert bare[bare.index("--tools") + 1] == ""


def test_session_streams_lookups_verifies_fetches_and_hides_thinking(tmp_path):
    good = context_mcp.get_record("EXPORT-NS-1", "confluence")
    forged = json.loads(json.dumps(context_mcp.get_record("FIN-SETTLEMENT-2", "confluence")))
    forged["document"]["body"] = "Refund the processing fee."
    lines = [{"type": "system", "subtype": "init", "model": "claude-opus-5-5"},
             {"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "private reasoning"},
                 {"type": "tool_use", "id": "a", "name": "mcp__context__confluence_get_page", "input": {"page_id": "EXPORT-NS-1"}},
                 {"type": "tool_use", "id": "b", "name": "mcp__context__confluence_get_page", "input": {"page_id": "FIN-SETTLEMENT-2"}}]}},
             {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "content": [{"type": "text", "text": json.dumps(good)}]},
                 {"type": "tool_result", "tool_use_id": "b", "content": [{"type": "text", "text": json.dumps(forged)}]}]}},
             {"type": "result", "result": "done", "structured_output": {"ok": True}, "total_cost_usd": 0.02}]
    script = "import sys; sys.stdin.read()\n" + "".join(f"print({json.dumps(json.dumps(line))}, flush=True)\n" for line in lines)
    events = []
    session = run_session([sys.executable, "-c", script], "prompt", tmp_path, timeout=10, cancel=threading.Event(),
                          emit=lambda kind, **data: events.append({"kind": kind, **data}), record_dir=tmp_path / "rec")
    assert session.errors == [] and session.output == {"ok": True} and session.models == ["claude-opus-5-5"]
    assert session.fetched == {"EXPORT-NS-1": good["sha256"]}
    assert [event["kind"] for event in events] == ["session", "lookup", "lookup", "lookup_result", "lookup_result"]
    assert events[3]["text"] == "EXPORT-NS-1 · Northstar settlement export agreement · approved · Reporting Product"
    assert "private reasoning" not in json.dumps(events)
    assert (tmp_path / "rec/trace.jsonl").exists() and json.loads((tmp_path / "rec/output.json").read_text())["cost_usd"] == 0.02


def request(server, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Demo-Token"] = token
    data = None if body is None else json.dumps(body).encode()
    with urlopen(Request(f"http://127.0.0.1:{server.server_port}{path}", data=data, headers=headers, method="POST" if data else "GET"), timeout=10) as response:
        return response.status, json.loads(response.read())


def test_server_runs_the_workflow_through_both_decisions(tmp_path):
    fake = FakeClaude(analyses=[analysis(blocking=True)])
    seen = []
    server = LiveServer(0, workflow_factory=lambda note, model, repo, context: seen.append(context) or make_run(tmp_path, fake, note, context=context))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        token = request(server, "/api/config")[1]["token"]
        assert request(server, "/api/workflows/graph")[1]["model"] == workflow.MODEL
        with pytest.raises(HTTPError) as error:
            request(server, "/api/workflows", {"case_id": "DH-401", "developer_note": "x" * 2001}, token)
        assert error.value.code == 400
        with pytest.raises(HTTPError) as error:
            request(server, "/api/workflows", {"case_id": "DH-401", "business_context": "no"}, token)
        assert error.value.code == 400
        status, started = request(server, "/api/workflows", {"case_id": "DH-401", "developer_note": "Use UTC", "business_context": False}, token)
        assert status == 202
        flow = server.workflows[started["id"]]
        wait(flow, "waiting_for_developer")
        with pytest.raises(HTTPError) as error:
            request(server, "/api/workflows", {"case_id": "DH-401"}, token)
        assert error.value.code == 409
        with pytest.raises(HTTPError) as error:
            request(server, f"/api/workflows/{flow.id}/respond", {"interrupt_id": "wrong", "action": "answer"}, token)
        assert error.value.code == 409
        pending = request(server, f"/api/workflows/{flow.id}?after=0")[1]["pending"]
        request(server, f"/api/workflows/{flow.id}/respond", {"interrupt_id": pending["id"], "action": "answer", "choices": {"Q1": "approved"}}, token)
        wait(flow, "waiting_for_developer")
        pending = flow.pending
        assert pending["payload"]["kind"] == "review"
        assert request(server, f"/api/workflows/{flow.id}/respond", {"interrupt_id": pending["id"], "action": "approve"}, token)[0] == 202
        wait(flow, "completed")
        snapshot = request(server, f"/api/workflows/{flow.id}?after=0")[1]
        assert snapshot["result"]["outcome"] == "approved" and snapshot["events"][-1]["kind"] == "finished"
        assert request(server, "/api/config")[1]["workflows"] == [{"id": flow.id, "status": "completed", "context": False}]
        assert seen == [False] and snapshot["context"] is False
    finally:
        server.shutdown()
        server.server_close()


def test_a_running_workflow_blocks_raw_runs(tmp_path):
    server = LiveServer(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        busy = type("Busy", (), {"id": "w", "status": "running"})()
        server.workflows["w"] = busy
        token = request(server, "/api/config")[1]["token"]
        with pytest.raises(HTTPError) as error:
            request(server, "/api/runs", {"case_id": "DH-401", "mode": "raw_repo"}, token)
        assert error.value.code == 409
        del server.workflows["w"]
    finally:
        server.shutdown()
        server.server_close()


def test_recordings_are_sanitized_and_replayable(tmp_path, monkeypatch):
    import demo
    import live_server
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    source = tmp_path / "artifacts/live/workflows" / ("a" * 32)
    source.mkdir(parents=True)
    workspace = "/private/var/folders/xy/T/datahoney-workflow-abc123"
    events = [{"index": 0, "kind": "tool_call", "name": "Read", "input": {"file_path": workspace + "/app/exporter.py"}},
              {"index": 1, "kind": "waiting", "payload": {"kind": "review", "summary": {"diff": "x"}}, "interrupt_id": "i"},
              {"index": 2, "kind": "note", "text": f"{tmp_path}/x and {Path.home()}/y"}]
    (source / "events.json").write_text(json.dumps(events))
    (source / "result.json").write_text(json.dumps({"status": "completed", "recorded_at": "2026-10-05T20:00:00+00:00",
                                                    "model": "claude-opus-5-5", "outcome": "approved"}))
    target = demo.record_workflow("a" * 32)
    assert target.name == "2026-10-05-opus-5-5.json"
    saved = json.loads(target.read_text())
    assert saved["events"][0]["input"]["file_path"] == "<workspace>/app/exporter.py"
    assert saved["events"][2]["text"] == "<demo>/x and ~/y"
    assert saved["events"][1]["payload"]["kind"] == "review" and saved["outcome"] == "approved"
    with pytest.raises(ValueError):
        demo.record_workflow("../" + "a" * 29)
    monkeypatch.setattr(live_server, "RECORDINGS", target.parent)
    server = LiveServer(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        listed = request(server, "/api/workflows/recordings")[1]["recordings"]
        assert [item["name"] for item in listed] == ["2026-10-05-opus-5-5"]
        assert request(server, "/api/workflows/recordings/2026-10-05-opus-5-5")[1]["events"][1]["kind"] == "waiting"
        with pytest.raises(HTTPError) as error:
            request(server, "/api/workflows/recordings/..%2Fsecrets")
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_committed_recordings_contain_both_decisions_and_no_local_paths():
    recordings = sorted((portfolio.ROOT / "recordings/langgraph-export").glob("*.json"))
    assert recordings
    for path in recordings:
        text = path.read_text()
        assert "datahoney-workflow-" not in text and str(Path.home()) not in text
        data = json.loads(text)
        kinds = [event.get("payload", {}).get("kind") for event in data["events"] if event["kind"] == "waiting"]
        assert kinds[-1] == "review" and data["headline"]["hidden_total"] == 12
        assert (data["status"], data["outcome"]) == ("completed", "approved") or data["status"] == "cancelled"


def test_an_unpushed_change_cannot_be_accepted(tmp_path):
    fake = FakeClaude(pushes=[False, True])
    run = make_run(tmp_path, fake)
    run.start()
    wait(run, "waiting_for_developer")
    rounds = run.pending["payload"]["summary"]["rounds"]
    assert rounds[0]["decision"] == "revise"
    assert any("not on the remote branch" in reason for reason in rounds[0]["guard"])
    assert rounds[1]["decision"] == "accept"


def test_requested_pull_request_is_opened_as_draft_and_marked_ready_on_approve(tmp_path, monkeypatch):
    requested = analysis()
    requested["pull_request"] = {"requested": True, "source_id": "developer-note", "quote": "Open a draft PR when it's ready"}
    opened, ready = [], []
    draft = {"number": 7, "url": "https://github.com/me/sandbox/pull/7", "isDraft": True, "state": "OPEN", "title": "DH-401"}
    monkeypatch.setattr(sandbox, "find_pr", lambda repo, branch: dict(draft) if opened else None)
    monkeypatch.setattr(sandbox, "mark_ready", lambda repo, number: ready.append(number) or {**draft, "isDraft": False})
    fake = FakeClaude(analyses=[requested], on_build=lambda cwd: opened.append(cwd))
    run = make_run(tmp_path, fake, note="Open a draft PR when it's ready", repo="me/sandbox")
    run.start()
    snapshot = wait(run, "waiting_for_developer")
    prompt = next(prompt for role, prompt in fake.calls if role == "implement")
    assert "gh pr create --draft --base main --head dh-401/workflow-record" in prompt
    assert snapshot["pending"]["payload"]["summary"]["git"]["pr"]["number"] == 7
    run.respond(snapshot["pending"]["id"], {"action": "approve"})
    wait(run, "completed")
    assert ready == [7] and run.result["git"]["pr"]["isDraft"] is False
    assert any("Marked PR #7 ready for review" in event.get("text", "") for event in run.events)


def test_a_requested_pull_request_that_was_not_opened_blocks_acceptance(tmp_path, monkeypatch):
    requested = analysis()
    requested["pull_request"] = {"requested": True, "source_id": "developer-note", "quote": "open a PR"}
    monkeypatch.setattr(sandbox, "find_pr", lambda repo, branch: None)
    run = make_run(tmp_path, FakeClaude(analyses=[requested]), note="Please open a PR", repo="me/sandbox", max_rounds=1)
    run.start()
    wait(run, "waiting_for_developer")
    assert run.pending["payload"]["outcome"] == "needs_help"
    assert "a pull request was requested but not opened" in run.pending["payload"]["summary"]["rounds"][0]["guard"]


def test_pull_requests_are_only_allowed_when_requested():
    pull = workflow.verify_citations({"requirements": [], "pull_request": {"requested": True, "source_id": "developer-note", "quote": "made up"}},
                                     {}, {"developer_notes": [{"stage": "intake", "text": "Use UTC"}]})["pull_request"]
    assert pull["status"] == "not_found" and pull["open"] is False


def test_refused_commands_are_shown_but_do_not_fail_the_step(tmp_path):
    lines = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "a", "name": "Bash", "input": {"command": "curl -s https://example.com"}}]}},
             {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "is_error": True,
                 "content": "Permission to use Bash has been denied because Claude Code is running in don't ask mode."}]}},
             {"type": "result", "result": "done", "structured_output": {"ok": True}, "permission_denials": [{"tool_name": "Bash"}]}]
    script = "import sys; sys.stdin.read()\n" + "".join(f"print({json.dumps(json.dumps(line))}, flush=True)\n" for line in lines)
    events = []
    session = run_session([sys.executable, "-c", script], "prompt", tmp_path, timeout=10, cancel=threading.Event(),
                          emit=lambda kind, **data: events.append({"kind": kind, **data}), record_dir=tmp_path / "rec")
    assert session.errors == [] and session.output == {"ok": True}
    assert session.denials == [{"tool": "Bash", "input": {"command": "curl -s https://example.com"}}]
    assert events[-1]["kind"] == "denied" and "curl -s https://example.com" in events[-1]["text"]


def test_engineer_shell_is_an_allow_list():
    command = session_command(["Read", "Bash"], {"type": "object"}, None, 1.0, allow=["Read", "Bash(git push:*)"])
    assert command[command.index("--tools") + 1] == "Read,Bash"
    assert command[command.index("--allowedTools") + 1].startswith("Read,Bash(git push:*),mcp__context__")
    assert "Bash(gh pr create:*)" in workflow.GH_PR and not any("gh repo" in item or "gh api" in item for item in workflow.GH_PR)


def test_single_session_runs_get_an_explicit_model(tmp_path):
    seen = []

    class Captured:
        def __init__(self, case_id, mode, prompt, model=None):
            seen.append(model)
            self.id, self.status, self.case_id, self.mode = "r1", "completed", case_id, mode
            self.cancel = threading.Event()

        def execute(self):
            pass
    server = LiveServer(0, run_factory=Captured, run_model="claude-opus-5-5")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        token = request(server, "/api/config")[1]["token"]
        assert request(server, "/api/runs", {"case_id": "DH-301", "mode": "raw_repo"}, token)[0] == 202
        assert seen == ["claude-opus-5-5"]
    finally:
        server.shutdown()
        server.server_close()


def test_a_requirement_only_its_owner_can_settle_is_escalated_not_looped(tmp_path):
    ambiguous = dict(MEDIUM, category="requirement", needs_owner_decision=True, evidence="R6 contradicts itself", suggested_fix="Ask Reporting Product")
    fake = FakeClaude(reviews=[review(findings=[ambiguous], status="unclear")])
    run = make_run(tmp_path, fake)
    run.start()
    wait(run, "waiting_for_developer")
    assert roles(fake).count("implement") == 1
    payload = run.pending["payload"]
    assert payload["outcome"] == "needs_decision"
    route = next(event for event in run.events if event["kind"] == "route" and event["node"] == "check_requirements")
    assert route["to"] == "prepare_summary" and "owner's decision" in route["reason"]
