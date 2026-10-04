"""Exercise disposable preparation and the actual patch-review boundary locally."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import prepare_live


PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project_copy(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(PROJECT / "app", project / "app", ignore=shutil.ignore_patterns("__pycache__"))
    (project / "scripts").mkdir()
    (project / "tests").mkdir()
    for name in ("check_regression.py", "review_live.py"):
        shutil.copy2(PROJECT / "scripts" / name, project / "scripts" / name)
    shutil.copy2(PROJECT / "tests/test_app.py", project / "tests/test_app.py")
    shutil.copy2(PROJECT / "mcp_server.py", project / "mcp_server.py")
    monkeypatch.setattr(prepare_live, "ROOT", project)
    return project


def review(project, workspace):
    # The legacy patch reviewer receives tests only in this local fixture. The
    # onramping repository itself contains no prepared grader or reference fix.
    tests = workspace / "tests"
    if not tests.exists():
        tests.mkdir()
        shutil.copy2(project / "tests/test_app.py", tests / "test_app.py")
    return subprocess.run(
        [sys.executable, str(project / "scripts/review_live.py"), str(workspace)],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def patch_limit(workspace, argument):
    service = workspace / "app/schedule_service.py"
    service.write_text(
        service.read_text().replace("self._configuration_service.resolve_maximum_zones()", f"self._configuration_service.resolve_maximum_zones({argument})")
    )


def test_prepare_omits_reference_and_preserves_prior_workspace(project_copy):
    original = (project_copy / "app/schedule_service.py").read_text()
    workspace = prepare_live.prepare("first")
    import json
    config = json.loads((workspace / ".mcp.json").read_text())
    assert config["mcpServers"]["engineering-knowledge"]["command"] == str(Path(sys.executable).absolute())
    assert not (workspace / "app/reference_validator.py").exists()
    assert not (workspace / "scripts/check_regression.py").exists()
    assert (workspace / "app/schedule_service.py").read_text() == original
    sentinel = workspace / "notes.txt"
    sentinel.write_text("Keep this previous investigation.")
    with pytest.raises(FileExistsError):
        prepare_live.prepare("first")
    assert sentinel.read_text() == "Keep this previous investigation."
    assert (project_copy / "app/schedule_service.py").read_text() == original


@pytest.mark.parametrize("name", ["../escape", "nested/name", "", "x" * 49])
def test_prepare_rejects_invalid_names_without_creating_workspace(project_copy, name):
    with pytest.raises(ValueError):
        prepare_live.prepare(name)
    assert not (project_copy / "demo-workspaces").exists()


def test_review_rejects_baseline_and_accepts_actual_model_specific_source_patch(project_copy):
    original = (project_copy / "app/schedule_service.py").read_text()
    workspace = prepare_live.prepare("correct")
    baseline = review(project_copy, workspace)
    assert baseline.returncode == 1
    assert "FAIL PRO accepts 21 zones" in baseline.stdout
    patch_limit(workspace, "schedule.controller_type")
    corrected = review(project_copy, workspace)
    assert corrected.returncode == 0, corrected.stdout + corrected.stderr
    assert "22/22 passed" in corrected.stdout
    assert "baseline/app/schedule_service.py" in corrected.stdout
    assert (project_copy / "app/schedule_service.py").read_text() == original


def test_review_rejects_global_limit_even_when_practice_tests_and_evaluator_are_weakened(project_copy):
    workspace = prepare_live.prepare("wrong")
    patch_limit(workspace, '"PRO"')
    (workspace / "tests").mkdir(exist_ok=True)
    (workspace / "tests/test_app.py").write_text("def test_always_passes():\n    assert True\n")
    (workspace / "scripts").mkdir(exist_ok=True)
    (workspace / "scripts/check_regression.py").write_text("raise SystemExit(0)\n")
    wrong = review(project_copy, workspace)
    assert wrong.returncode == 1
    assert "FAIL LEGACY rejects 21 zones" in wrong.stdout


def test_review_rejects_workspace_outside_prepared_directory(project_copy, tmp_path):
    outside = tmp_path / "outside"
    (outside / "app").mkdir(parents=True)
    rejected = review(project_copy, outside)
    assert rejected.returncode != 0
    assert "direct child" in rejected.stderr
