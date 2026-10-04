"""Evidence-boundary tests: real ranking, exact provenance, and registry isolation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import retriever


def registry(tmp_path: Path, records: dict | None = None) -> Path:
    path = tmp_path / "workspace" / "app" / "devices.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(records or {
        "DEV-101": {"model": "PRO", "firmware": "3.4.0"},
        "DEV-102": {"model": "PRO", "firmware": "3.1.0"},
        "DEV-103": {"model": "LEGACY", "firmware": "1.9.0"},
    }, indent=2) + "\n")
    return path


def test_exact_manifest_and_document_metadata():
    documents = retriever.load_documents()
    assert {doc["document_id"] for doc in documents} == {
        "AG-1423", "AG-1424", "AG-981", "controller-capacity-policy", "schedule-validation-design",
    }
    assert len(documents) == 5
    for document in documents:
        assert document["metadata"]["synthetic"] is True
        assert document["metadata"]["version"] == "1.0"
        assert document["metadata"]["owner"]
        assert document["metadata"]["updated"]
        assert "Synthetic demonstration fixture" in document["content"]
        assert "app/" not in document["source"]


def test_approved_policy_is_complete_and_citable():
    document = retriever.get_document("controller-capacity-policy")
    assert document["status"] == "ok"
    assert document["metadata"]["status"] == "Approved"
    assert document["metadata"]["effective"] == "2026-09-15"
    lines = document["content"].splitlines()
    span = document["sections"]["capacity-rules"]
    excerpt = "\n".join(lines[span["line_start"] - 1:span["line_end"]])
    assert "earlier than 3.2.0" in excerpt
    assert "exactly 3.2.0" in excerpt
    assert "3.10.0 is later than 3.2.0" in excerpt
    assert "LEGACY" in excerpt and "20 zones" in excerpt and "50 zones" in excerpt
    assert document["numbered_content"].splitlines()[span["line_start"] - 1].startswith(f"{span['line_start']}: ")
    assert document["sha256"] == hashlib.sha256(document["content"].encode()).hexdigest()


def test_tickets_are_symptoms_not_embedded_diagnoses():
    for ticket_id, controller_id in (("AG-1423", "DEV-101"), ("AG-1424", "DEV-102")):
        ticket = retriever.get_ticket(ticket_id)
        assert ticket["status"] == "ok"
        assert ticket["ticket_id"] == ticket_id
        assert ticket["body"] == ticket["content"]
        assert controller_id in ticket["content"]
        assert "HTTP 400" in ticket["content"] and "30 zones" in ticket["content"]
        assert "20 zones" in ticket["content"]
        assert "3.2.0" not in ticket["content"] and "50 zones" not in ticket["content"]
        assert "global" not in ticket["content"] and "schedule_validator" not in ticket["content"]


def test_historical_frontend_ticket_does_not_claim_backend_verification():
    document = retriever.get_ticket("AG-981")
    assert document["metadata"]["status"] == "Closed"
    assert "frontend work only" in document["content"]
    assert "Scheduling Backend owns" in document["content"]
    assert "not the authoritative capacity specification" in document["content"]


@pytest.mark.parametrize("query,expected", [
    ("Pro firmware capacity maximum zones 3.2.0", "controller-capacity-policy"),
    ("Schedule validation request flow in-memory repository", "schedule-validation-design"),
    ("DEV-101 30 zones HTTP 400", "AG-1423"),
    ("DEV-102 30 zones HTTP 400", "AG-1424"),
    ("Frontend larger schedule rollout closed", "AG-981"),
])
def test_real_bm25_ranking(query, expected):
    result = retriever.search_knowledge(query)
    assert result["status"] == "ok"
    assert result["results"][0]["document_id"] == expected
    assert all(item["score_kind"] == "bm25" for item in result["results"])
    assert len(result["results"]) <= 3


def test_search_returns_limited_exact_excerpts_without_full_documents():
    result = retriever.search_knowledge("controller firmware capacity policy", top_k=5)
    assert result["status"] == "ok"
    for item in result["results"]:
        assert "content" not in item and "numbered_content" not in item
        assert 1 <= len(item["excerpts"]) <= 2
        document = retriever.get_document(item["document_id"])
        lines = document["content"].splitlines()
        for excerpt in item["excerpts"]:
            assert excerpt["text"] == "\n".join(lines[excerpt["line_start"] - 1:excerpt["line_end"]])
            assert document["sections"][excerpt["section_id"]] == {
                "line_start": excerpt["line_start"], "line_end": excerpt["line_end"],
            }


@pytest.mark.parametrize("query", ["quantum banana synchronization", "the and are", "aardvark"])
def test_unrelated_queries_abstain(query):
    result = retriever.search_knowledge(query)
    assert result["status"] == "no_results" and result["results"] == []


@pytest.mark.parametrize("arguments", [
    {"query": ""}, {"query": " "}, {"query": "x" * 2001}, {"query": None},
    {"query": "capacity", "top_k": 0}, {"query": "capacity", "top_k": 6},
    {"query": "capacity", "top_k": True}, {"query": "capacity", "top_k": 1.5},
    {"query": "capacity", "mode": "invented"},
])
def test_search_rejects_invalid_arguments(arguments):
    assert retriever.search_knowledge(**arguments)["status"] == "invalid_request"


def test_hybrid_unavailable_is_explicit_without_silent_bm25_fallback(monkeypatch):
    index = retriever.EngineeringRetriever()

    def unavailable(query):
        raise retriever.SemanticUnavailable("test: cached weights absent")

    monkeypatch.setattr(index, "_semantic_scores", unavailable)
    result = index.search("controller firmware capacity", mode="hybrid")
    assert result["status"] == "unavailable" and result["results"] == []
    assert "cached weights absent" in result["reason"]
    assert index.search("controller firmware capacity", mode="bm25")["status"] == "ok"


@pytest.mark.parametrize("identifier", ["../../.env", "/etc/passwd", "knowledge/AG-1423.md", "AG-1423\n", "", None])
def test_document_and_ticket_ids_cannot_be_paths(identifier):
    for function in (retriever.get_document, retriever.get_ticket):
        result = function(identifier)
        assert result["status"] == "invalid_request"
        assert "content" not in result


def test_unknown_ids_do_not_expand_manifest():
    assert retriever.get_document("unknown-document")["status"] == "not_found"
    assert retriever.get_ticket("AG-9999")["status"] == "not_found"
    assert retriever.get_ticket("controller-capacity-policy")["status"] == "invalid_request"


def test_registry_lookup_has_exact_source_record_and_hash(tmp_path):
    path = registry(tmp_path)
    device = retriever.get_device("DEV-102", path)
    assert device["status"] == "ok"
    assert device["record"] == {"model": "PRO", "firmware": "3.1.0"}
    assert device["source"] == "app/devices.json"
    content = path.read_text()
    assert device["content"] == content
    assert device["registry_sha256"] == hashlib.sha256(content.encode()).hexdigest()
    lines = content.splitlines()
    excerpt = "\n".join(lines[device["line_start"] - 1:device["line_end"]])
    assert "DEV-102" in excerpt and "3.1.0" in excerpt
    assert "DEV-101" not in excerpt and "DEV-103" not in excerpt
    for field, span in device["field_references"].items():
        assert field in lines[span["line_start"] - 1]


def test_registry_is_read_fresh_and_matches_selected_workspace(tmp_path):
    path = registry(tmp_path)
    initial = retriever.get_device("DEV-101", path)
    data = json.loads(path.read_text())
    data["DEV-101"]["firmware"] = "3.1.0"
    path.write_text(json.dumps(data, indent=2))
    changed = retriever.get_device("DEV-101", path)
    assert changed["record"]["firmware"] == "3.1.0"
    assert changed["registry_sha256"] != initial["registry_sha256"]


def test_registry_missing_fields_are_exposed_as_observed_facts(tmp_path):
    path = registry(tmp_path, {"DEV-101": {"model": "PRO"}})
    device = retriever.get_device("DEV-101", path)
    assert device["status"] == "ok" and "firmware" not in device["record"]
    assert "firmware" not in device["field_references"]


@pytest.mark.parametrize("identifier", ["../../devices", "app/devices.json", "DEV-101\n", "", None])
def test_device_ids_cannot_change_configured_registry(tmp_path, identifier):
    result = retriever.get_device(identifier, registry(tmp_path))
    assert result["status"] == "invalid_request" and "content" not in result


def test_unknown_device_and_missing_registry_are_explicit(tmp_path):
    path = registry(tmp_path)
    assert retriever.get_device("DEV-9999", path)["status"] == "not_found"
    path.unlink()
    assert retriever.get_device("DEV-101", path)["status"] == "unavailable"


def test_duplicate_registry_keys_and_malformed_json_are_rejected(tmp_path):
    path = registry(tmp_path)
    path.write_text('{"DEV-101":{"model":"PRO"},"DEV-101":{"model":"LEGACY"}}')
    assert retriever.get_device("DEV-101", path)["status"] == "unavailable"
    path.write_text("broken JSON")
    assert retriever.get_device("DEV-101", path)["status"] == "unavailable"


def test_symlink_registry_cannot_expose_another_file(tmp_path):
    path = registry(tmp_path)
    other = tmp_path / "private.json"
    other.write_text(path.read_text())
    path.unlink()
    path.symlink_to(other)
    result = retriever.get_device("DEV-101", path)
    assert result["status"] == "unavailable" and "content" not in result


def test_registry_configuration_has_fixed_file_boundary(tmp_path):
    other = tmp_path / "secrets.json"
    other.write_text('{"DEV-101":{"model":"PRO"}}')
    assert retriever.get_device("DEV-101", other)["status"] == "unavailable"
