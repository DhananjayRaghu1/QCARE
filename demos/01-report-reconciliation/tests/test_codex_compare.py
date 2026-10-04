from codex_compare import PROMPT, inputs, command


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
