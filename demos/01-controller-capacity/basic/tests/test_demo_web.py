"""Exercise saved-packet boundaries over a real ephemeral loopback socket."""

from __future__ import annotations

import json
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from demo_web import create_server


class DemoWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "onramp"
        self.root.mkdir()
        self.project = Path(self.temporary.name)
        self.root_patch = patch("demo_web.ARTIFACT_ROOT", self.root)
        self.project_patch = patch("demo_web.ROOT", self.project)
        self.root_patch.start()
        self.project_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.project_patch.stop()
        self.temporary.cleanup()

    def request(self, path, method="GET"):
        request = Request(self.base + path, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            with error:
                return error.code, error.headers, error.read()

    def save_run(self, name, *, recorded_at="2026-10-04T14:00:00Z", valid=True, mode="augmented"):
        directory = self.root / name
        directory.mkdir()
        metadata = {
            "status": "complete" if valid else "failed",
            "claim_review": "pending",
            "sources_unchanged": True,
            "mode": mode,
            "ticket_id": "AG-1423",
            "model": "recorded-model" if mode != "local-sample" else None,
            "elapsed_seconds": 12.3,
            "recorded_at": recorded_at,
            "validation": {"status": "valid" if valid else "invalid", "errors": [] if valid else ["Missing code read"], "warnings": [], "word_count": 260},
            "internal_detail": "must not be returned",
        }
        code = "def create_schedule(payload):\n    return repository.save(payload)\n"
        app = self.project / "app"
        app.mkdir(exist_ok=True)
        (app / "service.py").write_text(code)
        document = "# Scheduling Architecture\nScheduling Backend owns this component.\n"
        ticket = "# AG-1423\nSome Pro customers cannot save schedules.\n"
        evidence = {
            "repo_root": str(self.project),
            "code_files": {"app/service.py": code},
            "code_spans": {"app/service.py": [[1, 2]]},
            "documents": {"knowledge/architecture.md": document, "knowledge/ticket.md": ticket},
        }
        packet = {
            "ticket_id": "AG-1423",
            "summary": "Some Pro customers cannot save schedules.",
            "summary_citations": ["T1"],
            "likely_subsystem": {"text": "Scheduling backend", "citations": ["D1"]},
            "starting_files": [{"path": "app/service.py", "line_start": 1, "line_end": 2, "reason": "Start at the save entry point", "citations": ["C1"]}],
            "execution_path": {"text": "Controller to repository", "citations": ["D1"]},
            "history": [],
            "owner": {"text": "Unknown", "citations": []},
            "first_investigation": {"text": "Check the request passed to persistence", "citations": ["C1"]},
            "unknowns": ["The affected customer configuration"],
            "citations": [
                {"id": "D1", "kind": "knowledge", "source": "knowledge/architecture.md", "line_start": 2, "line_end": 2, "excerpt": "Scheduling Backend owns this component."},
                {"id": "C1", "kind": "code", "source": "app/service.py", "line_start": 1, "line_end": 2, "excerpt": code.rstrip()},
                {"id": "T1", "kind": "knowledge", "source": "knowledge/ticket.md", "line_start": 2, "line_end": 2, "excerpt": "Some Pro customers cannot save schedules."},
            ],
        }
        (directory / "metadata.json").write_text(json.dumps(metadata))
        (directory / "packet.json").write_text(json.dumps(packet))
        (directory / "evidence.json").write_text(json.dumps(evidence))
        return directory, packet

    def test_server_is_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_browser_page_explains_provenance_and_serves_local_assets(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        page = body.decode("utf-8")
        self.assertIn("Synthetic practice application", page)
        self.assertIn("saved outputs are replayed here", page)
        self.assertIn("Exact fetch", page)
        self.assertIn("Ranked search", page)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        for path in ("/static/styles.css", "/static/app.js"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 200)
        script = self.request("/static/app.js")[2].decode()
        self.assertIn("Deterministic sample", script)
        self.assertIn("This is not Claude output", script)
        self.assertNotIn("innerHTML", script)

    def test_list_defaults_to_latest_valid_packet_without_hiding_failed_runs(self):
        self.save_run("old", recorded_at="2026-10-04T12:00:00Z", mode="local-sample")
        self.save_run("new-valid", recorded_at="2026-10-04T13:00:00Z")
        self.save_run("new-failed", recorded_at="2026-10-04T14:00:00Z", valid=False)
        status, _, body = self.request("/api/runs")
        result = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(result["default_run_id"], "new-valid")
        self.assertEqual([run["id"] for run in result["runs"]], ["new-failed", "new-valid", "old"])
        self.assertFalse(result["runs"][0]["packet_available"])
        self.assertNotIn("internal_detail", result["runs"][1]["metadata"])

    def test_run_returns_exact_saved_packet_and_failure_never_gets_a_packet(self):
        _, packet = self.save_run("saved")
        self.save_run("failed", valid=False)
        status, _, body = self.request("/api/run?id=saved")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["packet"], packet)
        status, _, body = self.request("/api/run?id=failed")
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(body)["packet"])
        self.assertFalse(json.loads(body)["packet_available"])

    def test_empty_and_corrupt_outputs_are_visible_without_fake_success(self):
        result = json.loads(self.request("/api/runs")[2])
        self.assertEqual(result["runs"], [])
        self.assertIsNone(result["default_run_id"])
        directory, _ = self.save_run("broken")
        (directory / "packet.json").write_text("{not JSON")
        result = json.loads(self.request("/api/runs")[2])
        self.assertEqual(result["unreadable_count"], 1)
        self.assertIsNone(result["default_run_id"])
        self.assertEqual(self.request("/api/run?id=broken")[0], 400)

    def test_artifact_paths_and_symlinks_cannot_escape_fixed_root(self):
        directory, _ = self.save_run("original")
        (self.root / "linked-run").symlink_to(directory, target_is_directory=True)
        for path in ("/api/run?id=../outside", "/api/run?id=%2Fprivate%2Fsecret", "/api/run?id=linked-run", "/api/run?id=missing"):
            with self.subTest(path=path):
                self.assertIn(self.request(path)[0], (400, 404))
        external = self.root.parent / "external.json"
        external.write_text('{"private": "do not return"}')
        (directory / "packet.json").unlink()
        (directory / "packet.json").symlink_to(external)
        self.assertEqual(self.request("/api/run?id=original")[0], 404)
        self.assertNotIn(b"do not return", self.request("/api/run?id=original")[2])

    def test_saved_validation_flag_cannot_hide_tampered_excerpt(self):
        directory, packet = self.save_run("tampered")
        packet["citations"][0]["excerpt"] = "Owner: Billing Backend"
        (directory / "packet.json").write_text(json.dumps(packet))
        result = json.loads(self.request("/api/run?id=tampered")[2])
        self.assertIsNone(result["packet"])
        self.assertEqual(result["metadata"]["saved_validation"]["status"], "valid")
        self.assertEqual(result["metadata"]["validation"]["status"], "invalid")
        self.assertTrue(any("excerpt does not match" in error for error in result["metadata"]["validation"]["errors"]))
        self.assertIsNone(json.loads(self.request("/api/runs")[2])["default_run_id"])

    def test_changed_code_invalidates_saved_output_now(self):
        self.save_run("source-changed")
        (self.project / "app/service.py").write_text("def create_schedule(payload): return None\n")
        result = json.loads(self.request("/api/run?id=source-changed")[2])
        self.assertIsNone(result["packet"])
        self.assertTrue(any("differs from the captured evidence" in error for error in result["metadata"]["validation"]["errors"]))
        self.assertIsNone(json.loads(self.request("/api/runs")[2])["default_run_id"])

    def test_failed_or_timeout_run_never_displays_even_mechanically_valid_packet(self):
        directory, _ = self.save_run("timed-out")
        metadata = json.loads((directory / "metadata.json").read_text())
        for status in ("failed", "timeout", "partial", "unavailable"):
            metadata["status"] = status
            (directory / "metadata.json").write_text(json.dumps(metadata))
            result = json.loads(self.request("/api/run?id=timed-out")[2])
            self.assertIsNone(result["packet"])
            self.assertEqual(result["metadata"]["validation"]["status"], "valid")
            self.assertFalse(result["packet_available"])
            self.assertEqual(json.loads(self.request("/api/runs")[2])["runs"][0]["metadata"]["status"], status)
            self.assertIsNone(json.loads(self.request("/api/runs")[2])["default_run_id"])

    def test_null_failed_packet_remains_visible_as_failed_run(self):
        directory, _ = self.save_run("no-packet", valid=False)
        (directory / "packet.json").write_text("null")
        result = json.loads(self.request("/api/runs")[2])
        self.assertEqual(len(result["runs"]), 1)
        self.assertEqual(result["runs"][0]["metadata"]["status"], "failed")
        self.assertFalse(result["runs"][0]["packet_available"])

    def test_evidence_cannot_redirect_reads_outside_practice_repositories(self):
        directory, _ = self.save_run("redirected")
        evidence = json.loads((directory / "evidence.json").read_text())
        evidence["repo_root"] = str(self.project.parent)
        (directory / "evidence.json").write_text(json.dumps(evidence))
        result = json.loads(self.request("/api/run?id=redirected")[2])
        self.assertIsNone(result["packet"])
        self.assertIn("outside the permitted", result["metadata"]["validation"]["errors"][0])

    def test_during_run_source_changes_block_even_valid_packets(self):
        directory, _ = self.save_run("changed-during-run")
        metadata = json.loads((directory / "metadata.json").read_text())
        metadata["sources_unchanged"] = False
        (directory / "metadata.json").write_text(json.dumps(metadata))
        result = json.loads(self.request("/api/run?id=changed-during-run")[2])
        self.assertIsNone(result["packet"])
        self.assertEqual(result["metadata"]["validation"]["status"], "valid")
        self.assertIn("changed during", result["error"])

    def test_symlinked_artifact_root_is_rejected(self):
        linked = self.root.parent / "linked"
        linked.symlink_to(self.root, target_is_directory=True)
        with patch("demo_web.ARTIFACT_ROOT", linked):
            self.assertEqual(self.request("/api/runs")[0], 400)

    def test_search_passes_query_and_mode_without_silent_fallback(self):
        calls = []
        def search(query, *, mode, top_k):
            calls.append((query, mode, top_k))
            return {"status": "unavailable", "mode": mode, "results": [], "reason": "No embeddings configured."}
        with patch.dict("sys.modules", {"retriever": types.SimpleNamespace(search_knowledge=search)}):
            status, _, body = self.request("/api/search?q=Pro%20controller&mode=semantic")
        self.assertEqual(status, 200)
        self.assertEqual(calls, [("Pro controller", "semantic", 6)])
        self.assertEqual(json.loads(body)["status"], "unavailable")

    def test_exact_ticket_fetch_is_distinct_from_search(self):
        calls = []
        def get_ticket(ticket_id):
            calls.append(ticket_id)
            return {"status": "ok", "id": ticket_id, "content": "Exact source record"}
        with patch.dict("sys.modules", {"retriever": types.SimpleNamespace(get_ticket=get_ticket)}):
            status, _, body = self.request("/api/ticket?id=AG-1423")
        self.assertEqual(status, 200)
        self.assertEqual(calls, ["AG-1423"])
        self.assertEqual(json.loads(body)["content"], "Exact source record")

    def test_invalid_queries_do_not_invoke_retrieval(self):
        for path in ("/api/search", "/api/search?q=&mode=bm25", "/api/search?q=zones&mode=unknown", "/api/search?q=a&q=b", "/api/ticket?id=", "/api/run", "/api/run?id=a&id=b", "/api/runs?path=../"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 400)

    def test_read_only_and_no_arbitrary_file_access(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertEqual(self.request("/api/run?id=saved", method=method)[0], 405)
        for path in ("/static/../demo_web.py", "/demo_web.py", "/api/write", "/api/report"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_errors_do_not_expose_internal_paths(self):
        with patch("demo_web.list_runs", side_effect=RuntimeError("secret internal path /private/demo-secret")):
            status, _, body = self.request("/api/runs")
        self.assertEqual(status, 503)
        self.assertNotIn(b"demo-secret", body)


if __name__ == "__main__":
    unittest.main()
