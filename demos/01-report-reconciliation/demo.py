"""Run the reproducible demo without a model, or explicitly start a real agent run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

from catalog import ROOT, cases, documents, get_case, get_document, snapshot_hashes, digest
from reconcile import reconcile
from evaluation import run_controls, expectations


def money(cents):
    if cents is None:
        return "Undetermined"
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}${whole:,}.{fraction:02d}"


def markdown(report):
    lines = [f"# {report['case_id']}: {cases()[report['case_id']]['title']}", "",
             f"**Decision:** {report['decision'].replace('_', ' ')}", "",
             "| Current report | Customer claim | Approved-rule result |",
             "| --- | --- | --- |",
             f"| {money(report['reported_total_cents'])} | {money(report['customer_claim_cents'])} | {money(report['expected_total_cents'])} |", ""]
    if report["ledger"]:
        lines += ["| Row | Raw | Current contribution | Correct contribution | Rule sources |",
                  "| --- | ---: | ---: | ---: | --- |"]
        for row in report["ledger"]:
            lines.append(f"| {row['row_id']} | {money(row['raw_amount_cents'])} | {money(row['observed_cents'])} | {money(row['expected_cents'])} | {row['policy_source']}; {row['feed_source']} |")
        lines.append("")
    row_status = ', '.join(report['problem_rows']) or ('none' if report['ledger'] else 'not established')
    lines += [f"Problem rows: {row_status}.", ""]
    lines += [message + "\n" for message in report["messages"]]
    lines += ["**Next action:** " + report["next_action"], "", "## Captured sources", ""]
    for source_id, snapshot in report["source_snapshots"].items():
        doc = snapshot["document"]
        lines += [f"### {source_id} — {doc['title']}", "",
                  f"{doc['system']} · {doc['status']} · owner: {doc['owner']} · version: {doc['version']}", "",
                  f"Effective: {doc['effective_from']} through {doc['effective_to'] or 'no specified end'} (end exclusive).", "",
                  doc["body"], "", f"SHA256: `{snapshot['sha256']}`", ""]
    lines += ["Synthetic fixtures. This is an executed deterministic workflow, not an agent transcript. Human review pending.", ""]
    return "\n".join(lines).rstrip()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def reproduce():
    runs = {}
    for implementation in ("seed", "naive", "reference"):
        process = subprocess.run([sys.executable, "-m", "controls.reported_case", implementation],
                                 cwd=ROOT, text=True, capture_output=True, timeout=10)
        runs[implementation] = {"exit_code": process.returncode, "stdout": process.stdout,
                                "stderr": process.stderr.replace(str(ROOT), "<demo>")}
    return {"provenance": "actual_regression_execution_against_prepared_implementations", "agent_runs": 0,
            "snapshot_hashes": snapshot_hashes(),
            "runs": runs, "passed": runs["seed"]["exit_code"] == 1 and runs["naive"]["exit_code"] == 1 and
            all("AssertionError: signed reversals must stay positive" in runs[name]["stderr"] for name in ("seed", "naive")) and
            runs["reference"]["exit_code"] == 0}


def benchmark(name, repeats=1, seed=20261004, timeout=180, budget=0.5, plan_only=False):
    import agent
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", name):
        raise ValueError("Use a new simple run name (letters, numbers, underscores or hyphens)")
    schedule = agent.plan(repeats, seed)
    destination = ROOT / "artifacts" / name
    destination.mkdir(parents=True, exist_ok=False)
    write_json(destination / "plan.json", schedule)
    runs = []
    result = {"status": "planned", "plan": schedule, "runs": runs, "model_requests_attempted": 0}
    if not plan_only:
        client = agent.preflight()
        result["client"] = client
        if not client["authenticated"]:
            result["status"] = "blocked"
            result["reason"] = "Claude Code is not authenticated. No model request was made."
        else:
            result["status"] = "completed"
            for index, trial in enumerate(schedule["trials"], 1):
                if (snapshot_hashes() != schedule["snapshot_hashes"] or
                        digest(expectations()) != schedule["oracle_sha256"] or
                        agent.protocol_hash() != schedule["protocol_sha256"]):
                    result["status"] = "aborted"
                    result["reason"] = "Frozen evidence, oracle or runner changed. Preserve this run and start a new comparison."
                    break
                print(f"{index}/{len(schedule['trials'])}: {trial['case_id']} {trial['condition']}", flush=True)
                run = agent.run_agent(trial["case_id"], trial["condition"], timeout=timeout, budget=budget, client=client)
                run["repeat"] = trial["repeat"]
                runs.append(run)
                result["model_requests_attempted"] += int(run["agent_run"])
                write_json(destination / f"trial-{index:03d}.json", run)
                # Persist every attempt before continuing; interrupted runs keep their evidence.
                write_json(destination / "results.json", {**result, "status": "running", "summary": agent.summarize(runs)})
    result["summary"] = agent.summarize(runs)
    write_json(destination / "results.json", result)
    print(json.dumps({"directory": str(destination), "status": result["status"], "summary": result["summary"]}, indent=2))
    return 0 if result["status"] in {"completed", "planned"} else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("case", "run"):
        item = sub.add_parser(name)
        item.add_argument("case_id", choices=sorted(cases()))
        item.add_argument("--json", action="store_true")
        item.add_argument("--output", type=Path)
    doc = sub.add_parser("document")
    doc.add_argument("document_id", choices=sorted(documents()))
    controls = sub.add_parser("controls")
    controls.add_argument("--output", type=Path)
    sub.add_parser("preflight")
    regression = sub.add_parser("reproduce")
    regression.add_argument("--output", type=Path)
    present = sub.add_parser("present")
    present.add_argument("--output", type=Path, default=ROOT / "artifacts/presentation.html")
    live = sub.add_parser("live", help="Serve the live model investigation UI on localhost")
    live.add_argument("--port", type=int, default=8768)
    run = sub.add_parser("agent")
    run.add_argument("case_id", choices=sorted(cases()))
    run.add_argument("--context", choices=("provided", "retrieval", "workflow"), required=True)
    run.add_argument("--timeout", type=float, default=180)
    run.add_argument("--budget", type=float, default=0.5)
    comparison = sub.add_parser("benchmark")
    comparison.add_argument("--name", required=True)
    comparison.add_argument("--repeats", type=int, default=1)
    comparison.add_argument("--seed", type=int, default=20261004)
    comparison.add_argument("--timeout", type=float, default=180)
    comparison.add_argument("--budget", type=float, default=0.5)
    comparison.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    if args.command in {"case", "run"}:
        data = get_case(args.case_id) if args.command == "case" else reconcile(args.case_id)["report"]
        output = json.dumps(data, indent=2) if args.json or args.command == "case" else markdown(data)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output + "\n")
        print(output)
    elif args.command == "document":
        print(json.dumps(get_document(args.document_id), indent=2))
    elif args.command == "controls":
        result = run_controls()
        if args.output:
            write_json(args.output, result)
        print(json.dumps({"summary": result["summary"], "interpretation": result["interpretation"]}, indent=2))
        return int(result["summary"]["policy_workflow"]["complete_cases"] != len(cases()))
    elif args.command == "live":
        from live_server import serve
        serve(args.port)
    elif args.command == "present":
        from presentation import render
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render())
        print(args.output.resolve())
    elif args.command == "reproduce":
        result = reproduce()
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, indent=2))
        return int(not result["passed"])
    elif args.command == "preflight":
        import agent
        print(json.dumps({"recorded_at": datetime.now(timezone.utc).isoformat(), "claude": agent.preflight(),
                          "snapshot_hashes": snapshot_hashes(), "offline_workflow_available": True}, indent=2))
    elif args.command == "agent":
        import agent
        result = agent.run_agent(args.case_id, args.context, timeout=args.timeout, budget=args.budget)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "completed" and result["acceptance"]["passed"] else 3
    elif args.command == "benchmark":
        return benchmark(args.name, args.repeats, args.seed, args.timeout, args.budget, args.plan_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
