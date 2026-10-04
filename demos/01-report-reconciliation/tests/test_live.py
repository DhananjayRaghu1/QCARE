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
