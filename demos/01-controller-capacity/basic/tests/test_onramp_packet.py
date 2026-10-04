"""Evidence checks must reject plausible output that the run did not observe."""

from copy import deepcopy
import json

import pytest

from onramp_packet import render_markdown, save_run, validate_packet


@pytest.fixture
def captured_packet(tmp_path):
    (tmp_path / "app").mkdir()
    code = "def save_schedule(payload):\n    maximum_zones = resolve()\n    return persist(payload)\n"
    (tmp_path / "app/service.py").write_text(code)
    document = "# Scheduling architecture\nOwner: Scheduling Backend\nService resolves capacity before validating and persisting.\n"
    evidence = {
        "repo_root": str(tmp_path),
        "code_files": {"app/service.py": code},
        "code_spans": {"app/service.py": [[1, 3]]},
        "documents": {"knowledge/architecture.md": document,
                      "knowledge/jira/AG-1423.md": "Pro customers report that saving a schedule returns an error.\n"},
    }
    code_ref = {
        "id": "C1", "kind": "code", "source": "app/service.py",
        "line_start": 1, "line_end": 3, "excerpt": code.rstrip(),
    }
    doc_ref = {
        "id": "D1", "kind": "knowledge", "source": "knowledge/architecture.md",
        "line_start": 2, "line_end": 3, "excerpt": "Owner: Scheduling Backend\nService resolves capacity before validating and persisting.",
    }
    ticket_ref = {"id": "T1", "kind": "knowledge", "source": "knowledge/jira/AG-1423.md",
                  "line_start": 1, "line_end": 1,
                  "excerpt": "Pro customers report that saving a schedule returns an error."}
    packet = {
        "ticket_id": "AG-1423", "summary": "Pro customers report that saving a schedule returns an error.",
        "summary_citations": ["T1"],
        "likely_subsystem": {"text": "Investigate server scheduling.", "citations": ["C1", "D1"]},
        "starting_files": [{
            "path": "app/service.py", "line_start": 1, "line_end": 2,
            "reason": "Start at the save entry and its capacity resolution.", "citations": ["C1"],
        }],
        "execution_path": {"text": "Capacity resolution precedes persistence.", "citations": ["C1", "D1"]},
        "history": [],
        "owner": {"text": "Scheduling Backend", "citations": ["D1"]},
        "first_investigation": {"text": "Compare the controller in the request with the resolver argument.", "citations": ["C1"]},
        "unknowns": ["The affected deployed version has not been established."],
        "citations": [code_ref, doc_ref, ticket_ref],
    }
    return packet, evidence


def test_valid_packet_references_current_captured_sources(captured_packet):
    packet, evidence = captured_packet
    result = validate_packet(packet, evidence)
    assert result["status"] == "valid"
    assert result["word_count"] > 0
    assert result["warnings"]  # Concision is guidance, not fabricated validity.
    assert "Scheduling Backend" in render_markdown(packet)
    assert "app/service.py:1–3" in render_markdown(packet)


@pytest.mark.parametrize("kind", ["code", "knowledge"])
def test_uncaptured_evidence_is_not_allowed(captured_packet, kind):
    packet, evidence = captured_packet
    evidence["code_files" if kind == "code" else "documents"] = {}
    assert validate_packet(packet, evidence)["status"] == "invalid"


@pytest.mark.parametrize("source", ["../service.py", "/tmp/service.py", "app/../app/service.py", "app\\service.py", "app//service.py", "./app/service.py"])
def test_non_normalized_paths_are_rejected(captured_packet, source):
    packet, evidence = captured_packet
    packet["citations"][0]["source"] = source
    assert validate_packet(packet, evidence)["status"] == "invalid"


def test_code_change_invalidates_captured_evidence(captured_packet):
    packet, evidence = captured_packet
    from pathlib import Path
    Path(evidence["repo_root"], "app/service.py").write_text("def save_schedule(payload): return None\n")
    errors = validate_packet(packet, evidence)["errors"]
    assert any("differs from the captured evidence" in error for error in errors)


def test_symlink_code_is_rejected_even_when_target_is_inside_repo(captured_packet):
    packet, evidence = captured_packet
    from pathlib import Path
    root = Path(evidence["repo_root"])
    path = root / "app/service.py"
    moved = root / "app/real_service.py"
    path.rename(moved)
    path.symlink_to(moved)
    assert validate_packet(packet, evidence)["status"] == "invalid"


@pytest.mark.parametrize("start,end", [(0, 1), (2, 1), (1, 99), (True, 3)])
def test_invalid_line_bounds_are_rejected(captured_packet, start, end):
    packet, evidence = captured_packet
    packet["citations"][0].update(line_start=start, line_end=end)
    assert validate_packet(packet, evidence)["status"] == "invalid"


def test_excerpt_must_come_from_claimed_lines(captured_packet):
    packet, evidence = captured_packet
    packet["citations"][1]["excerpt"] = "Owner: Billing Backend"
    assert any("excerpt does not match" in error for error in validate_packet(packet, evidence)["errors"])


def test_excerpt_whitespace_can_be_normalized(captured_packet):
    packet, evidence = captured_packet
    packet["citations"][0]["excerpt"] = "def save_schedule(payload): maximum_zones = resolve() return persist(payload)"
    assert validate_packet(packet, evidence)["status"] == "valid"


@pytest.mark.parametrize("spans,valid", [([[1, 1], [2, 3]], True), ([[1, 1], [3, 3]], False), ([[1, 2]], False), ([], False)])
def test_only_actual_read_lines_can_be_cited(captured_packet, spans, valid):
    packet, evidence = captured_packet
    evidence["code_spans"]["app/service.py"] = spans
    result = validate_packet(packet, evidence)
    assert (result["status"] == "valid") is valid


def test_starting_file_requires_its_own_covering_code_reference(captured_packet):
    packet, evidence = captured_packet
    packet["starting_files"][0]["citations"] = ["D1"]
    assert any("covering its starting lines" in error for error in validate_packet(packet, evidence)["errors"])


def test_unknown_reference_and_duplicate_id_are_rejected(captured_packet):
    packet, evidence = captured_packet
    packet["owner"]["citations"] = ["D99"]
    assert any("unknown citation" in error for error in validate_packet(packet, evidence)["errors"])
    packet["citations"].append(deepcopy(packet["citations"][0]))
    assert any("duplicate identifier" in error for error in validate_packet(packet, evidence)["errors"])


def test_owner_must_have_evidence_or_be_explicitly_unknown(captured_packet):
    packet, evidence = captured_packet
    packet["owner"]["citations"] = []
    assert validate_packet(packet, evidence)["status"] == "invalid"
    packet["owner"]["text"] = "Unknown: the retrieved material does not establish an owner."
    assert validate_packet(packet, evidence)["status"] == "valid"


def test_summary_requires_inspectable_citation_ids(captured_packet):
    packet, evidence = captured_packet
    assert "[T1]" in render_markdown(packet).split("## Likely subsystem")[0]
    packet["summary_citations"] = []
    assert validate_packet(packet, evidence)["status"] == "invalid"
    packet["summary_citations"] = ["INVENTED"]
    assert any("summary: unknown citation" in error for error in validate_packet(packet, evidence)["errors"])


def test_schema_limits_files_and_rejects_unexpected_fields(captured_packet):
    packet, evidence = captured_packet
    packet["starting_files"] *= 4
    packet["invented_owner"] = "Ishaan"
    assert validate_packet(packet, evidence)["status"] == "invalid"


@pytest.mark.parametrize("bad", [None, [], {"owner": None}, {"citations": [object()]}])
def test_malformed_packets_return_errors_without_crashing(captured_packet, bad):
    _, evidence = captured_packet
    assert validate_packet(bad, evidence)["status"] == "invalid"


def test_oversized_narrative_is_flagged_and_not_silently_trimmed(captured_packet):
    packet, evidence = captured_packet
    packet["summary"] = " ".join(["investigation"] * 350)
    # Stay within the per-field display limit while crossing the word target.
    packet["summary"] = " ".join(["word"] * 350)
    result = validate_packet(packet, evidence)
    assert result["status"] == "valid"
    assert any("No text was truncated" in warning for warning in result["warnings"])
    assert packet["summary"] in render_markdown(packet)


def test_saved_runs_are_unique_and_record_validation(captured_packet, tmp_path):
    packet, evidence = captured_packet
    metadata = {"status": "success", "mode": "hybrid", "model": "test-model"}
    first = save_run(tmp_path / "runs", packet, evidence, metadata, [{"type": "read"}])
    second = save_run(tmp_path / "runs", packet, evidence, metadata, "{\"type\":\"read\"}\n")
    assert first != second
    saved = json.loads((first / "metadata.json").read_text())
    assert saved["validation"]["status"] == "valid"
    assert saved["claim_review"] == "pending"
    assert saved["status"] == "success"
    assert json.loads((first / "trace.jsonl").read_text())["type"] == "read"


def test_invalid_saved_output_cannot_remain_success(captured_packet, tmp_path):
    packet, evidence = captured_packet
    packet["owner"]["citations"] = []
    run = save_run(tmp_path / "runs", packet, evidence, {"status": "success"}, [])
    saved = json.loads((run / "metadata.json").read_text())
    assert saved["status"] == "partial"
    assert "Context packet unavailable" in (run / "packet.md").read_text()
    assert json.loads((run / "packet.json").read_text()) == packet


def test_failure_remains_failure_even_with_valid_packet(captured_packet, tmp_path):
    packet, evidence = captured_packet
    run = save_run(tmp_path / "runs", packet, evidence, {"status": "failed"}, [])
    assert json.loads((run / "metadata.json").read_text())["status"] == "failed"


def test_failure_can_be_saved_without_a_packet(captured_packet, tmp_path):
    _, evidence = captured_packet
    run = save_run(tmp_path / "runs", None, evidence, {"status": "timeout"}, [])
    assert json.loads((run / "metadata.json").read_text())["status"] == "timeout"
    assert json.loads((run / "packet.json").read_text()) is None
