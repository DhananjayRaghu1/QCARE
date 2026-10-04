"""Local runner probes, not a simulated claim of live model verification."""
import json
from pathlib import Path
import sys

from onramp import (build_prompt, client_command, collect_trace, execute_client,
                    read_spans, resolve_run)
from scripts.guard_onramp_tool import decide


def event(kind, blocks):
    return json.dumps({"type": kind, "message": {"content": blocks}})


def call(name, identifier, args=None):
    return {"type": "tool_use", "name": name, "id": identifier, "input": args or {}}


def reply(identifier, content, error=False):
    return {"type": "tool_result", "tool_use_id": identifier, "content": content, "is_error": error}


def fixture(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("first\nsecond\nthird\n")
    return {"id": "AG-1423", "source": "knowledge/jira/AG-1423.md", "content": "Customer symptom"}


def test_partial_read_only_allows_verified_lines(tmp_path):
    ticket = fixture(tmp_path)
    lines = [event("assistant", [call("Read", "a", {"file_path": "app/a.py"})]),
             event("user", [reply("a", "2→second\n3→wrong")])]
    evidence, report = collect_trace(lines, tmp_path, ticket, augmented=True)
    assert evidence["code_spans"] == {"app/a.py": [[2, 2]]}
    assert report["application_files_read"] == ["app/a.py"]
    assert not report["searches"]


def test_denied_or_fabricated_reads_do_not_become_evidence(tmp_path):
    ticket = fixture(tmp_path)
    lines = [event("assistant", [call("Read", "a", {"file_path": "app/a.py"}), call("Read", "b", {"file_path": "../private.py"})]),
             event("user", [reply("a", "1→fabricated"), reply("b", "Permission denied", True)])]
    evidence, report = collect_trace(lines, tmp_path, ticket, augmented=True)
    assert not evidence["code_files"]
    assert len(report["tool_errors"]) == 1


def test_missing_or_unknown_tools_cannot_verify_success(tmp_path):
    ticket = fixture(tmp_path)
    lines = [event("assistant", [call("Bash", "x")]), event("user", [reply("x", "done")])]
    _, report = collect_trace(lines, tmp_path, ticket, augmented=False)
    assert report["tool_errors"][0]["tool"] == "Bash"


def test_read_line_number_formats_and_unmatched_text():
    assert read_spans(" 1\tone\n2→two", "one\ntwo\nthree") == [[1, 2]]
    assert read_spans("guess", "one\ntwo") == []


def test_same_ticket_given_to_both_modes(tmp_path):
    ticket = fixture(tmp_path)
    warm = build_prompt(ticket, True, "hybrid")
    cold = build_prompt(ticket, False, "hybrid")
    assert "1: Customer symptom" in warm and "1: Customer symptom" in cold
    assert "capacity" not in warm
    assert "No company knowledge tools" in cold


def test_cold_client_has_no_mcp_or_shell_tools(tmp_path):
    client = {"executable": "claude", "configured_model": "Claude client default"}
    command = client_command(client, tmp_path, False, "hybrid")
    config = json.loads(command[command.index("--mcp-config") + 1])
    assert config == {"mcpServers": {}}
    assert command[command.index("--tools") + 1] == "Read,Glob,Grep"
    assert "--dangerously-skip-permissions" not in command
    assert "--max-budget-usd" in command
    assert "--json-schema" in command


def test_guard_denies_external_reads_and_writes(tmp_path):
    fixture(tmp_path)
    outside = tmp_path.parent / "outside.py"
    outside.write_text("secret")
    for name, args in [("Read", {"file_path": str(outside)}), ("Bash", {"command": "pwd"}),
                       ("Glob", {"pattern": "../*.py"}), ("Edit", {"file_path": "app/a.py"})]:
        assert decide({"tool_name": name, "tool_input": args}, tmp_path, True)["hookSpecificOutput"]["permissionDecision"] == "deny"
    (tmp_path / "app/link.py").symlink_to(outside)
    assert decide({"tool_name": "Read", "tool_input": {"file_path": "app/link.py"}}, tmp_path, True)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_guard_narrows_root_search_and_cold_mcp_denied(tmp_path):
    fixture(tmp_path)
    allowed = decide({"tool_name": "Glob", "tool_input": {"path": ".", "pattern": "app/*.py"}}, tmp_path, True)["hookSpecificOutput"]
    assert allowed["permissionDecision"] == "allow"
    assert allowed["updatedInput"]["path"] == str(tmp_path / "app")
    assert allowed["updatedInput"]["pattern"] == "*.py"
    assert decide({"tool_name": "mcp__engineering-knowledge__get_engineering_ticket"}, tmp_path, False)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_runner_timeout_keeps_partial_trace_without_success(tmp_path):
    command = [sys.executable, "-u", "-c", 'import time; print(\'{"type":"system","subtype":"init","model":"local-fixture"}\'); time.sleep(5)']
    lines, code, timed_out, _ = execute_client(command, "", tmp_path, timeout=1)
    assert timed_out and code != 0
    assert len(lines) == 1


def test_replay_rejects_arbitrary_external_paths(tmp_path):
    try:
        resolve_run(str(tmp_path))
    except ValueError:
        pass
    else:
        raise AssertionError("External run path accepted")


def test_final_result_permission_denial_is_failure_evidence(tmp_path):
    ticket = fixture(tmp_path)
    _, report = collect_trace([json.dumps({"type": "result", "is_error": False,
                                           "permission_denials": [{"tool_name": "Read"}]})], tmp_path, ticket, augmented=True)
    assert report["tool_errors"][0]["tool"] == "Read"


def test_search_ok_label_without_verified_source_does_not_count(tmp_path):
    ticket = fixture(tmp_path)
    lines = [event("assistant", [call("mcp__engineering-knowledge__search_engineering_knowledge", "a")]),
             event("user", [reply("a", json.dumps({"status": "ok", "mode": "hybrid", "results": [
                 {"source": "knowledge/confluence/controller-limits.md", "content": "invented", "id": "fake"}]}))])]
    _, report = collect_trace(lines, tmp_path, ticket, augmented=True)
    assert not report["searches"]
    assert report["tool_errors"]


def test_guard_rejects_glob_brace_escape(tmp_path):
    fixture(tmp_path)
    for pattern in ["{../outside,**}/*.py", "{/Users/ishaan/outside,**}/*.py"]:
        output = decide({"tool_name": "Glob", "tool_input": {"pattern": pattern}}, tmp_path, True)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


import pytest


@pytest.mark.parametrize('reason', ['Ticket lookup: not_found', 'MCP transport unavailable', 'Retrieval preflight: unavailable'])
def test_preflight_failure_is_saved_without_launching_model(tmp_path, monkeypatch, reason):
    import onramp
    monkeypatch.setattr(onramp, 'ARTIFACTS', tmp_path / 'outputs')
    monkeypatch.setattr(onramp, 'client_preflight', lambda: {'installed': True, 'authenticated': True})
    def unavailable(*args, **kwargs):
        raise RuntimeError(reason)
    monkeypatch.setattr(onramp, 'local_inputs', unavailable)
    def unexpected_launch(*args, **kwargs):
        raise AssertionError('A model must not launch after failed preflight')
    monkeypatch.setattr(onramp, 'execute_client', unexpected_launch)
    assert onramp.run_live('AG-9999', 'hybrid', False, 180, None) == 1
    directory = next((tmp_path / 'outputs').iterdir())
    metadata = json.loads((directory / 'metadata.json').read_text())
    assert metadata['status'] == 'failed'
    assert metadata['agent_run'] is False
    assert reason in metadata['problems'][0]
    assert json.loads((directory / 'packet.json').read_text()) is None
    assert not (directory / 'trace.jsonl').read_text()


def test_corrected_schema_tool_error_is_a_retry_not_a_denial(tmp_path):
    ticket = fixture(tmp_path)
    lines = [event('assistant', [call('StructuredOutput', 'first')]),
             event('user', [reply('first', 'Output does not match required schema: owner must be object', True)]),
             json.dumps({'type': 'result', 'is_error': False, 'structured_output': {'ticket_id': 'AG-1423'}})]
    _, report = collect_trace(lines, tmp_path, ticket, augmented=True)
    assert report['tool_errors'] == []
    assert len(report['output_format_errors']) == 1
    denied_lines = [event('assistant', [call('StructuredOutput', 'denied')]),
                    event('user', [reply('denied', 'Permission denied', True)])]
    _, report = collect_trace(denied_lines, tmp_path, ticket, augmented=True)
    assert report['tool_errors']


def test_correction_prompt_only_includes_actually_read_code_spans(tmp_path):
    from onramp import correction_prompt
    ticket = fixture(tmp_path)
    evidence = {'documents': {ticket['source']: ticket['content']},
                'code_files': {'app/a.py': 'visible\nnot yet read\n'},
                'code_spans': {'app/a.py': [[1, 1]]}}
    prompt = correction_prompt(ticket, False, 'hybrid', None, {}, evidence, {'errors': ['bad range']})
    assert '1: visible' in prompt and 'not yet read' not in prompt
    assert 'No company knowledge tools' in prompt


# Reuse the strict packet fixture rather than inventing a second schema here.
from test_onramp_packet import captured_packet


@pytest.mark.parametrize('second_pass', ['valid', 'invalid', 'timeout'])
def test_one_bounded_correction_pass_preserves_original_and_honest_status(captured_packet, tmp_path, monkeypatch, second_pass):
    from copy import deepcopy
    import onramp
    packet, evidence = captured_packet
    ticket = {'id': 'AG-1423', 'source': 'knowledge/jira/AG-1423.md',
              'content': evidence['documents']['knowledge/jira/AG-1423.md']}
    original = deepcopy(packet)
    original['citations'][0]['excerpt'] = 'invented source text'
    repo = Path(evidence['repo_root'])
    monkeypatch.setattr(onramp, 'ARTIFACTS', tmp_path / 'outputs')
    monkeypatch.setattr(onramp, 'client_preflight', lambda: {
        'installed': True, 'authenticated': True, 'executable': 'local-test-fixture',
        'configured_model': 'Claude client default'})
    monkeypatch.setattr(onramp, 'local_inputs', lambda *a, **k: (ticket, {'transport': 'local test fixture'}))
    monkeypatch.setattr(onramp, 'prepare', lambda _: repo)
    received = []
    def fake_client(command, prompt, workspace, timeout):
        received.append((command, prompt, timeout))
        number = len(received)
        if number == 2 and second_pass == 'timeout':
            return [], -15, True, ''
        output = original if number == 1 or second_pass == 'invalid' else packet
        blocks = [event('assistant', [call('Read', f'r{number}', {'file_path': 'app/service.py'})]),
                  event('user', [reply(f'r{number}', evidence['code_files']['app/service.py'])]),
                  json.dumps({'type': 'result', 'is_error': False, 'structured_output': output})]
        return blocks, 0, False, ''
    monkeypatch.setattr(onramp, 'execute_client', fake_client)
    # This local fixture's ownership evidence was acquired in the modeled first
    # pass. Production collect_trace still requires actual successful tool results.
    real_collect = onramp.collect_trace
    def fixture_collect(lines, target, fetched, *, augmented):
        captured, report = real_collect(lines, target, fetched, augmented=augmented)
        captured['documents'].update(evidence['documents'])
        return captured, report
    monkeypatch.setattr(onramp, 'collect_trace', fixture_collect)
    status = onramp.run_live('AG-1423', 'hybrid', True, 180, None)
    assert status == (0 if second_pass == 'valid' else 1)
    assert len(received) == 2
    assert 1 <= received[1][2] <= received[0][2] <= 180
    for command, _, _ in received:
        assert command[command.index('--max-budget-usd') + 1] == '1'
    directory = next((tmp_path / 'outputs').iterdir())
    metadata = json.loads((directory / 'metadata.json').read_text())
    assert len(metadata['validation_attempts']) == 2
    assert metadata['sources_unchanged'] is True
    assert json.loads((directory / 'first-pass-packet.json').read_text()) == original
    if second_pass == 'valid':
        assert metadata['status'] == 'success'
    else:
        assert metadata['status'] in {'failed', 'partial'}
