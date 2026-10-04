"""Read-only artifact boundary and honest review-state presentation."""

from copy import deepcopy
from email.message import Message
import hashlib
from io import BytesIO
import json

import pytest

from evidence import materialize_packet
from viewer import ArtifactError, ArtifactStore, MAX_JSON_BYTES, handler_for, inspected_bundle


@pytest.fixture
def bundle():
    content = "def validate(zones):\n    return len(zones) <= 20\n"
    captured = {"ticket_id": "AG-1423", "sources": {
        "app/validator.py": {
            "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "spans": [[1, 2]], "kind": "code", "metadata": {},
        },
    }}
    packet = {
        "ticket_id": "AG-1423",
        "device": {"controller_id": "DEV-101", "model": "Unknown", "firmware": "Unknown", "citations": []},
        "policy": {"status": "unknown", "text": "Unknown: approved policy was not retrieved.", "citations": []},
        "diagnosis": {"classification": "insufficient_evidence", "text": "The implementation enforces twenty zones.", "citations": ["code"]},
        "starting_files": [{"path": "app/validator.py", "line_start": 1, "line_end": 2, "reason": "Capacity is checked here.", "citations": ["code"]}],
        "execution_path": {"text": "The validator counts zones.", "citations": ["code"]},
        "history": [], "owner": {"text": "Unknown", "citations": []},
        "next_action": {"text": "Obtain approved policy before changing this limit.", "citations": ["code"]},
        "unknowns": ["What capacity is approved?"],
        "citations": [{"id": "code", "source": "app/validator.py", "line_start": 1, "line_end": 2}],
    }
    return {
        "format_version": 1,
        "metadata": {
            "run_id": "run-1", "workspace": "first-session", "phase": "investigate",
            "ticket_id": "AG-1423", "context": "repo", "mode": "bm25",
            "recorded_at": "2026-10-04T17:00:00Z", "status": "success",
            "model": "recorded-model", "elapsed_seconds": 4.2, "problems": [],
            "claim_review": "pending", "sources_unchanged": True,
        },
        "packet": materialize_packet(packet, captured), "evidence": captured,
        "tools": [{"name": "Read", "input": {"file_path": "app/validator.py"}}],
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def store(tmp_path, bundle):
    write_json(tmp_path / "artifacts/runs/run-1/bundle.json", bundle)
    return ArtifactStore(tmp_path)


def request(store, path, method="GET"):
    """Exercise the HTTP handler without opening sockets in test sandboxes."""
    handler = object.__new__(handler_for(store))
    handler.path = path
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.command = method
    handler.headers = Message()
    handler.wfile = BytesIO()
    handler.rfile = BytesIO()
    getattr(handler, f"do_{method}")()
    response = handler.wfile.getvalue()
    head, body = response.split(b"\r\n\r\n", 1)
    code = int(head.split(b" ", 2)[1])
    return code, head, body


def test_valid_packet_has_separate_provenance_and_human_claim_review(bundle):
    original = deepcopy(bundle)
    result = inspected_bundle(bundle)
    assert bundle == original
    checked = result["viewer_validation"]
    assert checked["status"] == "valid"
    assert checked["packet"]["status"] == "valid"
    assert checked["claim_review"] == "pending"
    assert checked["claim_support"] == "not_established"
    assert "do not establish claim support" in checked["notice"]


@pytest.mark.parametrize("change", [
    lambda b: b["packet"]["citations"][0].update(excerpt="invented"),
    lambda b: b["evidence"]["sources"]["app/validator.py"].update(content="changed\n"),
    lambda b: b["evidence"]["sources"]["app/validator.py"].update(spans=[[1, 1]]),
    lambda b: b["packet"].update(invented_field="invalid schema"),
])
def test_saved_packets_are_rechecked_not_trusted(bundle, change):
    change(bundle)
    checked = inspected_bundle(bundle)["viewer_validation"]
    assert checked["status"] == "invalid"
    assert checked["source_errors"]


@pytest.mark.parametrize("field,value", [
    ("phase", []), ("status", {}), ("elapsed_seconds", True),
    ("problems", "nothing"), ("ticket_id", None), ("claim_review", 0),
    ("sources_unchanged", "yes"),
])
def test_invalid_metadata_is_visible_without_crashing(bundle, field, value):
    bundle["metadata"][field] = value
    checked = inspected_bundle(bundle)["viewer_validation"]
    assert checked["status"] == "invalid"
    assert checked["metadata_errors"]


def test_bad_bundle_types_do_not_appear_verified(bundle):
    assert inspected_bundle({})["viewer_validation"]["status"] == "invalid"
    bundle["metadata"] = []
    assert inspected_bundle(bundle)["viewer_validation"]["status"] == "invalid"


def test_recorded_approval_is_not_automatic_provenance_approval(bundle):
    bundle["metadata"]["claim_review"] = {"status": "approved", "reviewer": "human"}
    result = inspected_bundle(bundle)
    assert result["viewer_validation"]["claim_support"] == "human_review_recorded"
    bundle["packet"]["citations"][0]["excerpt"] = "tampered"
    assert inspected_bundle(bundle)["viewer_validation"]["status"] == "invalid"


def test_failed_run_retains_real_problems_and_elapsed_time(store, bundle):
    bundle["metadata"].update(status="failed", problems=["Tool call was denied"], elapsed_seconds=90.0)
    bundle.pop("packet")
    write_json(store.runs_root / "run-1/bundle.json", bundle)
    result = store.run("run-1")
    assert result["metadata"]["status"] == "failed"
    assert result["metadata"]["problems"] == ["Tool call was denied"]
    assert result["metadata"]["elapsed_seconds"] == 90.0
    assert result["viewer_validation"]["packet"]["status"] == "not_applicable"


def test_no_packet_phase_still_checks_captured_source_hashes(bundle):
    bundle.pop("packet")
    bundle["metadata"]["phase"] = "verify"
    bundle["evidence"]["sources"]["app/validator.py"]["sha256"] = "0" * 64
    assert inspected_bundle(bundle)["viewer_validation"]["source_errors"]


@pytest.mark.parametrize("phase", ["reproduce", "fix", "verify"])
def test_cli_phase_metadata_does_not_require_investigation_only_fields(bundle, phase):
    bundle.pop("packet")
    bundle["metadata"]["phase"] = phase
    for name in ("context", "mode", "sources_unchanged"):
        bundle["metadata"].pop(name)
    if phase == "verify":
        for name in ("ticket_id", "claim_review"):
            bundle["metadata"].pop(name)
        bundle["metadata"].update(model=None, provenance="actual_test_execution")
    checked = inspected_bundle(bundle)["viewer_validation"]
    assert checked["status"] == "valid"
    if phase == "verify":
        assert checked["claim_review"] == "not_applicable"


def test_successful_investigation_cannot_omit_its_packet(bundle):
    bundle.pop("packet")
    assert inspected_bundle(bundle)["viewer_validation"]["status"] == "invalid"


@pytest.mark.parametrize("value", ["yesterday", "2026-10-04T17:00:00"])
def test_invalid_recorded_timestamp_is_warning(bundle, value):
    bundle["metadata"]["recorded_at"] = value
    assert inspected_bundle(bundle)["viewer_validation"]["status"] == "invalid"


def test_listing_labels_runs_and_rehearsals_and_rechecks_nested_packets(store, bundle):
    session = {
        "format_version": 1, "provenance": "recorded_rehearsal",
        "workspace": "first-session", "recorded_at": "2026-10-04T18:00:00Z",
        "runs": [bundle], "report_markdown": "Recorded report", "readiness": {"status": "ready"},
    }
    write_json(store.replays_root / "rehearsal-1/session.json", session)
    listing = store.listing()
    assert [item["id"] for item in listing] == ["rehearsal-1", "run-1"]
    assert listing[0]["label"] == "Recorded rehearsal"
    assert listing[1]["label"] == "Actual recorded run"
    result = store.replay("rehearsal-1")
    assert result["runs"][0]["viewer_validation"]["packet"]["status"] == "valid"
    session["runs"][0]["packet"]["citations"][0]["excerpt"] = "tampered"
    write_json(store.replays_root / "rehearsal-1/session.json", session)
    assert store.replay("rehearsal-1")["viewer_validation"]["status"] == "invalid"


@pytest.mark.parametrize("session", [
    {}, {"format_version": 1, "runs": [None]},
    {"format_version": 1, "runs": "not a list", "readiness": []},
])
def test_bad_session_shape_is_warning_not_crash(store, session):
    write_json(store.replays_root / "bad-session/session.json", session)
    assert store.replay("bad-session")["viewer_validation"]["status"] == "invalid"
    assert store.listing()[0]["validation"] == "valid"  # valid run sorts first


@pytest.mark.parametrize("identifier", ["../run-1", "..", "/tmp", "run/1", "run\\1", "run-1\n", "x" * 101, ""])
def test_ids_cannot_escape_artifact_roots(store, identifier):
    with pytest.raises(ArtifactError):
        store.run(identifier)
    with pytest.raises(ArtifactError):
        store.replay(identifier)


def test_symbolic_folder_and_file_paths_are_rejected(store, tmp_path, bundle):
    outside = tmp_path / "outside"
    write_json(outside / "bundle.json", bundle)
    (store.runs_root / "symbolic-folder").symlink_to(outside, target_is_directory=True)
    (store.runs_root / "symbolic-file").mkdir()
    (store.runs_root / "symbolic-file/bundle.json").symlink_to(outside / "bundle.json")
    for identifier in ("symbolic-folder", "symbolic-file"):
        with pytest.raises(ArtifactError):
            store.run(identifier)
    assert "symbolic-folder" not in [item["id"] for item in store.listing()]


def test_symbolic_ancestor_roots_are_rejected(tmp_path, bundle):
    target = tmp_path / "target"
    write_json(target / "runs/run-1/bundle.json", bundle)
    (tmp_path / "artifacts").symlink_to(target, target_is_directory=True)
    store = ArtifactStore(tmp_path)
    assert store.listing() == []
    with pytest.raises(ArtifactError):
        store.run("run-1")


@pytest.mark.parametrize("payload", [b"[]", b"{broken", b'{"time":NaN}', b'{"time":Infinity}', b"\xff"])
def test_bad_json_is_listed_as_unreadable(store, payload):
    (store.runs_root / "run-1/bundle.json").write_bytes(payload)
    assert store.listing()[0]["metadata"]["status"] == "unreadable"
    with pytest.raises(ArtifactError):
        store.run("run-1")


def test_large_json_artifacts_are_not_read(store):
    (store.runs_root / "run-1/bundle.json").write_bytes(b" " * (MAX_JSON_BYTES + 1))
    with pytest.raises(ArtifactError):
        store.run("run-1")


def test_http_read_routes_and_head_support(store):
    status, headers, body = request(store, "/api/run?id=run-1")
    assert status == 200
    assert json.loads(body)["metadata"]["run_id"] == "run-1"
    assert b"Cache-Control: no-store" in headers
    assert b"X-Content-Type-Options: nosniff" in headers
    status, headers, body = request(store, "/api/runs", "HEAD")
    assert status == 200 and body == b""
    assert b"Content-Length:" in headers
    status, _, body = request(store, "/api/runs")
    assert json.loads(body)["runs"][0]["label"] == "Actual recorded run"
    assert request(store, "/favicon.ico")[0] == 204


@pytest.mark.parametrize("path,status", [
    ("/api/run?id=..%2Frun-1", 400), ("/api/run?id=%2Ftmp", 400),
    ("/api/run?id=run-1&id=other", 400), ("/api/run?id=run-1&file=secret", 400),
    ("/api/run", 400), ("/api/run?id=", 400),
    ("/api/source?path=secret", 404), ("/api/run?id=missing", 404),
    ("/artifacts/runs/run-1/bundle.json", 404),
    ("http://foreign.example/api/runs", 400),
])
def test_no_filesystem_query_or_ambiguous_routes(store, path, status):
    assert request(store, path)[0] == status


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_http_has_no_mutating_endpoints(store, method):
    status, _, body = request(store, "/api/run?id=run-1", method)
    assert status == 405
    assert "GET and HEAD only" in json.loads(body)["error"]


def test_static_page_is_allowlisted_and_content_is_inserted_as_text(store):
    from pathlib import Path
    page = Path(__file__).parents[1] / "static/index.html"
    destination = store.root / "static/index.html"
    destination.parent.mkdir()
    destination.write_bytes(page.read_bytes())
    status, headers, body = request(store, "/")
    assert status == 200
    assert b"text/html" in headers
    assert b"Content-Security-Policy:" in headers
    assert b"textContent" in body and b"innerHTML" not in body
    assert b"Human claim review" in body
    assert b"no work is executing now" in body
    assert request(store, "/static/index.html")[0] == 404
