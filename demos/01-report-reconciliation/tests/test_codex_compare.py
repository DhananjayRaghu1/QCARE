from codex_compare import PROMPT, inputs, command
import json
import sys
from types import SimpleNamespace

import pytest
import codex_compare


def test_conditions_differ_only_by_prose_business_documents():
    repo = inputs(False)
    docs = inputs(True)
    assert all(docs[path] == content for path, content in repo.items())
    assert len(docs.keys() - repo.keys()) == 10
    assert all(path.startswith("business-docs/") for path in docs.keys() - repo.keys())
    assert not any("acceptance" in path or "reference" in path or "recordings" in path for path in docs)
    assert "return reversal" not in repo["issue.json"]
    assert all('"rules"' not in content for path, content in docs.items() if path.startswith("business-docs/"))
    assert "125000" not in "\n".join(docs.values())
    assert "115000" in repo["issue.json"]


def test_both_conditions_use_same_nondirective_prompt_and_client(tmp_path):
    assert "If requirements remain ambiguous" in PROMPT
    assert "1250" not in PROMPT
    cmd = command(tmp_path, tmp_path/"output.json", tmp_path/"schema.json", {"model": "configured-model"})
    assert "--ignore-user-config" in cmd
    assert "--ephemeral" in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert "web_search=\"disabled\"" in cmd
    assert "memories.use_memories=false" in cmd
    assert "multi_agent" in cmd and "multi_agent_v2" in cmd


@pytest.mark.parametrize("failure", ["deleted_input", "timeout_race"])
def test_failed_condition_is_saved_and_next_condition_runs(monkeypatch, tmp_path, failure):
    frozen = {flag: inputs(flag) for flag in (False, True)}
    monkeypatch.setattr(codex_compare, "ROOT", tmp_path)
    monkeypatch.setattr(codex_compare, "inputs", lambda flag: frozen[flag])
    monkeypatch.setattr(codex_compare, "configuration", lambda: {})
    monkeypatch.setattr(codex_compare.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="stub"))
    packet = {"decision": "needs_clarification", "current_total_cents": 155000,
              "justified_total_cents": None, "diagnosis": "stub", "next_action": "Ask",
              "sources": [], "open_questions": ["Rule?"], "proposed_report_py": None, "regression_tests": []}
    if failure == "deleted_input":
        def stub(directory, output, schema, settings):
            delete = "Path('app/report.py').unlink(); " if "repo_only" in str(directory) else ""
            return [sys.executable, "-c", "from pathlib import Path; " + delete +
                    f"Path({str(output)!r}).write_text({json.dumps(packet)!r})"]
        monkeypatch.setattr(codex_compare, "command", stub)
    else:
        class ExitedProcess:
            pid, returncode = 123456, 0
            def communicate(self, *args, **kwargs):
                if args:
                    raise codex_compare.subprocess.TimeoutExpired("stub", .01)
                return "", ""
        monkeypatch.setattr(codex_compare.subprocess, "Popen", lambda *a, **k: ExitedProcess())
        def missing(*args):
            raise ProcessLookupError()
        monkeypatch.setattr(codex_compare.os, "killpg", missing)
    destination = codex_compare.run("regression")
    results = json.loads((destination / "results.json").read_text())["runs"]
    assert len(results) == 2
    assert results[0]["status"] == "failed"
    assert (destination / "repo_only.result.json").exists()
    assert (destination / "business_docs.result.json").exists()
    if failure == "deleted_input":
        assert "Input changed: app/report.py" in results[0]["errors"]
        assert results[1]["status"] == "completed"
