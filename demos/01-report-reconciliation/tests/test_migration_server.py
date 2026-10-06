"""Migration HTTP contract tests. Stub drivers never launch a model or GitHub action."""
import json
import threading
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

import live_server
import migration_workflow
from live_server import LiveServer


class StubFlow:
    def __init__(self, case_id, note, model, context):
        self.id = uuid.uuid4().hex
        self.case_id = case_id
        self.developer_note, self.model, self.context = note, model, context
        self.status = "running"
        self.worker = None
        self.stopped = False
        self.responses = []
        self.pending = {"id": "decision-" + self.id, "payload": {"kind": "decision"}}
        self.events = [{"index": 0, "kind": "status"}, {"index": 1, "kind": "waiting"}]

    def start(self):
        self.status = "waiting_for_developer"

    def snapshot(self, after=0):
        return {"id": self.id, "case_id": self.case_id, "status": self.status,
                "context": self.context, "pending": self.pending,
                "events": self.events[after:], "cursor": len(self.events)}

    def respond(self, interrupt_id, response):
        if self.status != "waiting_for_developer" or not self.pending or interrupt_id != self.pending["id"]:
            raise ValueError("This workflow is not waiting for that answer.")
        self.responses.append(response)
        self.pending, self.status = None, "completed"

    def stop(self):
        self.stopped, self.status = True, "cancelled"


class StubRaw:
    def __init__(self, case_id, mode, prompt, model=None):
        self.id, self.case_id, self.mode = uuid.uuid4().hex, case_id, mode
        self.status = "running"
        self.cancel, self.started = threading.Event(), threading.Event()

    def execute(self):
        self.started.set()
        self.cancel.wait(3)
        self.status = "cancelled"


@pytest.fixture
def api(tmp_path, monkeypatch):
    migration_calls, export_calls = [], []

    def migration_factory(note, *, model, context):
        flow = StubFlow("DH-501", note, model, context)
        migration_calls.append(flow)
        return flow

    def workflow_factory(note, *, model, repo, context):
        flow = StubFlow("DH-401", note, model, context)
        export_calls.append(flow)
        return flow

    monkeypatch.setattr(live_server, "MIGRATION_RECORDINGS", tmp_path / "migration")
    monkeypatch.setattr(live_server, "RECORDINGS", tmp_path / "export")
    server = LiveServer(0, migration_factory=migration_factory, workflow_factory=workflow_factory,
                        run_factory=StubRaw, workflow_model="stub-opus")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def request(path, body=None, headers=None, *, raw=False):
        sent_headers = {"Content-Type": "application/json", "X-Demo-Token": server.token}
        if headers is not None:
            sent_headers = headers
        data = None if body is None else json.dumps(body).encode()
        with urlopen(Request(base + path, data=data, headers=sent_headers), timeout=3) as response:
            content = response.read()
            return response.status, content.decode() if raw else json.loads(content)

    try:
        yield server, request, migration_calls, export_calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def assert_http_error(request, code, path, body=None, headers=None):
    with pytest.raises(HTTPError) as error:
        request(path, body, headers)
    assert error.value.code == code
    return json.loads(error.value.read())


@pytest.mark.parametrize("context", [False, True])
def test_migration_start_snapshot_decision_and_config(api, context):
    server, request, calls, exports = api
    status, started = request("/api/migrations", {"case_id": "DH-501", "developer_note": "Keep client promises", "business_context": context})
    assert status == 202
    flow = server.workflows[started["id"]]
    assert calls == [flow] and not exports
    assert (flow.developer_note, flow.model, flow.context) == ("Keep client promises", "stub-opus", context)
    snapshot = request(f"/api/migrations/{flow.id}?after=1")[1]
    assert snapshot["events"] == [flow.events[1]]
    assert snapshot["cursor"] == 2 and snapshot["context"] is context
    assert request("/api/config")[1]["workflows"] == [
        {"id": flow.id, "status": "waiting_for_developer", "context": context, "case_id": "DH-501"}]
    response = {"interrupt_id": snapshot["pending"]["id"], "action": "decide",
                "choice": "request_signoff", "message": "Ask the named owners first"}
    assert request(f"/api/migrations/{flow.id}/respond", response) == (202, {"status": "resumed"})
    assert flow.responses == [{"action": "decide", "choice": "request_signoff", "message": "Ask the named owners first"}]
    assert request(f"/api/migrations/{flow.id}")[1]["status"] == "completed"
    assert_http_error(request, 409, f"/api/migrations/{flow.id}/respond", response)
    assert len(flow.responses) == 1


@pytest.mark.parametrize("path", ["/api/migrations", "/api/migrations/missing/respond", "/api/migrations/missing/cancel"])
def test_migration_mutations_require_local_origin_and_token(api, path):
    server, request, calls, exports = api
    body = {"case_id": "DH-501"}
    for unsafe in ({}, {"X-Demo-Token": "wrong"},
                   {"X-Demo-Token": server.token, "Origin": "https://example.com"},
                   {"X-Demo-Token": server.token, "Host": "evil.test"}):
        assert_http_error(request, 403, path, body, unsafe)
    assert not calls and not exports and not server.workflows


@pytest.mark.parametrize("bad", [
    {"case_id": "DH-401"}, {"case_id": []}, {"case_id": "DH-501", "business_context": "false"},
    {"case_id": "DH-501", "business_context": 0}, {"case_id": "DH-501", "developer_note": []},
    {"case_id": "DH-501", "developer_note": "x" * 2001},
])
def test_invalid_migration_start_never_instantiates_driver(api, bad):
    server, request, calls, exports = api
    assert_http_error(request, 400, "/api/migrations", bad)
    assert not calls and not exports and not server.workflows


@pytest.mark.parametrize("changes", [
    {"interrupt_id": []}, {"action": "approve"}, {"choice": "remove_all"},
    {"choice": []}, {"message": []}, {"message": "x" * 2001},
])
def test_invalid_migration_response_does_not_resume(api, changes):
    server, request, calls, exports = api
    started = request("/api/migrations", {"case_id": "DH-501"})[1]
    flow = server.workflows[started["id"]]
    response = {"interrupt_id": flow.pending["id"], "action": "decide", "choice": "defer", **changes}
    assert_http_error(request, 400, f"/api/migrations/{flow.id}/respond", response)
    assert flow.status == "waiting_for_developer" and not flow.responses


@pytest.mark.parametrize("choice", ["defer", "scoped_canary", "request_signoff"])
def test_all_decision_choices_and_optional_message_are_forwarded(api, choice):
    server, request, calls, exports = api
    started = request("/api/migrations", {"case_id": "DH-501"})[1]
    flow = server.workflows[started["id"]]
    assert_http_error(request, 409, f"/api/migrations/{flow.id}/respond",
                      {"interrupt_id": "stale", "action": "decide", "choice": choice})
    assert not flow.responses
    assert request(f"/api/migrations/{flow.id}/respond",
                   {"interrupt_id": flow.pending["id"], "action": "decide", "choice": choice})[0] == 202
    assert flow.responses == [{"action": "decide", "choice": choice, "message": ""}]


def test_migration_cursor_validation_and_cancel(api):
    server, request, calls, exports = api
    started = request("/api/migrations", {"case_id": "DH-501"})[1]
    flow = server.workflows[started["id"]]
    for cursor in ("-1", "abc"):
        assert_http_error(request, 400, f"/api/migrations/{flow.id}?after={cursor}")
    assert request(f"/api/migrations/{flow.id}?after=100")[1]["events"] == []
    assert request(f"/api/migrations/{flow.id}/cancel", {}) == (200, {"status": "stop_requested"})
    assert flow.stopped and flow.status == "cancelled"
    assert request("/api/migrations", {"case_id": "DH-501"})[0] == 202


def test_migration_and_export_ids_are_isolated_in_each_api_namespace(api):
    server, request, calls, exports = api
    migration_id = request("/api/migrations", {"case_id": "DH-501"})[1]["id"]
    flow = server.workflows[migration_id]
    for path in (f"/api/workflows/{migration_id}", f"/api/runs/{migration_id}"):
        assert_http_error(request, 404, path)
    for action in ("respond", "cancel"):
        assert_http_error(request, 404, f"/api/workflows/{migration_id}/{action}", {})
    assert not flow.stopped and not flow.responses
    request(f"/api/migrations/{migration_id}/cancel", {})
    export_id = request("/api/workflows", {"case_id": "DH-401"})[1]["id"]
    for path in (f"/api/migrations/{export_id}", "/api/migrations/missing"):
        assert_http_error(request, 404, path)
    for action in ("respond", "cancel"):
        assert_http_error(request, 404, f"/api/migrations/{export_id}/{action}", {})
    config = request("/api/config")[1]["workflows"]
    assert config[-1] == {"id": export_id, "status": "waiting_for_developer", "context": True}
    assert config[0]["case_id"] == "DH-501" and not exports[0].stopped
    raw_id = request("/api/runs", {"case_id": "DH-301", "mode": "raw_repo"})[1]["id"]
    assert_http_error(request, 404, f"/api/migrations/{raw_id}")
    for action in ("respond", "cancel"):
        assert_http_error(request, 404, f"/api/migrations/{raw_id}/{action}", {})
    assert not server.runs[raw_id].cancel.is_set()


@pytest.mark.parametrize("active_kind", ["migration", "export", "raw"])
def test_running_model_session_is_exclusive_across_all_three_drivers(api, active_kind):
    server, request, calls, exports = api
    starts = [("/api/migrations", {"case_id": "DH-501"}),
              ("/api/workflows", {"case_id": "DH-401"}),
              ("/api/runs", {"case_id": "DH-301", "mode": "raw_repo"})]
    path, body = starts[{"migration": 0, "export": 1, "raw": 2}[active_kind]]
    active_id = request(path, body)[1]["id"]
    if active_kind == "raw":
        active = server.runs[active_id]
        assert active.started.wait(1)
    else:
        active = server.workflows[active_id]
        active.status = "running"
    for path, body in starts:
        assert assert_http_error(request, 409, path, body)["id"] == active_id
    assert len(server.runs) + len(server.workflows) == 1


@pytest.mark.parametrize("waiting_kind", ["migration", "export"])
def test_waiting_developer_decision_prevents_another_guided_workflow(api, waiting_kind):
    server, request, calls, exports = api
    path, case_id = ("/api/migrations", "DH-501") if waiting_kind == "migration" else ("/api/workflows", "DH-401")
    active_id = request(path, {"case_id": case_id})[1]["id"]
    for start_path, start_case in (("/api/migrations", "DH-501"), ("/api/workflows", "DH-401")):
        error = assert_http_error(request, 409, start_path, {"case_id": start_case})
        assert error["id"] == active_id and "waiting" in error["error"]


def test_migration_response_waits_for_any_active_raw_session(api):
    server, request, calls, exports = api
    migration_id = request("/api/migrations", {"case_id": "DH-501"})[1]["id"]
    migration = server.workflows[migration_id]
    raw_id = request("/api/runs", {"case_id": "DH-301", "mode": "raw_repo"})[1]["id"]
    response = {"interrupt_id": migration.pending["id"], "action": "decide", "choice": "defer"}
    assert assert_http_error(request, 409, f"/api/migrations/{migration_id}/respond", response)["id"] == raw_id
    assert not migration.responses and migration.status == "waiting_for_developer"


def test_graph_static_pages_and_recordings_are_readable_without_starting_a_driver(api, tmp_path, monkeypatch):
    server, request, calls, exports = api
    # The outline includes subprocess CI timing text; snapshot it once for this route check.
    outline = migration_workflow.graph_outline()
    monkeypatch.setattr(migration_workflow, "graph_outline", lambda: outline)
    graph = request("/api/migrations/graph")[1]
    assert graph == {**outline, "model": "stub-opus"}
    for path in ("/demos/migration", "/migration.js", "/migration.css"):
        status, content = request(path, raw=True)
        assert status == 200 and content.strip()
    recording_dir = tmp_path / "migration"
    recording_dir.mkdir()
    record = {"recorded_at": "2026-10-05T20:00:00+00:00", "model": "stub-opus", "context": True,
              "status": "completed", "outcome": "defer", "headline": {"hidden_passed": 12},
              "events": [{"kind": "waiting", "payload": {"kind": "decision"}}]}
    (recording_dir / "saved.json").write_text(json.dumps(record))
    (recording_dir / "partial.json").write_text("{truncated")
    listed = request("/api/migrations/recordings")[1]["recordings"]
    assert len(listed) == 1 and listed[0]["name"] == "saved"
    assert listed[0]["headline"] == record["headline"]
    assert request("/api/migrations/recordings/saved")[1] == record
    for path in ("/api/migrations/recordings/partial", "/api/migrations/recordings/missing",
                 "/api/migrations/recordings/..%2Fsecrets", "/api/workflows/recordings/saved"):
        assert_http_error(request, 404, path)
    assert not calls and not exports and not server.workflows and not server.runs
