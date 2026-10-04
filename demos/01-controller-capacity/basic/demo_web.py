"""Read-only, loopback viewer for saved synthetic developer-onramping packets."""

from __future__ import annotations

import argparse
import importlib
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"
ARTIFACT_ROOT = ROOT / "artifacts" / "onramp"
MODES = frozenset({"bm25", "semantic", "hybrid"})
RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z")
MAX_ARTIFACT_BYTES = 2_000_000
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
METADATA_FIELDS = (
    "status", "mode", "ticket_id", "model", "elapsed_seconds", "recorded_at",
    "validation", "retrieval_mode", "reason", "claim_review", "problems",
    "sources_unchanged", "agent_run", "provenance", "question",
)
SUCCESS_STATUSES = frozenset({"success", "complete", "validated"})


def _artifact_root() -> Path:
    """Do not follow a redirected artifacts directory or its onramp child."""
    root = ARTIFACT_ROOT.absolute()
    if root.is_symlink() or root.parent.is_symlink():
        raise ValueError("Saved output directory cannot be a symbolic link.")
    if root.exists() and not root.is_dir():
        raise ValueError("Saved output directory is unavailable.")
    return root


def _read_json(path: Path, *, allow_none: bool = False) -> dict | None:
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError("Saved output is unavailable.")
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("Saved output exceeds the viewer size limit.")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value is None and allow_none:
        return None
    if not isinstance(value, dict):
        raise ValueError("Saved output must be a JSON object.")
    return value


def _read_run(run_id: str, *, include_packet: bool = True) -> dict:
    if not RUN_NAME.fullmatch(run_id):
        raise ValueError("Use a saved run name, not a file path.")
    root = _artifact_root()
    directory = root / run_id
    if directory.is_symlink() or not directory.is_dir():
        raise FileNotFoundError("Saved run is unavailable.")
    if directory.resolve().parent != root.resolve():
        raise ValueError("Saved run is outside the output directory.")
    raw_metadata = _read_json(directory / "metadata.json")
    metadata = {key: raw_metadata[key] for key in METADATA_FIELDS if key in raw_metadata}
    metadata["saved_validation"] = metadata.get("validation")
    # Recheck the actual saved packet and captured evidence. A stale or forged
    # metadata.json validation flag must not make tampered output displayable.
    packet = _read_json(directory / "packet.json", allow_none=True)
    evidence = _read_json(directory / "evidence.json")
    repo_root = evidence.get("repo_root")
    permitted_root = ROOT.resolve()
    practice_root = permitted_root / "demo-workspaces"
    if not isinstance(repo_root, str) or not Path(repo_root).is_absolute():
        validation = {"status": "invalid", "errors": ["Saved evidence does not identify a permitted practice repository."], "warnings": [], "word_count": 0}
    else:
        recorded_root = Path(repo_root)
        resolved_root = recorded_root.resolve()
        allowed = resolved_root == permitted_root or resolved_root.parent == practice_root
        if not allowed or recorded_root.is_symlink() or practice_root.is_symlink():
            validation = {"status": "invalid", "errors": ["Saved evidence is outside the permitted practice repositories."], "warnings": [], "word_count": 0}
        else:
            validator = importlib.import_module("onramp_packet")
            validation = validator.validate_packet(packet, evidence)
    metadata["validation"] = validation
    succeeded = metadata.get("status") in SUCCESS_STATUSES
    sources_intact = metadata.get("sources_unchanged") is not False
    is_valid = validation.get("status") == "valid" and succeeded and sources_intact
    result = {"id": run_id, "metadata": metadata, "packet_available": is_valid}
    if include_packet:
        result["packet"] = packet if is_valid else None
        if not is_valid:
            result["error"] = (
                "This run failed or was incomplete; no success packet is displayed."
                if not succeeded else
                "Source files changed during this run; no success packet is displayed."
                if not sources_intact else
                "Current citation checks failed; no success packet is displayed."
            )
    return result


def list_runs() -> dict:
    root = _artifact_root()
    runs = []
    unreadable_count = 0
    if root.exists():
        for directory in root.iterdir():
            if not RUN_NAME.fullmatch(directory.name) or directory.is_symlink() or not directory.is_dir():
                continue
            try:
                runs.append(_read_run(directory.name, include_packet=False))
            except (OSError, ValueError, json.JSONDecodeError):
                unreadable_count += 1
    runs.sort(key=lambda run: (str(run["metadata"].get("recorded_at", "")), run["id"]), reverse=True)
    default_run_id = next((run["id"] for run in runs if run["packet_available"]), None)
    return {"runs": runs, "default_run_id": default_run_id, "unreadable_count": unreadable_count}


class DemoHandler(BaseHTTPRequestHandler):
    """Read saved packets and synthetic source records; never launch a model."""

    server_version = "DataHoneyOnramp/1.0"

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: object) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        route = urlsplit(self.path)
        path = route.path
        if path in STATIC_ROUTES:
            filename, mime = STATIC_ROUTES[path]
            try:
                content = (STATIC_ROOT / filename).read_bytes()
            except OSError:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Demo page is unavailable."})
                return
            self._send(HTTPStatus.OK, content, mime)
            return
        if path not in {"/api/runs", "/api/run", "/api/search", "/api/ticket"}:
            self._json(HTTPStatus.NOT_FOUND, {"error": "No such demo route."})
            return
        params = parse_qs(route.query, keep_blank_values=True)
        if any(len(values) != 1 for values in params.values()):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Query parameters must occur once."})
            return
        allowed = {"/api/runs": set(), "/api/run": {"id"}, "/api/search": {"q", "mode"}, "/api/ticket": {"id"}}[path]
        if set(params) - allowed:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Unknown query parameter."})
            return
        try:
            if path == "/api/runs":
                payload = list_runs()
            elif path == "/api/run":
                run_id = params.get("id", [""])[0]
                if not RUN_NAME.fullmatch(run_id):
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "Use a saved run name, not a file path."})
                    return
                payload = _read_run(run_id)
            elif path == "/api/search":
                query = params.get("q", [""])[0].strip()
                mode = params.get("mode", ["hybrid"])[0]
                if not query or len(query) > 2000:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "Enter a search query of 1–2000 characters."})
                    return
                if mode not in MODES:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "Mode must be bm25, semantic, or hybrid."})
                    return
                retriever = importlib.import_module("retriever")
                payload = retriever.search_knowledge(query, mode=mode, top_k=6)
            else:
                ticket_id = params.get("id", ["AG-1423"])[0].strip()
                if not ticket_id or len(ticket_id) > 64:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "Enter a ticket ID of 1–64 characters."})
                    return
                retriever = importlib.import_module("retriever")
                payload = retriever.get_ticket(ticket_id)
            if payload is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "No matching record in the synthetic fixture."})
                return
            self._json(HTTPStatus.OK, payload)
        except (KeyError, FileNotFoundError):
            self._json(HTTPStatus.NOT_FOUND, {"error": "No matching saved run or synthetic record."})
        except (ValueError, NotImplementedError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "The saved output or request is not valid for this viewer."})
        except Exception:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "The viewer could not read this result. Check the local output and retry."})

    def _method_not_allowed(self) -> None:
        self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "This viewer provides read-only GET endpoints."})

    do_POST = _method_not_allowed
    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed


def create_server(port: int = 8765) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), DemoHandler)
    server.daemon_threads = True
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765, help="Loopback port (default: 8765)")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    with create_server(args.port) as server:
        print(f"Saved onramping packets: http://127.0.0.1:{server.server_port}", flush=True)
        print("Read-only viewer · run the agent in your terminal · Ctrl-C to stop", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
