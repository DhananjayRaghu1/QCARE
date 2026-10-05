"""Demo 3 verification, bounded live runs and portable local recordings."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

from catalog import ROOT, digest
from claude_session import Session
import migration_release as release
import migration_workflow as workflow
from workflow_runner import MigrationRun, migration_headline


def prepared_assessment(context=True):
    """Author-prepared extraction for harness verification; never a model output."""
    corpus = release._records()
    dependents = []
    for name, policy in release.POLICIES.items():
        obligations = [{"source_id": policy["obligation"], "quote": corpus[policy["obligation"]]["body"]}] if context else []
        usage = [{"source_id": source, "quote": corpus[source]["body"]} for source in (release.CURRENT_USAGE, "OPS-USAGE-1001")] if context and policy["usage"] else []
        dependents.append({"id": name, "workflow": name, "customer": policy["customer"],
                           "code_path": "app/jobs.py → app/decoder.py" if name != "rollback" else "app/decoder.py",
                           "obligations": obligations, "usage": usage, "owners": policy["owners"] if context else [],
                           "earliest_removal": {"daily_sales": "2026-10-15", "historical_replay": "2026-12-30", "partner_statement": "2026-12-01"}.get(name) if context else None,
                           "conditions": ["Owner sign-off and dated operational verification are required."]})
    return {"summary": "Author-prepared synthetic dependency assessment for deterministic verification.",
            "dependents": dependents, "earliest_full_removal": None,
            "earliest_conditional_full_removal": "2026-12-30" if context else None,
            "missing_evidence": ["Customer migration, archive/backup acceptance and rollback proof." if context else "Approved obligations and current usage are unavailable."],
            "recommendation": "Defer shared removal; investigate only a proven live path."}


def prepared_session(context):
    def session(*args, **kwargs):
        kwargs["emit"]("note", text="Author-prepared assessment for deterministic verification; no model was called.")
        fetched = {source: digest(record) for source, record in release._records().items()} if context else {}
        return Session(output=prepared_assessment(context), fetched=fetched, elapsed_seconds=0)
    return session


def wait_until_paused(run):
    while run.status in {"running", "stopping"}:
        if run.worker:
            run.worker.join(timeout=0.25)
        else:
            time.sleep(0.05)


def complete(run, decision=None):
    run.start()
    wait_until_paused(run)
    if run.status == "waiting_for_developer":
        if decision is None:
            print(json.dumps(run.pending["payload"], indent=2))
            decision = input("Next action (defer / scoped_canary / request_signoff): ").strip()
        run.respond(run.pending["id"], {"action": "decide", "choice": decision})
        wait_until_paused(run)
    return run.result


def verify(output=None, record=False):
    """Run the actual graph and executable jobs twice with a prepared extraction."""
    results = []
    for context in (True, False):
        settings = workflow.Settings(record_dir=ROOT / "artifacts" / "migration-verification" / ("with-context" if context else "no-context"),
                                     context=context, session=prepared_session(context))
        run = MigrationRun("A developer note cannot waive obligations.", settings=settings, preflight=lambda: {"authenticated": True})
        result = complete(run, "defer")
        result["provenance"] = "deterministic_harness_verification_with_author_prepared_assessment"
        result["model"] = None
        result["label"] = "Prepared deterministic rehearsal — no model called."
        run._save({}, result)
        if record:
            record_run(run.id, datetime.now(timezone.utc).strftime("%Y-%m-%d") + ("-prepared-with-context" if context else "-prepared-no-context"))
        results.append(result)
    passed = (all(result["status"] == "completed" and result["summary"]["gate"]["decision"] == "block" for result in results)
              and results[0]["grading"]["hidden_passed"] == 12
              and results[1]["grading"]["hidden_passed"] < 12)
    value = {"provenance": "actual_deterministic_graph_and_job_execution", "model_requests": 0,
             "passed": passed, "runs": results}
    target = output or ROOT / "artifacts/migration-verification/results.json"
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": passed, "output": str(target), "scores": [result.get("grading") for result in results]}, indent=2))
    return 0 if passed else 1


def record_run(run_id, name=None):
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ValueError("Use the 32-character workflow run ID.")
    source = ROOT / "artifacts/live/workflows" / run_id
    result = json.loads((source / "result.json").read_text())
    if result["case_id"] != workflow.CASE_ID:
        raise ValueError("This is not a Demo 3 release-check run.")
    events = json.loads((source / "events.json").read_text())
    name = name or result["recorded_at"][:10] + ("-with-context" if result["context"] else "-no-context")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", name):
        raise ValueError("Use a simple lowercase recording name.")
    workspace = re.compile(r"/[^\s\"'()]*?datahoney-migration-[A-Za-z0-9_-]+(?:/repo)?")

    def clean(value):
        if isinstance(value, str):
            return workspace.sub("<workspace>", value).replace(str(ROOT), "<demo>").replace(str(Path.home()), "~")
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        return value
    prepared = result.get("provenance", "").startswith("deterministic_")
    label = ("Prepared deterministic rehearsal — no model called. Replay uses saved executed fixtures and an authored assessment." if prepared else
             "Recorded live model attempt. Replay shows its saved events; no model is called.")
    card = migration_headline(result)
    value = clean({**result, "format_version": 1, "name": name, "run_id": run_id, "label": label, "events": events,
                   "headline": card, "original_headline": result.get("headline"),
                   "recording_note": "Card counts are derived from saved analysis and verified citation statuses. The original run result and grading are preserved."})
    target = ROOT / "recordings/langgraph-migration" / (name + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError("Recording already exists; choose a new name to preserve earlier attempts.")
    target.write_text(json.dumps(value, indent=2) + "\n")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    offline = commands.add_parser("verify", help="Execute deterministic verification; no model called")
    offline.add_argument("--output", type=Path)
    offline.add_argument("--record", action="store_true", help="Save explicitly prepared offline replay recordings")
    live = commands.add_parser("run", help="One bounded read-only Opus assessment, then your decision")
    live.add_argument("--context", choices=("on", "off"), default="on")
    live.add_argument("--developer-note", default="")
    live.add_argument("--model", default=workflow.MODEL)
    live.add_argument("--decision", choices=("defer", "scoped_canary", "request_signoff"), help="Scripted presenter choice for a labeled rehearsal")
    record = commands.add_parser("record", help="Record any finished attempt, including failures")
    record.add_argument("run_id")
    record.add_argument("--name")
    args = parser.parse_args()
    if args.command == "verify":
        return verify(args.output, args.record)
    if args.command == "record":
        print(record_run(args.run_id, args.name))
        return 0
    run = MigrationRun(args.developer_note, model=args.model, context=args.context == "on")
    result = complete(run, args.decision)
    print(json.dumps({"id": run.id, "status": run.status, "error": result.get("error"),
                      "headline": result.get("headline"), "artifact_directory": str(run.directory)}, indent=2))
    return 0 if run.status == "completed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
