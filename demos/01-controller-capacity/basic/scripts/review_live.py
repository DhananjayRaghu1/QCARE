"""Show the actual practice diff and run checks. Does not merge or deploy."""

import argparse
import difflib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", help="Path to a workspace created by prepare_live.py")
    args = parser.parse_args()
    target = Path(args.workspace).resolve()
    if target.parent != (ROOT / "demo-workspaces").resolve() or not (target / "app").is_dir():
        parser.error("Select a direct child of this project's demo-workspaces folder.")
    print("ACTUAL LOCAL WORKSPACE DIFF; human review required", flush=True)
    baseline_files = {p.relative_to(ROOT) for p in (ROOT / "app").glob("*.py") if p.name != "reference_validator.py"}
    baseline_files.add(Path("tests/test_app.py"))
    target_files = {p.relative_to(target) for directory in ("app", "tests") for p in (target / directory).rglob("*.py")}
    changed = []
    for rel in sorted(baseline_files | target_files):
        original = (ROOT / rel).read_text() if rel in baseline_files else ""
        current = (target / rel).read_text() if (target / rel).exists() else ""
        if original != current:
            changed.append(str(rel))
            print("".join(difflib.unified_diff(original.splitlines(True), current.splitlines(True), fromfile=f"baseline/{rel}", tofile=f"practice/{rel}")), flush=True)
    print("Changed files: " + (", ".join(changed) or "none"), flush=True)
    python = sys.executable
    tests = subprocess.run([python, "-m", "pytest", "-q"], cwd=target, check=False)
    # Run a trusted, unchanged evaluator against the practice app in a fresh process.
    evaluator = ROOT / "scripts/check_regression.py"
    code = "import sys; from pathlib import Path; practice, evaluator = sys.argv[1:3]; sys.path.insert(0, practice); source=Path(evaluator).read_text(); source=source.replace('sys.path.insert(0, str(Path(__file__).resolve().parents[1]))', ''); sys.argv=[evaluator]+sys.argv[3:]; exec(compile(source, evaluator, 'exec'), {'__name__':'__main__','__file__':evaluator})"
    checks = subprocess.run([python, "-c", code, str(target), str(evaluator), "--implementation", "baseline"], cwd=target, check=False)
    return 0 if tests.returncode == 0 and checks.returncode == 0 and changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
