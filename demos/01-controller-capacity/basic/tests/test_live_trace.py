"""An attempted or denied tool call must not count as successful demo evidence."""

import json

from scripts.run_live_investigation import summarize_trace


def event(kind, blocks):
    return json.dumps({"type": kind, "message": {"content": blocks}})


def call(name, identifier, args=None):
    return {"type": "tool_use", "id": identifier, "name": name, "input": args or {}}


def reply(identifier, content, error=False):
    return {"type": "tool_result", "tool_use_id": identifier, "content": content, "is_error": error}


def test_denied_knowledge_calls_cannot_verify_live_demo(tmp_path):
    lines = [event("assistant", [call("mcp__engineering-knowledge__get_engineering_ticket", "a")]), event("user", [reply("a", "Permission denied", True)]), json.dumps({"type": "result", "is_error": False, "result": "A plausible answer"})]
    report = summarize_trace(lines, tmp_path)
    assert report["tools_called"]
    assert not report["knowledge_tools_used"]
    assert report["successful_knowledge_tools"] == []


def test_success_requires_evidence_from_both_knowledge_tools(tmp_path):
    lines = []
    for identifier, suffix in (("a", "get_engineering_ticket"), ("b", "search_engineering_knowledge")):
        lines.append(event("assistant", [call("mcp__engineering-knowledge__" + suffix, identifier)]))
        lines.append(event("user", [reply(identifier, [{"type": "text", "text": json.dumps({"status": "ok", "synthetic": True})}])]))
    lines.append(event("assistant", [call("Read", "c", {"file_path": "app/schedule_validator.py"})]))
    lines.append(event("user", [reply("c", "source text")]))
    report = summarize_trace(lines, tmp_path)
    assert report["knowledge_tools_used"]
    assert report["application_files_read"] == [str(tmp_path / "app/schedule_validator.py")]


def test_no_results_and_external_reads_do_not_count_as_demonstrated_evidence(tmp_path):
    lines = [event("assistant", [call("mcp__engineering-knowledge__search_engineering_knowledge", "a"), call("Read", "b", {"file_path": "../other.py"})]), event("user", [reply("a", json.dumps({"status": "no_results"})), reply("b", "unrelated source")])]
    report = summarize_trace(lines, tmp_path)
    assert not report["knowledge_tools_used"]
    assert not report["application_files_read"]
