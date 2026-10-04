"""Tool permissions are phase-scoped and reject filesystem escapes."""

from pathlib import Path

import pytest

from guard import MCP_TOOLS, decide


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "practice"
    (root / "app").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "app/service.py").write_text("LIMIT = 20\n")
    (root / "app/devices.json").write_text('{}\n')
    (root / "tests/test_existing.py").write_text("def test_example():\n    assert True\n")
    (root / "tests/test_reported_case.py").write_text("def test_reported():\n    assert True\n")
    (root / "CLAUDE.md").write_text("operator metadata\n")
    return root


def decision(workspace, name, args, phase="investigate", context="tools"):
    return decide({"tool_name": name, "tool_input": args}, workspace, phase, context)["hookSpecificOutput"]


@pytest.mark.parametrize("path", ["app/service.py", "app/devices.json", "tests/test_existing.py"])
def test_investigation_can_read_application_registry_and_seed_tests(workspace, path):
    result = decision(workspace, "Read", {"file_path": path})
    assert result["permissionDecision"] == "allow"
    assert result["updatedInput"]["file_path"] == str((workspace / path).resolve())


@pytest.mark.parametrize("name", ["Write", "Edit", "Bash", "NotebookEdit", "WebFetch", "Agent"])
def test_investigation_forbids_mutation_and_unscoped_tools(workspace, name):
    assert decision(workspace, name, {"file_path": "app/service.py"})["permissionDecision"] == "deny"


@pytest.mark.parametrize("name", sorted(MCP_TOOLS))
def test_mcp_tools_require_tools_context(workspace, name):
    assert decision(workspace, name, {})["permissionDecision"] == "allow"
    assert decision(workspace, name, {}, context="repo")["permissionDecision"] == "deny"
    assert decision(workspace, name, {}, context="provided")["permissionDecision"] == "deny"


@pytest.mark.parametrize("context", ["repo", "provided", "tools"])
def test_structured_output_is_allowed_in_each_context(workspace, context):
    assert decision(workspace, "StructuredOutput", {}, context=context)["permissionDecision"] == "allow"


@pytest.mark.parametrize("name", ["Write", "Edit"])
def test_reproduce_only_changes_the_reported_case_test(workspace, name):
    assert decision(workspace, name, {"file_path": "tests/test_reported_case.py"}, phase="reproduce")["permissionDecision"] == "allow"
    for path in ("app/service.py", "app/devices.json", "tests/test_existing.py", "tests/test_policy_capacity.py"):
        assert decision(workspace, name, {"file_path": path}, phase="reproduce")["permissionDecision"] == "deny"


@pytest.mark.parametrize("name", ["Write", "Edit"])
def test_fix_changes_app_python_and_new_policy_tests_only(workspace, name):
    for path in ("app/service.py", "app/new_rule.py", "tests/test_policy_capacity.py"):
        assert decision(workspace, name, {"file_path": path}, phase="fix")["permissionDecision"] == "allow"
    for path in ("tests/test_existing.py", "tests/test_reported_case.py", "tests/test_other.py", "app/devices.json", "app/subdir/nested.py", "controls/reference.py", "CLAUDE.md"):
        assert decision(workspace, name, {"file_path": path}, phase="fix")["permissionDecision"] == "deny"


@pytest.mark.parametrize("path", ["../outside.py", "app/../../outside.py", "/etc/passwd", "CLAUDE.md", "knowledge/policy.md", "app/missing.py"])
def test_read_rejects_escape_and_non_evidence_files(workspace, path):
    assert decision(workspace, "Read", {"file_path": path})["permissionDecision"] == "deny"


@pytest.mark.parametrize("name,args", [
    ("Glob", {"pattern": "app/**/*.py"}),
    ("Glob", {"path": ".", "pattern": "app/**/*.py"}),
    ("Grep", {"path": ".", "pattern": "capacity", "glob": "tests/*.py"}),
])
def test_searches_are_rewritten_to_permitted_roots(workspace, name, args):
    result = decision(workspace, name, args)
    assert result["permissionDecision"] == "allow"
    updated = result["updatedInput"]
    path = Path(updated["path"])
    assert path in {workspace / "app", workspace / "tests"}
    if name == "Glob":
        assert updated["pattern"] == "**/*.py"
    else:
        assert updated["glob"] == "*.py"


def test_omitted_glob_path_with_tests_prefix_searches_tests(workspace):
    result = decision(workspace, "Glob", {"pattern": "tests/**/*.py"})
    assert result["permissionDecision"] == "allow"
    assert result["updatedInput"]["path"] == str(workspace / "tests")
    assert result["updatedInput"]["pattern"] == "**/*.py"


@pytest.mark.parametrize("pattern", ["../*.py", "/tmp/*.py", "{app,knowledge}/**/*", "app/../../*.py"])
def test_glob_patterns_cannot_escape_or_expand_to_unscoped_paths(workspace, pattern):
    assert decision(workspace, "Glob", {"pattern": pattern})["permissionDecision"] == "deny"


def test_symlink_read_and_write_are_denied(workspace, tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("private = True\n")
    (workspace / "app/link.py").symlink_to(outside)
    for name in ("Read", "Write", "Edit"):
        assert decision(workspace, name, {"file_path": "app/link.py"}, phase="fix")["permissionDecision"] == "deny"
    (workspace / "app/linked").symlink_to(tmp_path, target_is_directory=True)
    assert decision(workspace, "Read", {"file_path": "app/linked/outside.py"})["permissionDecision"] == "deny"


@pytest.mark.parametrize("name,args", [
    ("Glob", {"path": "app", "pattern": "**/*.py"}),
    ("Grep", {"path": "app", "pattern": "private", "glob": "**/*.py"}),
])
def test_searches_cannot_follow_symlink_descendants(workspace, tmp_path, name, args):
    external = tmp_path / "external"
    external.mkdir()
    (external / "private.py").write_text("private = True\n")
    (workspace / "app/linked").symlink_to(external, target_is_directory=True)
    assert decision(workspace, name, args)["permissionDecision"] == "deny"


@pytest.mark.parametrize("args", [None, [], {"file_path": 7}, {"file_path": ""}])
def test_invalid_tool_inputs_fail_closed(workspace, args):
    assert decision(workspace, "Read", args)["permissionDecision"] == "deny"
