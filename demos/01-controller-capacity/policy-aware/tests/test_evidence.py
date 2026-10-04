"""Packet checks verify captured source provenance without claiming semantics."""

from copy import deepcopy
import hashlib

import pytest

from evidence import PACKET_SCHEMA, materialize_packet, render_markdown, validate_packet


def source(content, kind, spans=None, metadata=None):
    return {
        "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "spans": spans if spans is not None else [[1, len(content.splitlines())]],
        "kind": kind, "metadata": metadata or {},
    }


@pytest.fixture
def captured():
    return {
        "ticket_id": "AG-1423",
        "sources": {
            "app/validator.py": source("def validate(zones):\n    limit = 20\n    return len(zones) <= limit\n", "code"),
            "registry/devices.json": source('{"DEV-101": {"model": "PRO", "firmware": "3.4.0"}}\n', "registry", metadata={"device": {"controller_id": "DEV-101", "model": "PRO", "firmware": "3.4.0"}}),
            "knowledge/capacity-policy.md": source("# Approved policy\nPro firmware 3.2.0 or newer permits 50 zones.\nEarlier Pro firmware permits 20 zones.\n", "knowledge"),
        },
    }


@pytest.fixture
def packet():
    return {
        "ticket_id": "AG-1423",
        "device": {"controller_id": "DEV-101", "model": "PRO", "firmware": "3.4.0", "citations": ["registry"]},
        "policy": {"status": "established", "text": "Eligible Pro devices permit 50 zones.", "citations": ["policy"]},
        "diagnosis": {"classification": "investigate_mismatch", "text": "The global limit contradicts the approved capacity.", "citations": ["code", "policy", "registry"]},
        "starting_files": [{"path": "app/validator.py", "line_start": 1, "line_end": 3, "reason": "The limit is applied here.", "citations": ["code"]}],
        "execution_path": {"text": "The validator compares zone count to a global limit.", "citations": ["code"]},
        "history": [],
        "owner": {"text": "Unknown: ownership was not retrieved.", "citations": []},
        "next_action": {"text": "Add a regression for this mismatch before editing.", "citations": ["code", "policy"]},
        "unknowns": ["Was this behavior deployed?"],
        "citations": [
            {"id": "code", "source": "app/validator.py", "line_start": 1, "line_end": 3},
            {"id": "policy", "source": "knowledge/capacity-policy.md", "line_start": 1, "line_end": 3},
            {"id": "registry", "source": "registry/devices.json", "line_start": 1, "line_end": 1},
        ],
    }


def invalid(packet, captured, text):
    result = validate_packet(packet, captured)
    assert result["status"] == "invalid"
    assert any(text in error for error in result["errors"]), result
    with pytest.raises(ValueError):
        materialize_packet(packet, captured)


def test_model_schema_contains_selectors_not_excerpts():
    assert set(PACKET_SCHEMA["properties"]["citations"]["items"]["properties"]) == {"id", "source", "line_start", "line_end"}


def test_materialized_packet_preserves_exact_source_and_input(packet, captured):
    before = deepcopy(packet)
    result = materialize_packet(packet, captured)
    assert packet == before
    citation = result["citations"][0]
    assert citation["excerpt"] == "def validate(zones):\n    limit = 20\n    return len(zones) <= limit"
    assert citation["source_hash"] == captured["sources"]["app/validator.py"]["sha256"]
    assert citation["kind"] == "code"
    assert validate_packet(result, captured)["status"] == "valid"
    assert materialize_packet(result, captured) == result


@pytest.mark.parametrize("field,value,message", [
    ("excerpt", "invented excerpt", "saved excerpt"),
    ("source_hash", "0" * 64, "saved source_hash"),
    ("kind", "knowledge", "saved kind"),
])
def test_saved_derived_fields_cannot_be_tampered(packet, captured, field, value, message):
    saved = materialize_packet(packet, captured)
    saved["citations"][0][field] = value
    invalid(saved, captured, message)


def test_content_hash_tampering_is_rejected_even_for_uncited_source(packet, captured):
    captured["sources"]["app/unused.py"] = source("print('original')\n", "code")
    captured["sources"]["app/unused.py"]["content"] = "print('changed')\n"
    invalid(packet, captured, "source hash")


def test_uncaptured_and_out_of_range_sources_are_rejected(packet, captured):
    packet["citations"][0]["source"] = "app/not-read.py"
    invalid(packet, captured, "not captured")
    packet["citations"][0]["source"] = "app/validator.py"
    packet["citations"][0]["line_end"] = 4
    invalid(packet, captured, "outside the captured")


def test_full_snapshot_does_not_grant_access_to_unread_lines(packet, captured):
    captured["sources"]["app/validator.py"]["spans"] = [[1, 1], [3, 3]]
    invalid(packet, captured, "not covered by successful reads")
    captured["sources"]["app/validator.py"]["spans"] = [[1, 1], [2, 3]]
    assert validate_packet(packet, captured)["status"] == "valid"


def test_starting_lines_need_covering_code_citations(packet, captured):
    packet["starting_files"][0]["citations"] = ["policy"]
    invalid(packet, captured, "needs code citations")
    packet["starting_files"][0]["citations"] = ["code"]
    packet["citations"][0]["line_start"] = 2
    invalid(packet, captured, "needs code citations")


def test_code_citations_can_jointly_cover_starting_lines(packet, captured):
    packet["citations"][0]["line_end"] = 1
    packet["citations"].append({"id": "code_rest", "source": "app/validator.py", "line_start": 2, "line_end": 3})
    packet["starting_files"][0]["citations"].append("code_rest")
    assert validate_packet(packet, captured)["status"] == "valid"


def test_policy_unknown_is_valid_for_repo_baseline(packet, captured):
    packet["policy"] = {"status": "unknown", "text": "Not established: approved limits are unavailable in the repository.", "citations": []}
    packet["diagnosis"] = {"classification": "insufficient_evidence", "text": "The implementation has a global limit; correctness needs approved requirements.", "citations": ["code"]}
    packet["next_action"] = {"text": "Obtain approved limits before changing the observed global limit.", "citations": ["code"]}
    packet["citations"] = [citation for citation in packet["citations"] if citation["id"] != "policy"]
    del captured["sources"]["knowledge/capacity-policy.md"]
    assert validate_packet(packet, captured)["status"] == "valid"


def test_established_policy_needs_knowledge_evidence(packet, captured):
    packet["policy"]["citations"] = ["code"]
    invalid(packet, captured, "established policy needs")


def test_cautious_unknown_policy_does_not_require_a_sentence_prefix(packet, captured):
    packet["policy"].update(status="unknown", text=(
        "The capacity policy text caps earlier Pro firmware at 20 zones. "
        "Its approved status, scope, and effective date were not in the "
        "successfully read evidence, so I cannot establish it as approved."))
    packet["diagnosis"]["classification"] = "insufficient_evidence"
    result = validate_packet(packet, captured)
    assert result["status"] == "valid"
    assert any("Policy status is unknown" in warning for warning in result["warnings"])
    assert materialize_packet(packet, captured)["policy"]["status"] == "unknown"


def test_unknown_policy_status_can_abstain_when_no_policy_was_read(packet, captured):
    packet["policy"] = {"status": "unknown", "text": "Approved requirements were not available in this investigation.", "citations": []}
    assert validate_packet(packet, captured)["status"] == "valid"


def test_literal_device_metadata_mismatch_is_rejected(packet, captured):
    packet["device"]["firmware"] = "3.1.0"
    invalid(packet, captured, "captured registry metadata")


def test_two_device_lookups_preserve_literal_fact_validation(packet, captured):
    registry = captured["sources"]["registry/devices.json"]
    registry["metadata"] = {"devices": {
        "DEV-101": {"controller_id": "DEV-101", "model": "PRO", "firmware": "3.4.0"},
        "DEV-102": {"controller_id": "DEV-102", "model": "PRO", "firmware": "3.1.0"},
    }}
    assert validate_packet(packet, captured)["status"] == "valid"
    packet["device"].update(controller_id="DEV-102", firmware="3.1.0")
    assert validate_packet(packet, captured)["status"] == "valid"
    packet["device"]["firmware"] = "3.4.0"
    invalid(packet, captured, "captured registry metadata")


def test_missing_firmware_can_be_explicitly_unknown(packet, captured):
    captured["sources"]["registry/devices.json"]["metadata"] = {"devices": {
        "DEV-101": {"controller_id": "DEV-101", "model": "PRO", "firmware": None},
    }}
    packet["device"]["firmware"] = "Unknown: missing firmware"
    assert validate_packet(packet, captured)["status"] == "valid"


def test_missing_unknown_device_can_abstain_without_registry(packet, captured):
    packet["device"] = {"controller_id": "DEV-101", "model": "Unknown", "firmware": "Not available", "citations": []}
    del captured["sources"]["registry/devices.json"]
    packet["citations"] = [citation for citation in packet["citations"] if citation["id"] != "registry"]
    packet["diagnosis"]["citations"].remove("registry")
    assert validate_packet(packet, captured)["status"] == "valid"


@pytest.mark.parametrize("path", ["../policy.md", "/tmp/policy.md", "app/./validator.py", "app//validator.py", "app\\validator.py", "app/validator.py\n"])
def test_paths_are_normalized_portable_references(packet, captured, path):
    packet["citations"][0]["source"] = path
    invalid(packet, captured, "normalized relative path")


@pytest.mark.parametrize("mutation,message", [
    (lambda p: p.update(ticket_id="AG-1424"), "investigated ticket"),
    (lambda p: p["citations"].append(deepcopy(p["citations"][0])), "duplicate identifier"),
    (lambda p: p["owner"].update(text="Scheduling team"), "needs citations"),
    (lambda p: p["next_action"].update(citations=["not_there"]), "unknown citation"),
    (lambda p: p["citations"][0].update(line_start=True), "expected integer"),
    (lambda p: p.update(invented_field="no"), "unexpected field"),
    (lambda p: p["citations"][0].update(excerpt="model supplied"), "derived fields must be complete"),
])
def test_schema_and_reference_failures(packet, captured, mutation, message):
    mutation(packet)
    invalid(packet, captured, message)


@pytest.mark.parametrize("bad", [None, [], {"ticket_id": "AG-1423"}, {"citations": [None]}])
def test_bad_inputs_report_errors_without_crashing(bad, captured):
    assert validate_packet(bad, captured)["status"] == "invalid"


@pytest.mark.parametrize("field,value", [
    ("kind", []), ("metadata", None), ("spans", [[True, 3]]),
    ("spans", [[1, 4]]), ("spans", "all"), ("content", None),
])
def test_corrupt_snapshot_fields_report_errors(packet, captured, field, value):
    captured["sources"]["app/validator.py"][field] = value
    assert validate_packet(packet, captured)["status"] == "invalid"


def test_long_narrative_warns_without_retry_or_truncation(packet, captured):
    packet["diagnosis"]["text"] = " ".join(["fact"] * 350)
    result = validate_packet(packet, captured)
    assert result["status"] == "valid"
    assert result["word_count"] > 300
    assert any("Length does not invalidate" in warning for warning in result["warnings"])
    assert materialize_packet(packet, captured)["diagnosis"]["text"] == packet["diagnosis"]["text"]


def test_mechanical_validity_does_not_assert_semantic_claim_support(packet, captured):
    packet["diagnosis"]["text"] = "This excerpt proves the sky is green and the customer has an SLA."
    result = validate_packet(packet, captured)
    assert result["status"] == "valid"
    assert any("do not establish claim support" in warning for warning in result["warnings"])
    markdown = render_markdown(materialize_packet(packet, captured))
    assert "Claim support requires human review" in markdown
    assert "actual model and run status" in markdown
    assert "limit = 20" in markdown


def test_markdown_escapes_html_and_handles_fenced_excerpts(packet, captured):
    packet["owner"]["text"] = "Unknown: <script>demo</script>"
    content = "```\n    limit = 20\n```\n"
    captured["sources"]["app/validator.py"] = source(content, "code")
    markdown = render_markdown(materialize_packet(packet, captured))
    assert "<script>" not in markdown
    assert "&lt;script&gt;" in markdown
    assert "````text\n```" in markdown


def test_markdown_requires_materialized_citations(packet):
    with pytest.raises(ValueError, match="materialized"):
        render_markdown(packet)
