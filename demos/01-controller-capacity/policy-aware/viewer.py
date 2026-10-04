"""Read-only local viewer for captured runs and portable recorded rehearsals.

Only allowlisted JSON artifacts are readable; no route executes a model, shell
command, or application code. Validation uses captured evidence, never a live
checkout, so a replay can be inspected after its workspace has moved.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from evidence import validate_packet

ROOT = Path(__file__).absolute().parent
MAX_JSON_BYTES = 4 * 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
PHASES = {"investigate", "reproduce", "fix", "verify", "baseline"}
STATUSES = {"success", "partial", "failed"}


class ArtifactError(ValueError):
    """An artifact is unavailable, malformed, too large, or outside its root."""


def _without_symlinks(path: Path) -> bool:
    return not any(part.is_symlink() for part in (path, *path.parents))


def _safe_path(root: Path, identifier: str, filename: str) -> Path:
    if not isinstance(identifier, str) or not SAFE_ID.fullmatch(identifier):
        raise ArtifactError("Invalid artifact identifier.")
    root = root.absolute()
    path = root / identifier / filename
    if not _without_symlinks(path):
        raise ArtifactError("Symbolic artifact paths are not allowed.")
    # Defense in depth if this helper gains another caller in the future.
    if not path.resolve().is_relative_to(root.resolve()):
        raise ArtifactError("Artifact path is outside its allowed directory.")
    return path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise ArtifactError("Artifact is missing or exceeds the 4 MiB limit.")
        # Read at most the limit even if a file grows after stat().
        with path.open("rb") as stream:
            data = stream.read(MAX_JSON_BYTES + 1)
        if len(data) > MAX_JSON_BYTES:
            raise ArtifactError("Artifact exceeds the 4 MiB limit.")
        result = json.loads(data.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ArtifactError("Artifact could not be read as finite JSON.") from exc
    if not isinstance(result, dict):
        raise ArtifactError("Artifact must contain a JSON object.")
    return result


def _metadata_errors(bundle: dict[str, Any]) -> list[str]:
    errors = []
    if type(bundle.get("format_version")) is not int or bundle["format_version"] != 1:
        errors.append("Unsupported bundle format version.")
    metadata = bundle.get("metadata")
    if not isinstance(metadata, dict):
        return errors + ["Run metadata must be an object."]
    phase = metadata.get("phase")
    required_text = ["run_id", "workspace", "recorded_at"]
    if phase in ("investigate", "reproduce", "fix", "baseline"):
        required_text.append("ticket_id")
    if phase == "investigate":
        required_text.extend(("context", "mode"))
    for name in required_text:
        if not isinstance(metadata.get(name), str) or not metadata[name].strip():
            errors.append(f"Run metadata {name} is missing or invalid.")
    if isinstance(metadata.get("recorded_at"), str):
        try:
            if datetime.fromisoformat(metadata["recorded_at"]).tzinfo is None:
                raise ValueError("Missing timezone")
        except ValueError:
            errors.append("Run recorded time must be an ISO timestamp with a timezone.")
    if not isinstance(metadata.get("phase"), str) or metadata["phase"] not in PHASES:
        errors.append("Run phase is missing or unsupported.")
    if not isinstance(metadata.get("status"), str) or metadata["status"] not in STATUSES:
        errors.append("Run status is missing or unsupported.")
    elapsed = metadata.get("elapsed_seconds")
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
        errors.append("Run elapsed time is missing or invalid.")
    if not isinstance(metadata.get("problems"), list) or not all(isinstance(item, str) for item in metadata.get("problems", [])):
        errors.append("Run problems must be an array of text.")
    if phase in ("investigate", "reproduce", "fix") and not isinstance(metadata.get("claim_review"), (str, dict)):
        errors.append("Human claim-review status is missing or invalid.")
    if phase == "investigate" and not isinstance(metadata.get("sources_unchanged"), bool):
        errors.append("Source-change status is missing or invalid.")
    if phase == "investigate" and metadata.get("status") == "success" and bundle.get("packet") is None:
        errors.append("A successful investigation needs a decision packet.")
    return errors


def _source_errors(evidence: Any) -> list[str]:
    """Check captured hashes even for phases without a decision packet."""
    if evidence is None:
        return []
    if not isinstance(evidence, dict) or not isinstance(evidence.get("sources"), dict):
        return ["Captured evidence must contain a sources object."]
    errors = []
    for name, source in evidence["sources"].items():
        if not isinstance(source, dict) or not isinstance(source.get("content"), str):
            errors.append(f"Captured source {name!r} is malformed.")
            continue
        if source.get("sha256") != hashlib.sha256(source["content"].encode("utf-8")).hexdigest():
            errors.append(f"Captured source {name!r} has a content-hash mismatch.")
    return errors


def inspected_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Attach independent viewer checks without overwriting recorded outcomes."""
    result = deepcopy(bundle)
    metadata_errors = _metadata_errors(bundle)
    source_errors = _source_errors(bundle.get("evidence"))
    packet = bundle.get("packet")
    if packet is not None:
        packet_check = validate_packet(packet, bundle.get("evidence"))
        source_errors.extend(packet_check["errors"])
    else:
        packet_check = {
            "status": "not_applicable", "errors": [],
            "warnings": ["This phase has no decision packet to check."],
        }
    metadata = bundle.get("metadata") if isinstance(bundle.get("metadata"), dict) else {}
    review = metadata.get("claim_review", "not_applicable" if metadata.get("phase") == "verify" else "pending")
    review_status = review.get("status", "pending") if isinstance(review, dict) else review
    result["viewer_validation"] = {
        "status": "invalid" if metadata_errors or source_errors else "valid",
        "metadata_errors": metadata_errors,
        "source_errors": list(dict.fromkeys(source_errors)),
        "packet": packet_check,
        "claim_review": review_status,
        "claim_support": "human_review_recorded" if review_status == "approved" else "not_established",
        "notice": "Source hashes and read coverage do not establish claim support. Human review is required.",
    }
    return result


class ArtifactStore:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root).absolute()
        self.runs_root = self.root / "artifacts" / "runs"
        self.replays_root = self.root / "replays"

    def run(self, identifier: str) -> dict[str, Any]:
        return inspected_bundle(_load_json(_safe_path(self.runs_root, identifier, "bundle.json")))

    def replay(self, identifier: str) -> dict[str, Any]:
        session = _load_json(_safe_path(self.replays_root, identifier, "session.json"))
        errors = []
        if type(session.get("format_version")) is not int or session["format_version"] != 1:
            errors.append("Unsupported session format version.")
        if session.get("provenance") != "recorded_rehearsal":
            errors.append("Session is not labeled as a recorded rehearsal.")
        for name in ("workspace", "recorded_at"):
            if not isinstance(session.get(name), str) or not session[name].strip():
                errors.append(f"Session {name} is missing or invalid.")
        if not isinstance(session.get("report_markdown"), str):
            errors.append("Session report must be text.")
        if not isinstance(session.get("readiness"), dict):
            errors.append("Session readiness must be an object.")
        runs = session.get("runs")
        if not isinstance(runs, list):
            errors.append("Session runs must be an array.")
            runs = []
        checked_runs = []
        for index, run in enumerate(runs):
            if not isinstance(run, dict):
                errors.append(f"Session run {index + 1} must be an object.")
                continue
            checked = inspected_bundle(run)
            checked_runs.append(checked)
            if checked["viewer_validation"]["status"] != "valid":
                errors.append(f"Session run {index + 1} failed artifact checks.")
        session["runs"] = checked_runs
        session["viewer_validation"] = {
            "status": "invalid" if errors else "valid", "errors": errors,
            "notice": "Recorded rehearsal; this viewer does not execute the application or model.",
        }
        return session

    def _entries(self, root: Path, filename: str, kind: str) -> list[dict[str, Any]]:
        if not root.is_dir() or not _without_symlinks(root):
            return []
        results = []
        for directory in root.iterdir():
            identifier = directory.name
            if not SAFE_ID.fullmatch(identifier) or directory.is_symlink() or not directory.is_dir():
                continue
            if not (directory / filename).exists():
                continue
            try:
                record = self.run(identifier) if kind == "run" else self.replay(identifier)
                readiness = record.get("readiness", {}) if isinstance(record.get("readiness"), dict) else {}
                metadata = record.get("metadata", {}) if kind == "run" else {
                    "workspace": record.get("workspace"), "recorded_at": record.get("recorded_at"),
                    "status": readiness.get("status", "complete" if readiness.get("workflow_complete") else "incomplete"),
                    "phase": "session", "ticket_id": "Recorded session",
                    "workflow_complete": readiness.get("workflow_complete", readiness.get("status") == "ready"),
                }
                results.append({
                    "id": identifier, "kind": kind,
                    "label": "Actual recorded run" if kind == "run" else "Recorded rehearsal",
                    "metadata": metadata if isinstance(metadata, dict) else {},
                    "validation": record["viewer_validation"]["status"],
                })
            except ArtifactError as exc:
                results.append({
                    "id": identifier, "kind": kind,
                    "label": "Actual recorded run" if kind == "run" else "Recorded rehearsal",
                    "metadata": {"status": "unreadable", "problems": [str(exc)]},
                    "validation": "invalid",
                })
        return results

    def listing(self) -> list[dict[str, Any]]:
        entries = self._entries(self.runs_root, "bundle.json", "run") + self._entries(self.replays_root, "session.json", "replay")
        return sorted(entries, key=lambda item: (
            item["kind"] == "replay" and item["validation"] == "valid" and item["metadata"].get("workflow_complete") is True,
            item["metadata"].get("recorded_at") if isinstance(item["metadata"].get("recorded_at"), str) else "",
        ), reverse=True)


def handler_for(store: ArtifactStore) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "PolicyEvidenceViewer/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _response(self, status: int, content: bytes, content_type: str, head: bool = False) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            if not head:
                self.wfile.write(content)

        def _json(self, status: int, value: Any, head: bool = False) -> None:
            self._response(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8", head)

        def _get(self, head: bool = False) -> None:
            # Reject absolute-form requests and encoded route ambiguity.
            route = urlsplit(self.path)
            if route.scheme or route.netloc:
                self._json(400, {"error": "Invalid request target."}, head)
                return
            if route.path in {"/", "/index.html"} and not route.query:
                path = store.root / "static" / "index.html"
                if not _without_symlinks(path) or not path.is_file():
                    self._json(404, {"error": "Viewer page is unavailable."}, head)
                    return
                self._response(200, path.read_bytes(), "text/html; charset=utf-8", head)
                return
            if route.path == "/favicon.ico":
                self._response(204, b"", "image/x-icon", head)
                return
            if route.path == "/api/runs" and not route.query:
                self._json(200, {"runs": store.listing()}, head)
                return
            if route.path not in {"/api/run", "/api/replay"}:
                self._json(404, {"error": "Route not found."}, head)
                return
            params = parse_qs(route.query, keep_blank_values=True)
            if set(params) != {"id"} or len(params["id"]) != 1 or not SAFE_ID.fullmatch(params["id"][0]):
                self._json(400, {"error": "Exactly one safe artifact identifier is required."}, head)
                return
            try:
                artifact = store.run(params["id"][0]) if route.path == "/api/run" else store.replay(params["id"][0])
            except ArtifactError as exc:
                self._json(404, {"error": str(exc)}, head)
                return
            self._json(200, artifact, head)

        def do_GET(self) -> None:
            self._get()

        def do_HEAD(self) -> None:
            self._get(head=True)

        def _not_allowed(self) -> None:
            self._json(405, {"error": "This viewer supports GET and HEAD only."})

        do_POST = _not_allowed
        do_PUT = _not_allowed
        do_PATCH = _not_allowed
        do_DELETE = _not_allowed
        do_OPTIONS = _not_allowed

    return Handler


def serve(port: int = 8766) -> None:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("Port must be an integer between 1 and 65535.")
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(ArtifactStore()))
    print(f"Read-only evidence viewer: http://127.0.0.1:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    serve(parser.parse_args().port)
