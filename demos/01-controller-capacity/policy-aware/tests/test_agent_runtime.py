"""Synthetic Claude traces test evidence capture independently of a model run."""

from copy import deepcopy
import hashlib
import json

import pytest

import agent_runtime
from evidence import PACKET_SCHEMA


def tool(name, args, content, *, identifier="use-1", error=False):
    return [
        json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": identifier, "name": name, "input": args}]}}),
        json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": identifier, "is_error": error, "content": content}]}}),
    ]


def mcp(name, args, response, **kwargs):
    return tool(f"mcp__engineering-knowledge__{name}", args, [{"type": "text", "text": json.dumps(response)}], **kwargs)


def final(**kwargs):
    return json.dumps({"type": "result", "is_error": False, "subtype": "success", **kwargs})


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "practice"
    (root / "app").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "app/validator.py").write_text("def validate(zones):\n    limit = 20\n    return len(zones) <= limit\n")
    (root / "app/devices.json").write_text('{\n  "DEV-101": {\n    "model": "PRO",\n    "firmware": "3.4.0"\n  },\n  "DEV-102": {\n    "model": "PRO",\n    "firmware": "3.1.0"\n  }\n}\n')
    (root / "tests/test_existing.py").write_text("def test_initial():\n    assert True\n")
    return root


@pytest.fixture
def evidence():
    return {"sources": {}, "ticket_id": "AG-1423"}


@pytest.fixture
def policy(monkeypatch):
    document = {
        "status": "ok", "document_id": "controller-capacity-policy",
        "source": "knowledge/confluence/controller-capacity-policy.md",
        "content": "# Capacity\nStatus: approved\n## Rules\nPro 3.2.0 and later permits 50 zones.\nEarlier Pro permits 20 zones.\nLegacy permits 20 zones.\n",
        "metadata": {"status": "approved", "version": "1"},
    }
    def lookup(identifier):
        return deepcopy(document) if identifier == document["document_id"] else {"status": "not_found"}
    monkeypatch.setattr(agent_runtime, "get_document", lookup)
    return document


def collect(lines, workspace, evidence, phase="investigate", context="tools"):
    return agent_runtime.collect_trace(lines, workspace, evidence, phase, context)


def test_only_successful_read_lines_become_citable(workspace, evidence):
    lines = tool("Read", {"file_path": "app/validator.py"}, "     2→    limit = 20\n")
    result = collect(lines + [final()], workspace, evidence)
    assert not result["errors"]
    source = evidence["sources"]["app/validator.py"]
    assert [list(span) for span in source["spans"]] == [[2, 2]]
    assert source["sha256"] == hashlib.sha256(source["content"].encode()).hexdigest()
    assert source["kind"] == "code"
    assert source["content"].startswith("def validate")


def test_denied_read_never_captures_snapshot(workspace, evidence):
    result = collect(tool("Read", {"file_path": "app/validator.py"}, "Permission denied", error=True) + [final()], workspace, evidence)
    assert result["errors"]
    assert not evidence["sources"]


def test_successful_read_with_unverifiable_content_fails_closed(workspace, evidence):
    result = collect(tool("Read", {"file_path": "app/validator.py"}, "     2→    limit = 500\n") + [final()], workspace, evidence)
    assert result["errors"]
    assert not evidence["sources"]


def test_symlink_read_is_independently_rejected_by_collector(workspace, evidence, tmp_path):
    outside = tmp_path / "secret.py"
    outside.write_text("secret = True\n")
    (workspace / "app/linked.py").symlink_to(outside)
    result = collect(tool("Read", {"file_path": "app/linked.py"}, "1→secret = True") + [final()], workspace, evidence)
    assert result["errors"]
    assert not evidence["sources"]


def test_native_registry_read_has_registry_kind(workspace, evidence):
    content = (workspace / "app/devices.json").read_text()
    text = "\n".join(f"{index}→{line}" for index, line in enumerate(content.splitlines(), 1))
    result = collect(tool("Read", {"file_path": "app/devices.json"}, text), workspace, evidence)
    assert not result["errors"]
    assert evidence["sources"]["app/devices.json"]["kind"] == "registry"


def search_response(policy, start=3, end=4):
    return {"status": "ok", "results": [{
        "document_id": policy["document_id"], "source": policy["source"],
        "excerpts": [{"line_start": start, "line_end": end,
                      "text": "\n".join(policy["content"].splitlines()[start - 1:end])}],
    }]}


def test_search_preview_does_not_authorize_unread_full_document(workspace, evidence, policy):
    result = collect(mcp("search_knowledge", {"query": "firmware capacity"}, search_response(policy)), workspace, evidence)
    assert not result["errors"]
    source = evidence["sources"][policy["source"]]
    assert [list(span) for span in source["spans"]] == [[3, 4]]
    assert source["content"] == policy["content"]
    # Having canonical content in a snapshot does not grant all its lines.
    assert [1, len(policy["content"].splitlines())] not in source["spans"]


@pytest.mark.parametrize("mutation", [
    lambda data: data["results"][0].update(source="knowledge/secret.md"),
    lambda data: data["results"][0]["excerpts"][0].update(text="Made up policy"),
    lambda data: data["results"][0]["excerpts"][0].update(line_end=999),
    lambda data: data["results"][0]["excerpts"][0].update(line_start="3"),
])
def test_search_mismatches_and_bad_bounds_fail_closed(workspace, evidence, policy, mutation):
    response = search_response(policy, 3, 6)
    mutation(response)
    result = collect(mcp("search_knowledge", {"query": "firmware"}, response), workspace, evidence)
    assert result["errors"]
    assert not evidence["sources"]


def test_full_document_fetch_authorizes_exact_full_document(workspace, evidence, policy):
    result = collect(mcp("get_document", {"document_id": policy["document_id"]}, policy), workspace, evidence)
    assert not result["errors"]
    assert [list(span) for span in evidence["sources"][policy["source"]]["spans"]] == [[1, 6]]


@pytest.mark.parametrize("mutation", [
    lambda data: data.update(source="knowledge/wrong.md"),
    lambda data: data.update(content=data["content"] + "invented\n"),
])
def test_full_document_result_must_match_manifest(workspace, evidence, policy, mutation):
    response = deepcopy(policy)
    mutation(response)
    result = collect(mcp("get_document", {"document_id": policy["document_id"]}, response), workspace, evidence)
    assert result["errors"]
    assert not evidence["sources"]


def test_document_result_id_must_match_request(workspace, evidence, policy):
    result = collect(mcp("get_document", {"document_id": "schedule-validation-design"}, policy), workspace, evidence)
    assert result["errors"]
    assert not evidence["sources"]


def device_response(workspace):
    content = (workspace / "app/devices.json").read_text()
    return {"status": "ok", "controller_id": "DEV-101", "record": {"model": "PRO", "firmware": "3.4.0"},
            "source": "app/devices.json", "content": content,
            "registry_sha256": hashlib.sha256(content.encode()).hexdigest(), "line_start": 2, "line_end": 5}


def test_device_tool_captures_consistent_record_and_normalized_fact_metadata(workspace, evidence):
    result = collect(mcp("get_device", {"controller_id": "DEV-101"}, device_response(workspace)), workspace, evidence)
    assert not result["errors"]
    source = evidence["sources"]["app/devices.json"]
    assert source["metadata"]["device"] == {"controller_id": "DEV-101", "model": "PRO", "firmware": "3.4.0"}
    assert [list(span) for span in source["spans"]] == [[2, 5]]


@pytest.mark.parametrize("mutation", [
    lambda data: data["record"].update(firmware="3.1.0"),
    lambda data: data.update(controller_id="DEV-102"),
    lambda data: data.update(content="{}\n"),
    lambda data: data.update(registry_sha256="0" * 64),
    lambda data: data.update(line_start=True),
    lambda data: data.update(line_end=1000),
])
def test_device_response_must_match_requested_workspace_record(workspace, evidence, mutation):
    response = device_response(workspace)
    mutation(response)
    result = collect(mcp("get_device", {"controller_id": "DEV-101"}, response), workspace, evidence)
    assert result["errors"]
    assert not evidence["sources"]


@pytest.mark.parametrize("status", ["no_results", "not_found"])
def test_absent_information_is_not_a_tool_execution_failure(workspace, evidence, status):
    result = collect(mcp("search_knowledge", {"query": "unicorns"}, {"status": status, "results": []}) + [final()], workspace, evidence)
    assert not result["errors"]
    assert not evidence["sources"]


@pytest.mark.parametrize("status", ["invalid_request", "unavailable"])
def test_failed_retrieval_status_is_fatal(workspace, evidence, status):
    result = collect(mcp("search_knowledge", {"query": "firmware"}, {"status": status, "results": []}), workspace, evidence)
    assert result["errors"]


def test_structured_output_schema_error_is_separate_from_tool_denial(workspace, evidence):
    lines = tool("StructuredOutput", {}, "Output does not match required schema: missing policy", error=True)
    lines += tool("StructuredOutput", {}, "{}", identifier="use-2") + [final(structured_output={"ticket_id": "AG-1423"})]
    result = collect(lines, workspace, evidence)
    assert not result["errors"]
    assert result["format_errors"]
    assert result["result"]["structured_output"] == {"ticket_id": "AG-1423"}


def schema_failure():
    return tool("StructuredOutput", {}, "Output does not match required schema: missing policy", identifier="schema", error=True)


def sdk_unknown(name):
    return f"<tool_use_error>Error: No such tool available: {name}</tool_use_error>"


@pytest.mark.parametrize("name", sorted(PACKET_SCHEMA["properties"]))
def test_schema_field_misaddressing_is_formatting_only_after_schema_failure(workspace, evidence, name):
    lines = tool("Read", {"file_path": "app/validator.py"}, "2→    limit = 20", identifier="read")
    lines += schema_failure()
    lines += tool(name, {"text": "field value", "citations": []}, sdk_unknown(name), identifier="field", error=True)
    lines += [final(structured_output={"ticket_id": "AG-1423"}, permission_denials=[])]
    before = (workspace / "app/validator.py").read_text()
    result = collect(lines, workspace, evidence)
    assert not result["errors"]
    assert result["format_errors"] == ["Output does not match required schema: missing policy", sdk_unknown(name)]
    assert [item["name"] for item in result["tools"]] == ["Read", "StructuredOutput", name]
    assert set(evidence["sources"]) == {"app/validator.py"}
    source = evidence["sources"]["app/validator.py"]
    assert source["content"] == before
    assert [list(span) for span in source["spans"]] == [[2, 2]]
    assert (workspace / "app/validator.py").read_text() == before


def test_schema_field_unknown_tool_without_prior_schema_error_stays_fatal(workspace, evidence):
    result = collect(tool("policy", {}, sdk_unknown("policy"), error=True) + [final()], workspace, evidence)
    assert result["errors"]
    assert not result["format_errors"]
    assert not evidence["sources"]


def test_later_schema_error_cannot_reclassify_an_earlier_unknown_tool(workspace, evidence):
    lines = tool("policy", {}, sdk_unknown("policy"), identifier="field", error=True) + schema_failure() + [final()]
    result = collect(lines, workspace, evidence)
    assert result["errors"]
    assert result["format_errors"] == ["Output does not match required schema: missing policy"]


def test_structured_output_denial_does_not_enable_field_recovery(workspace, evidence):
    lines = tool("StructuredOutput", {}, "Permission denied", identifier="schema", error=True)
    lines += tool("policy", {}, sdk_unknown("policy"), identifier="field", error=True) + [final()]
    result = collect(lines, workspace, evidence)
    assert result["errors"]
    assert not result["format_errors"]


@pytest.mark.parametrize("name", ["Bash", "WebFetch", "firmware", "text", "policy_extra", "Policy"])
def test_only_top_level_schema_fields_qualify_for_format_recovery(workspace, evidence, name):
    lines = schema_failure() + tool(name, {}, sdk_unknown(name), identifier="other", error=True) + [final()]
    result = collect(lines, workspace, evidence)
    assert result["errors"]
    assert result["format_errors"] == ["Output does not match required schema: missing policy"]


@pytest.mark.parametrize("message", [
    "Permission denied", "No such tool available: policy",
    "<tool_use_error>Error: No such tool available: diagnosis</tool_use_error>",
    "<tool_use_error>Error: Tool execution failed: policy</tool_use_error>",
    "prefix <tool_use_error>Error: No such tool available: policy</tool_use_error>",
])
def test_schema_field_recovery_requires_exact_matching_sdk_reply(workspace, evidence, message):
    lines = schema_failure() + tool("policy", {}, message, identifier="field", error=True) + [final()]
    result = collect(lines, workspace, evidence)
    assert result["errors"]
    assert result["format_errors"] == ["Output does not match required schema: missing policy"]


def test_schema_field_success_cannot_be_treated_as_a_format_error(workspace, evidence):
    lines = schema_failure() + tool("policy", {}, "executed", identifier="field", error=False) + [final()]
    result = collect(lines, workspace, evidence)
    assert any("Unexpected execution" in error for error in result["errors"])
    assert result["format_errors"] == ["Output does not match required schema: missing policy"]
    assert not evidence["sources"]


def test_schema_field_attempt_without_sdk_result_is_fatal(workspace, evidence):
    lines = schema_failure() + tool("policy", {}, sdk_unknown("policy"), identifier="field", error=True)[:1] + [final()]
    result = collect(lines, workspace, evidence)
    assert any("Unresolved output field" in error for error in result["errors"])


def test_final_permission_denial_overrides_recoverable_field_formatting(workspace, evidence):
    lines = schema_failure() + tool("policy", {}, sdk_unknown("policy"), identifier="field", error=True)
    lines += [final(permission_denials=[{"tool_name": "policy"}])]
    result = collect(lines, workspace, evidence)
    assert sdk_unknown("policy") in result["format_errors"]
    assert any("Permission denial" in error for error in result["errors"])


def test_recovered_field_output_still_requires_a_final_client_result(workspace, evidence):
    from demo import invocation_problems
    result = collect(schema_failure() + tool("policy", {}, sdk_unknown("policy"), identifier="field", error=True), workspace, evidence)
    assert result["result"] is None
    problems = invocation_problems({"timed_out": False, "exit_code": 0}, result)
    assert any("successful final result" in problem for problem in problems)


def test_format_recovery_does_not_validate_an_incomplete_final_packet(workspace, evidence):
    from evidence import validate_packet
    lines = schema_failure() + tool("policy", {}, sdk_unknown("policy"), identifier="field", error=True)
    lines += [final(structured_output={"ticket_id": "AG-1423"})]
    result = collect(lines, workspace, evidence)
    assert not result["errors"]
    assert validate_packet(result["result"]["structured_output"], evidence)["status"] == "invalid"


def test_recovered_field_formatting_does_not_hide_an_escaped_native_read(workspace, evidence, tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("private = True\n")
    lines = schema_failure() + tool("policy", {}, sdk_unknown("policy"), identifier="field", error=True)
    lines += tool("Read", {"file_path": str(outside)}, "1→private = True", identifier="read") + [final()]
    result = collect(lines, workspace, evidence)
    assert any("escaped workspace" in error for error in result["errors"])
    assert not evidence["sources"]


@pytest.mark.parametrize("phase", ["reproduce", "fix"])
def test_field_formatting_exception_does_not_expand_coding_phase_tools(workspace, evidence, phase):
    lines = schema_failure() + tool("policy", {}, sdk_unknown("policy"), identifier="field", error=True) + [final()]
    result = collect(lines, workspace, evidence, phase=phase)
    assert result["errors"]
    assert result["format_errors"] == ["Output does not match required schema: missing policy"]


def test_permission_denial_reported_only_in_final_metadata_stays_fatal(workspace, evidence):
    result = collect([final(permission_denials=[{"tool_name": "Read"}])], workspace, evidence)
    assert any("Permission denial" in error for error in result["errors"])


def test_structured_output_denial_is_fatal_not_schema_repair(workspace, evidence):
    result = collect(tool("StructuredOutput", {}, "Permission denied", error=True), workspace, evidence)
    assert result["errors"]
    assert not result["format_errors"]


def test_out_of_scope_tool_attempt_is_fatal_without_success_result(workspace, evidence):
    lines = tool("Bash", {"command": "cat /etc/passwd"}, "denied", error=True)
    result = collect(lines, workspace, evidence)
    assert any("outside phase scope" in error for error in result["errors"])
    assert not evidence["sources"]


@pytest.mark.parametrize("event", ["junk", "null", "[]", "42", '{"type":"assistant","message":null}'])
def test_non_event_stream_records_do_not_crash_collector(workspace, evidence, event):
    result = collect([event, final()], workspace, evidence)
    assert result["result"]["type"] == "result"


def test_incomplete_trace_has_no_final_result(workspace, evidence):
    result = collect(tool("StructuredOutput", {}, "{}"), workspace, evidence)
    assert result["result"] is None


def test_model_identity_comes_from_actual_client_metadata(workspace, evidence):
    init = json.dumps({"type": "system", "subtype": "init", "model": "actual-model"})
    assert collect([init, final(modelUsage={"fallback-model": {}})], workspace, evidence)["model"] == "actual-model"
    assert collect([final(modelUsage={"actual-model": {}})], workspace, evidence)["model"] == "actual-model"


def test_coding_phase_does_not_relabel_mutable_files_as_investigation_evidence(workspace, evidence):
    result = collect(tool("Read", {"file_path": "app/validator.py"}, "1→def validate(zones):"), workspace, evidence, phase="fix")
    assert not result["errors"]
    assert not evidence["sources"]


def test_source_changes_during_capture_are_detected(evidence):
    agent_runtime.capture(evidence, "app/file.py", "old\n", [[1, 1]], "code")
    with pytest.raises(ValueError, match="Source changed"):
        agent_runtime.capture(evidence, "app/file.py", "new\n", [[1, 1]], "code")


@pytest.mark.parametrize("context", ["repo", "provided", "tools"])
@pytest.mark.parametrize("phase", ["investigate", "reproduce", "fix"])
def test_client_command_keeps_native_scope_and_mcp_configuration_explicit(workspace, phase, context):
    command = agent_runtime.client_command({"executable": "claude", "configured_model": "configured-model"}, workspace, phase, context, "bm25", schema={"type": "object"})
    def argument(flag):
        return command[command.index(flag) + 1]
    assert argument("--setting-sources") == ""
    assert "--strict-mcp-config" in command
    assert "--no-session-persistence" in command
    assert "--no-chrome" in command
    assert "--disable-slash-commands" in command
    assert "Bash" not in argument("--tools").split(",")
    assert not (set(PACKET_SCHEMA["properties"]) & set(argument("--allowedTools").split(",")))
    assert ("Edit" in argument("--tools").split(",")) == (phase != "investigate")
    servers = json.loads(argument("--mcp-config"))["mcpServers"]
    if context == "tools":
        assert servers["engineering-knowledge"]["args"][-1] == str(workspace / "app/devices.json")
    else:
        assert not servers
    assert argument("--model") == "configured-model"
