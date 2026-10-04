"""State-level checks for the reported regression and independent evaluator."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def workspace(tmp_path, state="seed"):
    destination = tmp_path / state
    shutil.copytree(ROOT / "seed", destination, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    if state != "seed":
        source = "reference_validator.py" if state == "reference" else "unsafe_validator.py"
        shutil.copyfile(ROOT / "controls" / source, destination / "app" / "schedule_validator.py")
    return destination


def checks(path):
    result = subprocess.run([sys.executable, str(ROOT / "acceptance" / "checks.py"),
                             "--workspace", str(path), "--json"], capture_output=True, text=True)
    return result, json.loads(result.stdout)


def pytest_run(path, reported=False):
    if reported:
        shutil.copyfile(ROOT / "controls" / "test_reported_case.py", path / "tests" / "test_reported_case.py")
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                          cwd=path, capture_output=True, text=True)


def file_hashes(path):
    return {str(file.relative_to(path)): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in path.rglob("*") if file.is_file() and file.suffix in {".py", ".json"}}


def test_seed_passes_existing_tests_but_reported_regression_is_red(tmp_path):
    selected = workspace(tmp_path)
    existing = pytest_run(selected)
    assert existing.returncode == 0, existing.stdout + existing.stderr
    reported = pytest_run(selected, reported=True)
    assert reported.returncode == 1
    assert "test_reported_30_zones" in reported.stdout
    assert "AG-1423 still fails" in reported.stdout


@pytest.mark.parametrize("state", ["reference", "unsafe-pro-50"])
def test_both_patches_pass_existing_tests_and_reported_case(tmp_path, state):
    selected = workspace(tmp_path, state)
    result = pytest_run(selected, reported=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_reference_passes_independent_policy_checks(tmp_path):
    selected = workspace(tmp_path, "reference")
    before = file_hashes(selected)
    result, report = checks(selected)
    assert result.returncode == 0, report
    assert report["status"] == "passed" and report["failed"] == 0
    assert report["passed"] >= 30
    assert file_hashes(selected) == before, "Independent checker must not alter application fixtures"


def test_unsafe_patch_is_caught_for_older_firmware(tmp_path):
    selected = workspace(tmp_path, "unsafe-pro-50")
    result, report = checks(selected)
    failures = {item["id"] for item in report["cases"] if item["status"] == "failed"}
    assert result.returncode == 1
    assert failures == {"pro_old_21", "pro_below_boundary_3_1_99"}
    main = next(item for item in report["cases"] if item["id"] == "pro_eligible_30")
    assert main["status"] == "passed"


def test_seed_is_caught_for_eligible_firmware_without_false_old_device_failure(tmp_path):
    result, report = checks(workspace(tmp_path))
    failures = {item["id"] for item in report["cases"] if item["status"] == "failed"}
    assert result.returncode == 1
    assert failures == {"pro_eligible_30", "pro_eligible_50", "pro_boundary_3_2_0", "pro_numeric_3_10_0"}


def test_broken_application_returns_structured_failure(tmp_path):
    selected = workspace(tmp_path)
    (selected / "app" / "api.py").write_text("raise RuntimeError('broken application')\n", encoding="utf-8")
    result, report = checks(selected)
    assert result.returncode == 1
    assert report["status"] == "failed"
    assert report["cases"][0]["id"] == "application_load"
    assert "broken application" in report["cases"][0]["detail"]


def test_mutated_registry_cannot_silently_change_ticket_identity(tmp_path):
    selected = workspace(tmp_path, "reference")
    path = selected / "app" / "devices.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    fixture["DEV-102"]["firmware"] = "3.4.0"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    result, report = checks(selected)
    assert result.returncode == 1
    failures = {item["id"] for item in report["cases"] if item["status"] == "failed"}
    assert {"registry_fixture", "pro_old_21"} <= failures
