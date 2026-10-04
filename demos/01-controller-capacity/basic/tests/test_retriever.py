from pathlib import Path

import pytest

from retriever import EngineeringRetriever, SemanticUnavailable, get_ticket, load_documents, search_knowledge


def test_manifest_contains_only_six_synthetic_organizational_sources():
    documents = load_documents()
    assert len(documents) == 6
    assert {doc["id"] for doc in documents} == {
        "AG-1423", "AG-981", "controller-limits", "scheduling-architecture", "INC-331", "PR-719"
    }
    assert all(doc["source"].startswith("knowledge/") for doc in documents)
    assert all("Synthetic demonstration fixture" in doc["text"] for doc in documents)


@pytest.mark.parametrize("query, expected", [
    ("What is the maximum number of zones for a Pro controller?", "controller-limits"),
    ("Who owns backend scheduling validation and what is the architecture?", "scheduling-architecture"),
    ("Has this issue happened to customers before?", "INC-331"),
])
def test_focused_questions_find_the_primary_source(query, expected):
    response = search_knowledge(query)
    assert response["status"] == "ok"
    assert response["results"][0]["id"] == expected


def test_bug_and_prior_change_queries_surface_both_present_and_historical_evidence():
    bug = search_knowledge("Why do Pro controllers fail when schedules have more than 20 zones?")
    assert "INC-331" in {result["id"] for result in bug["results"][:3]}
    history = search_knowledge("Was anything previously changed for Pro controller capacity?")
    assert {result["id"] for result in history["results"][:2]} == {"AG-981", "PR-719"}


@pytest.mark.parametrize("query", [
    "Does this system support quantum banana synchronization?",
    "How do payroll tax withholding rules work?",
    "the and of",
])
def test_irrelevant_or_stopword_only_queries_abstain(query):
    response = search_knowledge(query)
    assert response["status"] == "no_results"
    assert response["results"] == []


def test_citations_are_exact_text_from_real_line_spans():
    root = Path(__file__).resolve().parents[1]
    response = search_knowledge("Pro controller maximum zones")
    for result in response["results"]:
        assert result["citations"]
        lines = (root / result["source"]).read_text().splitlines()
        for citation in result["citations"]:
            assert citation["source"] == result["source"]
            assert "\n".join(lines[citation["line_start"] - 1:citation["line_end"]]) == citation["text"]


def test_exact_ticket_returns_known_id_and_abstains_for_missing_id():
    ticket = get_ticket("AG-1423")
    assert ticket["status"] == "ok"
    assert ticket["source"] == "knowledge/jira/AG-1423.md"
    assert "The editor accepts the schedule, but saving returns an error." in ticket["content"]
    assert "20" not in ticket["content"] and "50" not in ticket["content"]
    assert ticket["citations"]
    assert get_ticket("AG-9999")["status"] == "not_found"


@pytest.mark.parametrize("ticket_id", ["../confluence/controller-limits", "../../pyproject", "/etc/passwd", "AG-1423.md", "ag-1423", "AG-1423/.."])
def test_exact_ticket_rejects_paths_and_nonexact_ids(ticket_id):
    response = get_ticket(ticket_id)
    assert response["status"] == "invalid_request"
    assert "content" not in response


@pytest.mark.parametrize("kwargs", [{"top_k": 0}, {"top_k": 7}, {"top_k": True}, {"mode": "fake-semantic"}])
def test_invalid_search_options_are_explicit(kwargs):
    response = search_knowledge("Pro controller capacity", **kwargs)
    assert response["status"] == "invalid_request"
    assert response["results"] == []


def test_bm25_never_loads_the_optional_model(monkeypatch):
    retriever = EngineeringRetriever()

    def forbidden_load(query):
        raise AssertionError("BM25 must not request embeddings")

    monkeypatch.setattr(retriever, "_semantic_scores", forbidden_load)
    assert retriever.search("Pro controller capacity")["status"] == "ok"


@pytest.mark.parametrize("mode", ["semantic", "hybrid"])
def test_missing_embedding_model_does_not_silently_fall_back(monkeypatch, mode):
    retriever = EngineeringRetriever()

    def unavailable(query):
        raise SemanticUnavailable("Test model is unavailable")

    monkeypatch.setattr(retriever, "_semantic_scores", unavailable)
    response = retriever.search("Pro controller capacity", mode=mode)
    assert response["status"] == "unavailable"
    assert response["mode"] == mode
    assert response["results"] == []


def test_semantic_relevance_and_rrf_orchestration(monkeypatch):
    # Fixed injected scores test mode logic, not embedding quality. Actual MiniLM
    # quality is checked separately after explicitly preparing its real weights.
    retriever = EngineeringRetriever()
    scores = [0.15, 0.72, 0.45, 0.10, 0.20, 0.78]
    monkeypatch.setattr(retriever, "_semantic_scores", lambda query: scores)
    semantic = retriever.search("previous Pro controller capacity changes", mode="semantic")
    assert semantic["results"][0]["id"] == "PR-719"
    assert len(semantic["results"]) == 3
    assert all(item["score_kind"] == "cosine_similarity" for item in semantic["results"])
    hybrid = retriever.search("previous Pro controller capacity changes", mode="hybrid")
    assert hybrid["results"][0]["id"] == "PR-719"
    assert all(item["score_kind"] == "reciprocal_rank_fusion" for item in hybrid["results"])
    monkeypatch.setattr(retriever, "_semantic_scores", lambda query: [0.1] * 6)
    assert retriever.search("quantum banana", mode="semantic")["status"] == "no_results"
