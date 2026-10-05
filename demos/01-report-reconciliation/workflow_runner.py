"""Background driver for the engineering workflow: one LangGraph thread per run.

Mirrors live_runner.Run: display events with a cursor, explicit cancellation and a
saved run record. The graph pauses at interrupts; respond() resumes it with the
developer's answer.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import threading
import time
import uuid

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import agent
from catalog import ROOT
from claude_session import Cancelled
import engineering_workflow as workflow
import sandbox

ACTIONS = {"questions": {"answer"}, "review": {"approve", "revise"}}


def headline(result):
    """The numbers the with/without-context comparison card shows for one finished run."""
    summary, grading = result.get("summary") or {}, result.get("grading") or {}
    tests, citations = summary.get("tests") or {}, summary.get("citations") or {}
    return {"context": result.get("context", True), "outcome": result.get("outcome"), "status": result.get("status"),
            "hidden_passed": grading.get("hidden_passed"), "hidden_total": grading.get("hidden_total"),
            "tests_passed": (tests.get("total") or 0) - (tests.get("failed") or 0) if tests else None, "tests_total": tests.get("total"),
            "decisions": len(summary.get("decisions", [])), "assumptions": len(summary.get("assumptions", [])),
            "requirements": len(summary.get("trace", [])), "quotes_verified": citations.get("verified"), "quotes_checkable": citations.get("checkable"),
            "rounds": summary.get("rounds_used"), "model_seconds": summary.get("model_seconds"), "cost_usd": result.get("spent_usd"),
            "pr": bool((result.get("git") or {}).get("pr"))}


class WorkflowRun:
    def __init__(self, developer_note="", *, model=workflow.MODEL, repo=None, context=True, settings=None, preflight=None):
        self.workflow = getattr(self, "workflow", workflow)
        self.actions = getattr(self, "actions", ACTIONS)
        self.id = uuid.uuid4().hex
        self.case_id = self.workflow.CASE_ID
        self.developer_note = developer_note.strip()
        self.model = model
        self.lock = threading.RLock()  # re-entrant: waiting and finishing emit events while holding it
        self.events = []
        self.status = "running"
        self.pending = None
        self.result = None
        self.started = time.monotonic()
        self.recorded_at = datetime.now(timezone.utc).isoformat()
        self.directory = ROOT / "artifacts" / "live" / "workflows" / self.id
        self.settings = settings or self.workflow.Settings(record_dir=self.directory, model=model, repo=repo, context=context,
                                                      remote=sandbox.remote_url(repo) if repo else None)
        self.context = self.settings.context
        self.cancel = self.settings.cancel
        self.preflight = preflight or (lambda: agent.preflight(model))
        self.graph = self.workflow.build_graph(InMemorySaver())
        self.config = {"configurable": {"thread_id": self.id}}
        self.worker = None

    def emit(self, kind, **data):
        with self.lock:
            self.events.append({"index": len(self.events), "kind": kind,
                                "seconds": round(time.monotonic() - self.started, 2), **data})

    def snapshot(self, after=0):
        with self.lock:
            return {"id": self.id, "case_id": self.case_id, "status": self.status, "model": self.model, "context": self.context,
                    "developer_note": self.developer_note, "recorded_at": self.recorded_at,
                    "elapsed_seconds": round(time.monotonic() - self.started, 2) if self.result is None else self.result["elapsed_seconds"],
                    "events": self.events[after:], "cursor": len(self.events), "pending": self.pending, "result": self.result}

    def start(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        notes = [{"stage": "intake", "text": self.developer_note}] if self.developer_note else []
        self._launch({"developer_notes": notes})

    def respond(self, interrupt_id, response):
        with self.lock:
            pending = self.pending
            if self.status != "waiting_for_developer" or not pending or pending["id"] != interrupt_id:
                raise ValueError("This workflow is not waiting for that answer.")
            if response.get("action") not in self.actions[pending["payload"]["kind"]]:
                raise ValueError("That action does not answer this question.")
            if pending["payload"]["kind"] == "migration_decision" and response.get("choice") not in {item["id"] for item in pending["payload"]["options"]}:
                raise ValueError("Choose one of the available next actions; release overrides are not supported.")
            if response.get("action") == "revise" and not (response.get("message") or "").strip():
                raise ValueError("Write an instruction before sending the work back.")
            self.status, self.pending = "running", None
        self.emit("resumed", response=response)
        self._launch(Command(resume=response))

    def stop(self):
        self.cancel.set()
        with self.lock:
            waiting = self.status == "waiting_for_developer"
            if waiting:
                self.status = "stopping"
        if waiting:
            self._finish("cancelled", "Stopped by the presenter while waiting for a decision.")

    def _launch(self, value):
        self.worker = threading.Thread(target=self._drive, args=(value,), daemon=False)
        self.worker.start()

    def _drive(self, value):
        status, message = "failed", None
        try:
            if self.cancel.is_set():
                raise Cancelled()
            if not isinstance(value, Command):
                self.emit("status", text="Checking Claude Code authentication…")
                client = self.preflight()
                if not client.get("authenticated"):
                    status = "blocked"
                    raise RuntimeError("Claude Code is not signed in. Run claude auth login in your terminal, then start a new workflow.")
            if self.cancel.is_set():
                raise Cancelled()
            for mode, chunk in self.graph.stream(value, self.config, context=self.settings, stream_mode=["updates", "custom"]):
                if self.cancel.is_set():
                    raise Cancelled()
                if mode == "custom" and isinstance(chunk, dict) and isinstance(chunk.get("kind"), str):
                    self.emit(**chunk)
            if self.cancel.is_set():
                raise Cancelled()
            state = self.graph.get_state(self.config)
            if state.interrupts:
                item = state.interrupts[0]
                with self.lock:
                    # Publishing the pause and saving happen together, so a stop cannot interleave.
                    if self.cancel.is_set():
                        raise Cancelled()
                    self.emit("waiting", interrupt_id=item.id, payload=item.value)
                    self.pending, self.status = {"id": item.id, "payload": item.value}, "waiting_for_developer"
                    self._save(state.values)
                return
            status = "completed"
        except Cancelled:
            status, message = "cancelled", "Stopped by the presenter."
        except workflow.Stopped as error:
            status, message = "stopped", str(error)
        except Exception as error:
            message = str(error) or type(error).__name__
        self._finish(status, message)

    def _values(self):
        try:
            return self.graph.get_state(self.config).values
        except Exception:
            return {}

    def _save(self, values, result=None):
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.lock:
            events = list(self.events)
        (self.directory / "events.json").write_text(json.dumps(events, indent=2) + "\n")
        if result is not None:
            (self.directory / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    def _finish(self, status, message=None):
        with self.lock:
            self._finish_locked(status, message)

    def _finish_locked(self, status, message):
        values = dict(self._values())
        if not values.get("metrics"):
            values["metrics"] = [event["metric"] for event in self.events if event.get("metric")]
        if message:
            self.emit("error", text=message)
        self.emit("finished", status=status, outcome=values.get("outcome"))
        result = {"id": self.id, "case_id": self.case_id, "status": status, "outcome": values.get("outcome"), "context": self.context,
                  "recorded_at": self.recorded_at, "model": self.model, "developer_note": self.developer_note,
                  "elapsed_seconds": round(time.monotonic() - self.started, 3), "spent_usd": self.workflow.spent(values),
                  "error": message, "summary": values.get("summary"), "grading": values.get("grading"),
                  "rounds": values.get("rounds", []), "metrics": values.get("metrics", []),
                  "decisions": values.get("decisions", []), "developer_notes": values.get("developer_notes", []),
                  "diff": (values.get("patch") or {}).get("diff", ""),
                  "git": {key: value for key, value in (values.get("git") or {}).items() if key != "pushed"},
                  "applied": False, "artifact_directory": str(self.directory)}
        result["headline"] = self.headline(result) if hasattr(self, "headline") else headline(result)
        if self.case_id == "DH-501":
            result["provenance"] = "live_model_assessment_with_executed_synthetic_replays"
            result["partial_evidence"] = {key: values.get(key) for key in ("ci", "diff", "replay", "analysis", "grounding", "gate", "input_hashes") if key in values}
        if values.get("workspace"):
            # The clone lives in its own temporary parent directory; remove both.
            shutil.rmtree(Path(values["workspace"]).parent, ignore_errors=True)
        self._save(values, result)
        with self.lock:
            self.result, self.status, self.pending = result, status, None


def migration_headline(result):
    import migration_release
    summary, grading = result.get("summary") or {}, result.get("grading") or {}
    grounding, gate = summary.get("grounding") or {}, summary.get("gate") or {}
    mapped = {migration_release._identity(item) for item in (summary.get("analysis") or {}).get("dependents", [])}
    verified_obligations = {(item.get("dependent"), item.get("source_id"), item.get("quote"))
                            for item in grounding.get("results", [])
                            if item.get("status") == "verified" and item.get("kind") in {"obligation", "obligations"}}
    return {"context": result.get("context", True), "status": result.get("status"), "outcome": result.get("outcome"),
            "hidden_passed": grading.get("hidden_passed"), "hidden_total": grading.get("hidden_total"),
            "quotes_verified": grounding.get("verified"), "quotes_checkable": grounding.get("checkable"),
            "gate": gate.get("decision"), "dependents": len(mapped - {None}),
            "obligations": len(verified_obligations),
            "owners": len({owner for item in gate.get("dependents", []) for owner in item.get("owners", [])}),
            "earliest_full_removal": gate.get("earliest_full_removal"),
            "earliest_conditional_full_removal": gate.get("earliest_conditional_full_removal"),
            "model_seconds": summary.get("model_seconds"), "cost_usd": result.get("spent_usd"),
            "decisions": len(result.get("decisions", [])), "sent": False}


class MigrationRun(WorkflowRun):
    """Demo 3 reuses Demo 2's checkpoint, event and cancellation driver; no Git remote."""
    actions = {"migration_decision": {"decide"}}
    headline = staticmethod(migration_headline)

    def __init__(self, developer_note="", *, model=workflow.MODEL, context=True, settings=None, preflight=None):
        import migration_workflow
        self.workflow = migration_workflow
        super().__init__(developer_note, model=model, context=context, settings=settings, preflight=preflight)
