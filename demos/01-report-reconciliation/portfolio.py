"""Three audience demos; author notes and reference answers stay out of model inputs."""
from pathlib import Path
import difflib
import json
import subprocess
import sys
import tempfile

from catalog import ROOT, get_case

BASE = ROOT / "portfolio"
DEFINITIONS = {
    "report": dict(id="report", case_id="DH-301", number="01", title="Investigate a customer problem", subtitle="Which sales total can we defend?", benefit="Resolve uncertainty before changing code.", sources=["REPORT-STD-SEP","FEED-ATLAS-1","FEED-ATLAS-2","DH-188"], outcome="An evidence-backed diagnosis and next action", editable=False),
    "export": dict(id="export", case_id="DH-401", number="02", title="Build the right feature", subtitle="Turn a short request into a correct customer export.", benefit="Recover requirements the feature request leaves out.", sources=["EXPORT-NS-1","FIN-SETTLEMENT-2","DH-411","EXPORT-NS-2-DRAFT"], outcome="A reviewable code patch and independent acceptance results", editable=True),
    "migration": dict(id="migration", case_id="DH-501", number="03", title="Assess a change before it breaks something", subtitle="Can the old ATLAS format safely be retired?", benefit="Connect code dependencies to customer and operational obligations.", sources=["MIG-OVERVIEW","DH-510","OPS-REPLAY","CONTRACT-CEDAR","OPS-USAGE-1001","RUNBOOK-ROLLBACK"], outcome="An impact assessment with owners, blockers and rollout gates", editable=False),
}
CASE_DEMOS = {value["case_id"]: key for key,value in DEFINITIONS.items()}
PROMPTS = {
    "export": "Read issue.json and the available repository files. Establish the requirements from available evidence. If essential requirements are missing, state the precise blocking questions instead of guessing. Otherwise implement the requested feature in app/exporter.py and add tests under tests/. Preserve existing behavior for other customers. Do not alter input data, documents, issue.json or the supplied baseline tests. Run relevant tests and explain the changes, evidence and limitations. Use only this working directory.",
    "migration": "Read issue.json. Inspect the repository and available evidence, run relevant checks, and recommend whether the proposed removal can proceed. Identify impacted workflows and customers, the evidence for each dependency, missing or stale evidence, owners, and concrete rollout or deferral gates. Cite source IDs when available. Do not modify files. Use only this working directory.",
}

def read_json(path):
    return json.loads(path.read_text())


def documents():
    return {doc["id"]: doc for name in ("export","migration") for doc in read_json(BASE/name/"documents.json")}


def inputs(case_id, with_documents):
    name = CASE_DEMOS[case_id]
    files = {}
    for relative in ("issue.json", "sample.json", "app/exporter.py", "app/decoder.py", "app/jobs.py", "tests/test_existing.py"):
        path = BASE/name/relative
        if path.exists(): files[relative] = path.read_text()
    files["app/__init__.py"] = ""
    files["README.md"] = "# Customer workflow sample\n\nRead issue.json. Python uses the standard library. Run existing checks with python3 -m unittest discover -s tests -v. Existing tests cover current behavior, not every business requirement.\n"
    if with_documents:
        for doc in read_json(BASE/name/"documents.json"):
            metadata = "\n".join(f"{key}: {doc[key]}" for key in ("system","status","owner","scope","effective_from","effective_to","version"))
            files[f"business-docs/{doc['id']}.md"] = f"# {doc['id']}: {doc['title']}\n\n{metadata}\n\n{doc['body']}\n"
    return files


def public_demo(name):
    data = dict(DEFINITIONS[name])
    if name == "report":
        data["request"] = get_case("DH-301")["case"]["ticket"]
    else:
        data["request"] = read_json(BASE/name/"issue.json")["request"]
        data["prompt"] = PROMPTS[name]
        data["files"] = inputs(data["case_id"], False)
        data["documents"] = read_json(BASE/name/"documents.json")
    return data


def acceptance(directory):
    try:
        result = subprocess.run([sys.executable, str(BASE/"acceptance/export_checks.py"), "-v"], cwd=directory,
                                capture_output=True, text=True, timeout=20)
        baseline = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=directory,
                                  capture_output=True, text=True, timeout=20)
        return {"passed": result.returncode == 0 and baseline.returncode == 0, "exit_code": result.returncode,
                "independent_passed": result.returncode == 0, "repository_passed": baseline.returncode == 0,
                "output": ("INDEPENDENT ACCEPTANCE CHECKS\n"+result.stdout+result.stderr+"\nREPOSITORY TESTS\n"+baseline.stdout+baseline.stderr)[-24000:],
                "label": "Independent and repository checks (after the model finishes)"}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"passed": False, "output": str(error), "label": "Independent checks could not finish"}


def reference_export():
    # Execute trusted prepared code in a fresh workspace, with external checks.
    with tempfile.TemporaryDirectory(prefix="datahoney-reference-") as temp:
        path = Path(temp)
        for relative, content in inputs("DH-401",False).items():
            target=path/relative; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(content)
        seed=(path/"app/exporter.py").read_text()
        reference=(BASE/"export/reference.py").read_text()
        (path/"app/exporter.py").write_text(reference)
        checked=acceptance(path)
        output=subprocess.run([sys.executable,"-c","import json; from app.exporter import export_csv; print(export_csv(json.load(open('sample.json')),'NORTHSTAR','2026-09'),end='')"],cwd=path,capture_output=True,text=True,timeout=10)
        return {"label":"Prepared example — not a model run", "summary":"September includes a late-September local settlement and a refund. It excludes the August local settlement, the pending invoice and another customer.",
                "csv":output.stdout,"net_cents":14400,"checks":checked,
                "patch":"".join(difflib.unified_diff(seed.splitlines(True),reference.splitlines(True),fromfile="a/app/exporter.py",tofile="b/app/exporter.py")),
                "steps":[
                    {"text":"Use the New York settlement month. N-101 is August locally; N-102 is September locally even though its UTC timestamp is October 1.","sources":["EXPORT-NS-1"]},
                    {"text":"N-102 contributes $200 − $6 = $194. N-103 contributes −$50; the processing fee is not returned. September net settlement is $144.","sources":["FIN-SETTLEMENT-2"]},
                    {"text":"Exclude pending records before reading their absent settlement date. Preserve other customers' invoice export and standard CSV quoting.","sources":["EXPORT-NS-1","DH-411"]},
                    {"text":"Do not apply the later draft's UTC month or fee-refund proposal. Review the patch and acceptance evidence before merging.","sources":["EXPORT-NS-2-DRAFT","DH-411"]}]}


def reference_migration():
    return {"label":"Prepared example — not a model run", "summary":"Defer shared v1 decoder removal on October 15. The daily-sales migration does not clear partner delivery, historical replay or rollback dependencies.",
        "matrix":[
            {"workflow":"daily_sales · NORTHSTAR","status":"Candidate for a scoped canary; refresh evidence","code":"app/jobs.py → app/decoder.py","why":"Delivery ticket covers live ingest only. October 1 usage is a dated snapshot, not current proof.","owner":"Data Integrations","sources":["DH-510","OPS-USAGE-1001"]},
            {"workflow":"historical_replay · archived accounts","status":"Blocked","code":"app/jobs.py → app/decoder.py","why":"90-day replay includes v1 archives; conversion has not been verified.","owner":"Data Operations","sources":["OPS-REPLAY"]},
            {"workflow":"partner_statement · CEDAR","status":"Blocked","code":"app/jobs.py → app/decoder.py","why":"Signed agreement requires v1 through November 30; obtain an approved amendment or wait and verify migration.","owner":"Partner Engineering + Customer Success","sources":["CONTRACT-CEDAR","OPS-USAGE-1001"]}],
        "steps":[
            {"text":"Confirm each code consumer and owner; a call graph shows capability, not current traffic or customer consent.","sources":["MIG-OVERVIEW"]},
            {"text":"Refresh usage per workflow and account. Obtain Cedar's approved migration window. Prove archived exports and backups remain replayable.","sources":["OPS-USAGE-1001","CONTRACT-CEDAR","OPS-REPLAY"]},
            {"text":"Test both sign conventions and rehearse rollback. Canary only the cleared live path; retain the shared decoder until every dependent is cleared.","sources":["RUNBOOK-ROLLBACK"]}],
        "checks":["Repo test: a v1 positive return contributes +5000; it cannot be reinterpreted as a v2 refund.","Operational evidence: no conclusion of zero traffic from an old snapshot.","Business approval: a done Jira ticket cannot override a customer agreement.","Release gate: owner sign-off, replay evidence, current telemetry and rollback rehearsal are still needed." ],
        "code_checks": migration_checks()}


def migration_checks():
    results = []
    for remove in (False, True):
        with tempfile.TemporaryDirectory(prefix="datahoney-migration-check-") as temp:
            for relative, content in inputs("DH-501", False).items():
                path = Path(temp)/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            if remove:
                path = Path(temp)/"app/decoder.py"
                path.write_text(path.read_text().replace('    if row["schema_version"] == "1":\n        return row["amount_cents"]\n', ''))
            result = subprocess.run([sys.executable,"-B","-m","unittest","discover","-s","tests","-v"],cwd=temp,capture_output=True,text=True,timeout=10)
            results.append({"variant":"Prepared removal of v1 support" if remove else "Current implementation",
                            "passed":result.returncode == 0,"output":result.stdout+result.stderr})
    return results


def capture_patch(directory, original):
    patches=[]; files={}
    candidates=["app/exporter.py"]+[str(p.relative_to(directory)) for p in (directory/"tests").glob("test_*.py") if str(p.relative_to(directory)) not in original]
    extra_code = {str(p.relative_to(directory)) for p in directory.rglob("*.py")} - set(original) - set(candidates)
    if extra_code:
        raise ValueError("Unsupported extra code files would be missing from the review patch: "+", ".join(sorted(extra_code)))
    for relative in candidates:
        path=directory/relative
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()) or not path.is_file() or path.stat().st_size > 200000:
            raise ValueError("Missing or unsafe generated file: "+relative)
        value=path.read_text(); before=original.get(relative,"")
        if value!=before:
            files[relative]=value
            patches.extend(difflib.unified_diff(before.splitlines(True),value.splitlines(True),fromfile="a/"+relative,tofile="b/"+relative))
    return {"files":files,"diff":"".join(patches)}
