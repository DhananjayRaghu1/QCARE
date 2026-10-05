"""Local live-demo HTTP API. One active model session, explicit start/cancel."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
from urllib.parse import urlparse, parse_qs

from catalog import ROOT, cases, get_case, documents, get_document
from live_runner import MODES, RAW_PROMPT, Run
import portfolio


class LiveServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=8768, run_factory=Run, restore=False):
        super().__init__(("127.0.0.1", port), Handler)
        self.token = secrets.token_urlsafe(32)
        self.runs = {}
        self.lock = threading.Lock()
        self.run_factory = run_factory
        self.workers = []
        if restore:
            for path in sorted((ROOT / "artifacts/live").glob("*/result.json"), key=lambda p: p.stat().st_mtime)[-30:]:
                try:
                    result = json.loads(path.read_text())
                    if result.get("mode") == "workflow" and '"title":' in result.get("prompt", ""):
                        result["comparability_warning"] = "Historical guided run: its input included a scenario title that disclosed the diagnosis. Do not use it as a fair raw-versus-guided comparison. New runs omit that title."
                    run = Run(result["case_id"], result["mode"])
                    run.id, run.result, run.status = result["id"], result, result["status"]
                    events = path.with_name("events.json")
                    warnings = []
                    if events.exists():
                        try:
                            saved_events = json.loads(events.read_text())
                            if not isinstance(saved_events, list) or not all(isinstance(event, dict) for event in saved_events):
                                raise ValueError("Invalid saved events")
                            run.events = saved_events
                        except (ValueError, OSError):
                            warnings.append("Saved activity was incomplete; recovered available events from the trace.")
                    if not events.exists() or warnings:
                        # Older live records predate the saved display-event stream.
                        trace = path.with_name("trace.jsonl")
                        if trace.exists():
                            for line in trace.read_text().splitlines():
                                try:
                                    event = json.loads(line)
                                except ValueError:
                                    warnings.append("Skipped an incomplete trace line; the saved result is retained.")
                                    continue
                                if isinstance(event, dict):
                                    run.consume(event)
                            for event in run.events:
                                event["seconds"] = None
                    if warnings:
                        result["restore_warnings"] = list(dict.fromkeys(warnings))
                    self.runs[run.id] = run
                except (ValueError, KeyError, OSError):
                    continue

    def server_close(self):
        for run in self.runs.values():
            run.cancel.set()
        for worker in self.workers:
            worker.join(timeout=5)
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, value, content_type="application/json; charset=utf-8"):
        body = json.dumps(value).encode() if content_type.startswith("application/json") else value.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def local_request(self):
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if host not in allowed or (origin and origin != "http://" + host):
            self.respond(403, {"error": "Local same-origin requests only."})
            return False
        return True

    def do_GET(self):
        if not self.local_request():
            return
        url = urlparse(self.path)
        if url.path == "/" or url.path in ("/demos/export", "/demos/migration"):
            return self.respond(200, (ROOT / "portfolio.html").read_text(), "text/html; charset=utf-8")
        if url.path in ("/demos/report", "/live.html"):
            return self.respond(200, (ROOT / "live.html").read_text(), "text/html; charset=utf-8")
        if url.path.startswith("/architecture/") and url.path.rsplit("/",1)[-1] in portfolio.DEFINITIONS:
            import architecture
            return self.respond(200, architecture.render(url.path.rsplit("/",1)[-1]), "text/html; charset=utf-8")
        if url.path == "/api/demos":
            return self.respond(200, {"demos": list(portfolio.DEFINITIONS.values())})
        if url.path.startswith("/api/demos/") and url.path.rsplit("/",1)[-1] in portfolio.DEFINITIONS:
            return self.respond(200, portfolio.public_demo(url.path.rsplit("/",1)[-1]))
        if url.path == "/api/examples/export":
            return self.respond(200, portfolio.reference_export())
        if url.path == "/api/examples/migration":
            return self.respond(200, portfolio.reference_migration())
        if url.path in ("/portfolio.js", "/portfolio.css"):
            kind = "text/javascript" if url.path.endswith(".js") else "text/css"
            return self.respond(200, (ROOT / url.path[1:]).read_text(), kind + "; charset=utf-8")
        if url.path in ("/reader.js", "/reader.css"):
            kind = "text/javascript" if url.path.endswith(".js") else "text/css"
            return self.respond(200, (ROOT / url.path[1:]).read_text(), kind + "; charset=utf-8")
        if url.path == "/api/documents":
            return self.respond(200, {"documents": [get_document(key) for key in documents()]})
        if url.path.startswith("/documents/"):
            from source_pages import render_document
            page = render_document(url.path.rsplit("/", 1)[-1])
            if page:
                return self.respond(200, page, "text/html; charset=utf-8")
        if url.path.startswith("/api/walkthroughs/"):
            case_id = url.path.rsplit("/", 1)[-1]
            if case_id in cases():
                from reconcile import reconcile
                return self.respond(200, reconcile(case_id))
        if url.path == "/api/config":
            with self.server.lock:
                runs = [{"id": run.id, "case_id": run.case_id, "mode": run.mode,
                         "status": run.status} for run in self.server.runs.values()]
            return self.respond(200, {"token": self.server.token, "modes": MODES,
                "prompt": RAW_PROMPT, "cases": [{"id": item["id"], "customer": item["customer"],
                    "month": item["month"]} for item in cases().values() if item["id"] == "DH-301"],
                "budget_usd": 1.0, "timeout_seconds": 240,
                "runs": runs})
        if url.path.startswith("/api/cases/"):
            case_id = url.path.rsplit("/", 1)[-1]
            if case_id in cases():
                case = get_case(case_id)
                # No solution-revealing scenario titles in the live task view.
                case["case"].pop("title", None)
                return self.respond(200, case)
        if url.path.startswith("/api/runs/"):
            run_id = url.path.rsplit("/", 1)[-1]
            with self.server.lock:
                run = self.server.runs.get(run_id)
            if run:
                try:
                    after = int(parse_qs(url.query).get("after", ["0"])[0])
                    if after < 0:
                        raise ValueError()
                except ValueError:
                    return self.respond(400, {"error": "Invalid event cursor."})
                return self.respond(200, run.snapshot(after))
        self.respond(404, {"error": "Not found."})

    def do_POST(self):
        if not self.local_request():
            return
        if not secrets.compare_digest(self.headers.get("X-Demo-Token", ""), self.server.token):
            return self.respond(403, {"error": "Reload the page before starting a run."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16000:
                raise ValueError()
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            return self.respond(400, {"error": "Invalid request body."})
        if self.path == "/api/runs":
            case_id, mode = body.get("case_id"), body.get("mode")
            demo_name = portfolio.CASE_DEMOS.get(case_id) if isinstance(case_id, str) else None
            prompt = body.get("prompt", portfolio.PROMPTS.get(demo_name, RAW_PROMPT))
            if (not isinstance(case_id, str) or case_id not in portfolio.CASE_DEMOS
                    or not isinstance(mode, str) or mode not in MODES
                    or (demo_name != "report" and mode == "workflow")
                    or not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 6000):
                return self.respond(400, {"error": "Choose a known case and mode, and a prompt of 1–6000 characters."})
            with self.server.lock:
                active = next((run for run in self.server.runs.values() if run.status == "running"), None)
                if active:
                    return self.respond(409, {"error": "A run is already active. Stop it or wait for it to finish.", "id": active.id})
                run = self.server.run_factory(case_id, mode, prompt)
                self.server.runs[run.id] = run
                worker = threading.Thread(target=run.execute, daemon=False)
                self.server.workers.append(worker)
                worker.start()
            return self.respond(202, {"id": run.id})
        if self.path.startswith("/api/runs/") and self.path.endswith("/cancel"):
            run_id = self.path.split("/")[-2]
            with self.server.lock:
                run = self.server.runs.get(run_id)
            if run:
                run.cancel.set()
                return self.respond(200, {"status": "stop_requested"})
        self.respond(404, {"error": "Not found."})


def serve(port=8768):
    server = LiveServer(port, restore=True)
    print(f"Live demo: http://127.0.0.1:{server.server_port}/", flush=True)
    print("Click Run to start a fresh Claude session. Synthetic fixtures; no live Jira connection.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8768)
    serve(parser.parse_args().port)
