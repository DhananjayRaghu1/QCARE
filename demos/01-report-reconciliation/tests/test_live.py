import json
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

import live_runner
from live_runner import RAW_PROMPT, Run, raw_command
from live_server import LiveServer
from codex_compare import inputs


def test_raw_conditions_differ_only_in_prose_evidence_and_never_include_answers():
    repo, docs = inputs(False, "DH-304"), inputs(True, "DH-304")
    assert all(docs[path] == text for path, text in repo.items())
    assert len(set(docs) - set(repo)) == 10
    assert json.loads(repo["issue.json"])["id"] == "DH-304"
    assert "title" not in json.loads(repo["issue.json"])
    assert not any("acceptance" in path or "reconcile" in path or "recordings" in path for path in docs)
    command = raw_command(None, 1)
    assert "--json-schema" not in command
    assert "--system-prompt" not in command
    assert command[command.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert "--restricted" in command and "--safe-mode" in command


def test_activity_exposes_tools_and_answer_but_not_thinking():
    run = Run("DH-301", "raw_repo")
    run.consume({"type": "assistant", "message": {"content": [
        {"type": "thinking", "thinking": "private reasoning"},
        {"type": "text", "text": "I will inspect the application."},
        {"type": "tool_use", "id": "a", "name": "Read", "input": {"file_path": "app/report.py"}},
    ]}})
    assert [event["kind"] for event in run.events] == ["message", "tool_call"]
    assert "private reasoning" not in json.dumps(run.events)


def test_real_subprocess_streams_events_before_finishing_and_retains_record(monkeypatch, tmp_path):
    # Stub emits CLI protocol, not model evidence. The subprocess and stream are real.
    monkeypatch.setattr(live_runner, "ROOT", tmp_path)
    monkeypatch.setattr(live_runner.agent, "preflight", lambda: {"authenticated": True})
    event = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "Read", "input": {}}]}}
    final = {"type": "result", "result": "Needs clarification.", "total_cost_usd": 0}
    script = f"import time; print({json.dumps(event)!r}, flush=True); time.sleep(.8); print({json.dumps(final)!r}, flush=True)"
    monkeypatch.setattr(live_runner, "raw_command", lambda *args: [sys.executable, "-c", script])
    run = Run("DH-301", "raw_repo")
    thread = threading.Thread(target=run.execute)
    thread.start()
    deadline = time.monotonic() + 3
    while not any(e["kind"] == "tool_call" for e in run.snapshot()["events"]) and time.monotonic() < deadline:
        time.sleep(.01)
    assert run.snapshot()["status"] == "running"
    assert any(e["kind"] == "tool_call" for e in run.snapshot()["events"])
    thread.join(5)
    assert run.result["status"] == "completed"
    assert run.result["answer"] == "Needs clarification."
    assert "acceptance" not in run.result
    assert (tmp_path / "artifacts/live" / run.id / "result.json").exists()
    import live_server
    monkeypatch.setattr(live_server, "ROOT", tmp_path)
    restored = LiveServer(0, restore=True)
    try:
        saved = restored.runs[run.id].snapshot()
        assert saved["result"] == run.result
        assert saved["events"] == run.events
        assert saved["status"] == "completed"
    finally:
        restored.server_close()


@pytest.mark.parametrize("cancel", [False, True])
def test_timeout_and_cancel_stop_a_real_subprocess(monkeypatch, tmp_path, cancel):
    monkeypatch.setattr(live_runner, "ROOT", tmp_path)
    monkeypatch.setattr(live_runner.agent, "preflight", lambda: {"authenticated": True})
    monkeypatch.setattr(live_runner, "raw_command", lambda *args: [sys.executable, "-c", "import time; time.sleep(20)"])
    run = Run("DH-301", "raw_repo", timeout=.1 if not cancel else 20)
    if cancel:
        threading.Timer(.15, run.cancel.set).start()
    run.execute()
    assert run.result["status"] == ("cancelled" if cancel else "failed")
    assert run.result["elapsed_seconds"] < 5
    assert run.result["errors"]


def test_auth_failure_does_not_launch_model(monkeypatch, tmp_path):
    monkeypatch.setattr(live_runner, "ROOT", tmp_path)
    monkeypatch.setattr(live_runner.agent, "preflight", lambda: {"authenticated": False})
    run = Run("DH-301", "raw_repo")
    run.execute()
    assert run.status == "blocked"
    assert not run.result["agent_run"]


def test_valid_answer_survives_slow_exit_after_stdout_closes(monkeypatch, tmp_path):
    monkeypatch.setattr(live_runner, "ROOT", tmp_path)
    monkeypatch.setattr(live_runner.agent, "preflight", lambda: {"authenticated": True})
    final = json.dumps({"type": "result", "result": "Preserve this completed answer."})
    script = f"import os,time; print({final!r},flush=True); os.close(1); time.sleep(5.2)"
    monkeypatch.setattr(live_runner, "raw_command", lambda *args: [sys.executable, "-c", script])
    run = Run("DH-301", "raw_repo", timeout=10)
    run.execute()
    assert run.status == "completed", run.result
    assert run.result["answer"] == "Preserve this completed answer."


@pytest.mark.parametrize("events_file", [None, "[truncated"])
def test_truncated_trace_does_not_hide_saved_result(monkeypatch, tmp_path, events_file):
    import live_server
    monkeypatch.setattr(live_server, "ROOT", tmp_path)
    path = tmp_path / "artifacts/live/saved"
    path.mkdir(parents=True)
    result = {"id": "saved", "case_id": "DH-301", "mode": "raw_repo", "status": "completed",
              "elapsed_seconds": 2, "answer": "Saved answer"}
    (path / "result.json").write_text(json.dumps(result))
    (path / "trace.jsonl").write_text(json.dumps({"type": "system", "subtype": "init", "model": "stub"})+'\n{bad line\n'+json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Answer"}]}})+'\n{"truncated":')
    if events_file:
        (path / "events.json").write_text(events_file)
    server = LiveServer(0, restore=True)
    try:
        run = server.runs["saved"]
        assert run.result["answer"] == "Saved answer"
        assert run.status == "completed"
        assert [event["kind"] for event in run.events] == ["session", "message"]
        assert run.result["restore_warnings"]
    finally:
        server.server_close()


def test_http_origin_token_validation_concurrency_and_stop():
    class WaitingRun(Run):
        def execute(self):
            self.cancel.wait(5)

    server = LiveServer(0, run_factory=WaitingRun)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def request(path, body=None, headers=None):
        return urlopen(Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                               headers=headers or {}), timeout=3)

    try:
        config = json.load(request("/api/config"))
        headers = {"X-Demo-Token": config["token"]}
        body = {"case_id": "DH-301", "mode": "raw_repo", "prompt": RAW_PROMPT}
        for unsafe in ({}, {**headers, "Origin": "https://example.com"}, {**headers, "Host": "evil.test"}):
            with pytest.raises(HTTPError) as error:
                request("/api/runs", body, unsafe)
            assert error.value.code == 403
        for bad in ({**body, "case_id": []}, {**body, "mode": "bogus"}, {**body, "prompt": ""}):
            with pytest.raises(HTTPError) as error:
                request("/api/runs", bad, headers)
            assert error.value.code == 400
        started = json.load(request("/api/runs", body, headers))
        with pytest.raises(HTTPError) as error:
            request("/api/runs", body, headers)
        assert error.value.code == 409
        assert json.load(request("/api/runs/" + started["id"]))["status"] == "running"
        request("/api/runs/" + started["id"] + "/cancel", {}, headers)
        assert server.runs[started["id"]].cancel.is_set()
        with pytest.raises(HTTPError) as error:
            request("/artifacts/anything")
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_historical_title_hint_is_flagged_without_rewriting_saved_record(monkeypatch, tmp_path):
    import live_server
    monkeypatch.setattr(live_server, "ROOT", tmp_path)
    path = tmp_path / "artifacts/live/old-guided/result.json"
    path.parent.mkdir(parents=True)
    original = json.dumps({"id": "old-guided", "case_id": "DH-308", "mode": "workflow",
                           "status": "completed", "prompt": '{"title": "Negative magnitude is invalid source data"}'})
    path.write_text(original)
    server = LiveServer(0, restore=True)
    try:
        assert "disclosed the diagnosis" in server.runs["old-guided"].result["comparability_warning"]
        assert path.read_text() == original
    finally:
        server.server_close()


def test_source_links_and_worked_examples_serve_actual_fixtures_without_starting_runs():
    from html import unescape
    import re
    from catalog import documents, digest

    server = LiveServer(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/api/documents") as response:
            snapshots = json.load(response)["documents"]
        assert len(snapshots) == len(documents()) == 10
        for snapshot in snapshots:
            doc = snapshot["document"]
            assert doc == documents()[doc["id"]]
            assert snapshot["sha256"] == digest(doc)
            with urlopen(base + "/documents/" + doc["id"]) as response:
                text = unescape(re.sub("<[^>]+>", "", response.read().decode()))
            assert doc["body"] in text
            assert doc["owner"] in text
            assert snapshot["sha256"] in text
        for case_id, expected in (("DH-301", 125000), ("DH-304", None), ("DH-305", None), ("DH-308", None)):
            with urlopen(base + "/api/walkthroughs/" + case_id) as response:
                assert json.load(response)["report"]["expected_total_cents"] == expected
        for path in ("/documents/does-not-exist", "/documents/../../agent.py", "/api/walkthroughs/not-a-case"):
            with pytest.raises(HTTPError) as error:
                urlopen(base + path)
            assert error.value.code == 404
        assert not server.runs
    finally:
        server.shutdown()
        server.server_close()
