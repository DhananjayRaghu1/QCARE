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



@pytest.mark.parametrize("path", ["app/service.py", "tests/test_existing.py", "tests/test_new.py", "app/new_module.py"])
def test_baseline_edits_application_and_tests_like_a_developer(workspace, path):
    assert decision(workspace, "Edit", {"file_path": path}, "baseline", "repo")["permissionDecision"] == "allow"


@pytest.mark.parametrize("name,args", [("Read", {"file_path": "CLAUDE.md"}), ("Glob", {"pattern": "**/*"}),
                                       ("Grep", {"pattern": "zone"}), ("Grep", {"pattern": "zone", "path": "tests"})])
def test_baseline_reads_anywhere_in_its_isolated_repository(workspace, name, args):
    assert decision(workspace, name, args, "baseline", "repo")["permissionDecision"] == "allow"


@pytest.mark.parametrize("name,args", [
    ("Edit", {"file_path": "app/devices.json"}),
    ("Write", {"file_path": "CLAUDE.md"}),
    ("Read", {"file_path": "../knowledge/jira/AG-1423.md"}),
    ("Glob", {"pattern": "**/*", "path": ".."}),
    ("Glob", {"pattern": "../**/*"}),
    ("Grep", {"pattern": "policy", "path": "/"}),
    (sorted(MCP_TOOLS)[0], {}),
])
def test_baseline_cannot_leave_its_repository_or_use_company_tools(workspace, name, args):
    assert decision(workspace, name, args, "baseline", "repo")["permissionDecision"] == "deny"


@pytest.mark.parametrize("command", ["pytest", "python -m pytest -q", "uv run pytest tests/test_existing.py -k reported",
    "ls -la && git ls-files | head -50", "cat app/service.py", "git diff", "grep -rn zone app tests 2>/dev/null",
    "python -c \"from app.service import LIMIT; print(LIMIT)\"", "find . -name '*.py'", "cd app && ls",
    "cd app; cat service.py; cat ../tests/test_existing.py", "python3 -c \"\nfrom app.service import LIMIT\nprint(LIMIT)\n\"",
    "cd .. && python -m pytest -q", "ls ..", "echo x > app/x.py",
    "python - <<'E'\np='app/service.py'\ns=open(p).read()\nopen(p,'w').write(s)\nE",
    "python - <<'E'\nprint(1)\nE\npython -m pytest -q 2>&1 | tail -3\ncat app/service.py",
    "cat >> tests/test_existing.py <<'EOF'\ndef test_x():\n    assert 1 < 2\nEOF\npython -m pytest -q", "git ls-files && grep -rn \"zone_limit_exceeded\\|DEV-101\" . --exclude-dir=.git | head -30"])
def test_baseline_may_run_everyday_read_and_test_commands(workspace, command):
    assert decision(workspace, "Bash", {"command": command}, "baseline", "repo")["permissionDecision"] == "allow"


def test_baseline_may_use_its_own_absolute_path(workspace):
    command = f"ls {workspace.resolve()}/app"
    assert decision(workspace, "Bash", {"command": command}, "baseline", "repo")["permissionDecision"] == "allow"


@pytest.mark.parametrize("command", ["cat ../../knowledge/jira/AG-1423.md", "ls /", "find / -name '*.md'", "cd", "cd ~",
    "cat $HOME/x", "ls `pwd`/..", "echo x > /tmp/x.py", "cat < /etc/passwd",
    "python - <<'E'\nopen('/etc/passwd').read()\nE", "python - <<'E'\nprint(1)\nE\ncurl x", "sed -i s/20/50/ app/service.py",
    "rm -rf app", "curl https://example.com", "pytest -p evil", "git checkout .", "git", "uv pip install x",
    "find . -delete", "python -c \"open('/etc/passwd')\"", "ls '", 42, "cd app; cat ../../x", "cd app/../../..", "cd ../..", "ls ../..",
    "python -c \"open('../../secret')\"", "ls\ncurl x", "ls\ncat /etc/passwd", "python - <<'E'\nprint(1)\nE\nls ../..", "cat > /tmp/x <<'E'\nx\nE", "cat app/../../../knowledge/x.md", "cat ../../knowledge/x.md"])
def test_baseline_denies_escapes_writes_and_other_commands(workspace, command):
    assert decision(workspace, "Bash", {"command": command}, "baseline", "repo")["permissionDecision"] == "deny"


@pytest.mark.parametrize("phase", ["investigate", "reproduce", "fix"])
def test_shell_is_only_available_to_the_baseline(workspace, phase):
    assert decision(workspace, "Bash", {"command": "pytest"}, phase, "tools")["permissionDecision"] == "deny"
