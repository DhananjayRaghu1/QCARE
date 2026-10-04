"""Six-source demo retrieval with honest abstention and optional real embeddings.

BM25 is lexical search, even with case/plural normalization. Semantic/hybrid
modes use the actual MiniLM model; missing dependencies or weights are reported
as unavailable instead of silently changing the mode. Scores are ranking values,
not calibrated probabilities. Source code is deliberately outside this index.
"""

from __future__ import annotations

import argparse
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Plus

ROOT = Path(__file__).resolve().parent
KNOWLEDGE = ROOT / "knowledge"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_CACHE = ROOT / ".models" / "sentence-transformers"
MODES = ("bm25", "semantic", "hybrid")

# Fixed manifest: adding code/files to the repository cannot expand tool access.
SOURCES = {
    "AG-1423": "knowledge/jira/AG-1423.md",
    "AG-981": "knowledge/jira/AG-981.md",
    "controller-limits": "knowledge/confluence/controller-limits.md",
    "scheduling-architecture": "knowledge/confluence/scheduling-architecture.md",
    "INC-331": "knowledge/incidents/INC-331.md",
    "PR-719": "knowledge/prs/PR-719.md",
}
TICKET_IDS = frozenset({"AG-1423", "AG-981"})
STOPWORDS = frozenset(
    "a an and are as at be because been before by can cannot could did do does "
    "for from has have how i in into is it its me more must no not of on or our "
    "should so some than that the their them there these they this to up us use "
    "using was we were what when where which who why will with would you your "
    "system anything happen number synthetic demonstration fixture datahoney record".split()
)
# Inflections and an explicit lexical synonym, not an embedding substitute.
NORMALIZE = {
    "controllers": "controller", "models": "model", "zones": "zone",
    "schedules": "schedule", "scheduling": "schedule", "scheduler": "schedule",
    "supports": "support", "supported": "support",
    "fails": "failure", "fail": "failure", "failures": "failure",
    "customers": "customer", "reports": "report", "responses": "response",
    "capabilities": "capability", "limits": "limit", "limited": "limit",
    "maximum": "limit", "max": "limit", "validator": "validation",
    "changes": "change", "changed": "change", "modified": "change",
    "expanded": "expand", "expanding": "expand", "increased": "increase",
    "updated": "update", "constraints": "constraint",
    "happened": "occur", "occurred": "occur",
}
GENERIC_TERMS = frozenset({"support", "information", "work", "issue", "change"})


def tokenize(text: str) -> list[str]:
    """Keep engineering IDs/HTTP numbers; split CamelCase and normalize words."""
    text = text.replace("Synthetic demonstration fixture. This is not a DataHoney customer record.", "")
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    tokens = re.findall(r"[A-Za-z]+-\d+|[A-Za-z]+|\d+", text.lower())
    return [NORMALIZE.get(token, token) for token in tokens if token not in STOPWORDS]


def load_documents() -> list[dict[str, Any]]:
    """Load the explicit demo manifest, rejecting symlinks and escaped sources."""
    documents = []
    for source_id, relative_path in SOURCES.items():
        path = ROOT / relative_path
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(ROOT)):
            raise ValueError(f"Knowledge source must not be a symlink: {relative_path}")
        if not path.resolve().is_relative_to(KNOWLEDGE.resolve()):
            raise ValueError(f"Knowledge source escapes the index: {relative_path}")
        text = path.read_text(encoding="utf-8")
        documents.append({
            "id": source_id,
            "source": relative_path,
            "title": text.splitlines()[0].lstrip("# "),
            "text": text,
            "synthetic": True,
        })
    return documents


def _paragraphs(document: dict[str, Any]) -> list[dict[str, Any]]:
    lines = document["text"].splitlines()
    spans = []
    start = None
    for index, line in enumerate(lines + [""], start=1):
        if line.strip() and start is None:
            start = index
        elif not line.strip() and start is not None:
            text = "\n".join(lines[start - 1:index - 1])
            if not text.startswith("Synthetic demonstration"):
                spans.append({
                    "source": document["source"],
                    "line_start": start,
                    "line_end": index - 1,
                    "reference": f"{document['source']}:L{start}-L{index - 1}",
                    "text": text,
                })
            start = None
    return spans


def _citations(document: dict[str, Any], query_tokens: list[str] | None = None) -> list[dict[str, Any]]:
    spans = _paragraphs(document)
    if query_tokens is None:
        return spans
    terms = set(query_tokens)
    ranked = sorted(spans, key=lambda span: len(terms & set(tokenize(span["text"]))), reverse=True)
    matches = [span for span in ranked if terms & set(tokenize(span["text"]))]
    # A semantic paraphrase may share no words: cite its full source instead.
    if not matches:
        return spans
    return sorted(matches[:3], key=lambda span: span["line_start"])


class SemanticUnavailable(RuntimeError):
    """The requested real embedding mode cannot currently run."""


class EngineeringRetriever:
    """Small in-memory index. Models/embeddings load only for semantic requests."""

    def __init__(self, *, allow_model_download: bool = False):
        self.documents = load_documents()
        self.by_id = {document["id"]: document for document in self.documents}
        self.tokens = [tokenize(document["text"]) for document in self.documents]
        # Repeating the title twice is a simple title boost. Delta=0 avoids the
        # BM25Plus baseline assigning a nonzero score to unmatched documents.
        corpus = [tokens + 2 * tokenize(doc["title"]) for doc, tokens in zip(self.documents, self.tokens)]
        self.bm25 = BM25Plus(corpus, delta=0)
        self.allow_model_download = allow_model_download
        self._model = None
        self._embeddings = None
        self._semantic_error = None

    def _load_semantic(self) -> None:
        if self._semantic_error:
            raise SemanticUnavailable(self._semantic_error)
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise SemanticUnavailable(
                "Install the semantic extra, then run python retriever.py --prepare-semantic. "
                "BM25 remains available."
            ) from error
        try:
            model = SentenceTransformer(
                MODEL_NAME,
                cache_folder=str(MODEL_CACHE),
                local_files_only=not self.allow_model_download,
                trust_remote_code=False,
            )
            embeddings = model.encode(
                [document["text"] for document in self.documents],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as error:
            self._semantic_error = (
                f"MiniLM could not load ({type(error).__name__}). "
                "Run python retriever.py --prepare-semantic once with network access "
                "to cache the model. BM25 remains available."
            )
            raise SemanticUnavailable(self._semantic_error) from error
        self._model, self._embeddings = model, embeddings

    def _semantic_scores(self, query: str) -> list[float]:
        self._load_semantic()
        embedding = self._model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
        return [float(score) for score in self._embeddings @ embedding]

    def _lexical_candidates(self, query_tokens: list[str]) -> set[int]:
        """Conservative demo heuristic, not a general confidence estimator."""
        terms = set(query_tokens)
        informative = terms - GENERIC_TERMS
        candidates = set()
        for index, tokens in enumerate(self.tokens):
            matched = terms & set(tokens)
            if not matched & informative:
                continue
            if len(matched) >= min(2, len(terms)):
                candidates.add(index)
        return candidates

    def search(self, query: str, top_k: int = 5, mode: str = "bm25") -> dict[str, Any]:
        response: dict[str, Any] = {
            "status": "ok", "query": query, "mode": mode,
            "synthetic": True, "results": [],
        }
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            response.update(status="invalid_request", reason="Query must be a nonempty string of at most 2000 characters.")
            return response
        if mode not in MODES:
            response.update(status="invalid_request", reason=f"Mode must be one of {', '.join(MODES)}.")
            return response
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= len(self.documents):
            response.update(status="invalid_request", reason=f"top_k must be an integer from 1 to {len(self.documents)}.")
            return response
        query_tokens = tokenize(query)
        if not query_tokens:
            response.update(status="no_results", reason="Query contains no searchable terms.")
            return response
        lexical_scores = [float(score) for score in self.bm25.get_scores(query_tokens)]
        lexical_candidates = self._lexical_candidates(query_tokens)
        semantic_scores = None
        if mode != "bm25":
            try:
                semantic_scores = self._semantic_scores(query)
            except SemanticUnavailable as error:
                response.update(status="unavailable", reason=str(error))
                return response
            # Empirical demo threshold, never a probability. The small synthetic
            # corpus is insufficient to calibrate production relevance.
            semantic_candidates = {index for index, score in enumerate(semantic_scores) if score >= 0.40}
        if mode == "bm25":
            candidates = lexical_candidates
            scores = lexical_scores
            score_kind = "bm25"
        elif mode == "semantic":
            candidates = semantic_candidates
            scores = semantic_scores
            score_kind = "cosine_similarity"
        else:
            candidates = lexical_candidates | semantic_candidates
            # Reciprocal rank fusion avoids mixing unrelated raw score scales.
            scores = [0.0] * len(self.documents)
            for ranking_scores, eligible in ((lexical_scores, lexical_candidates), (semantic_scores, semantic_candidates)):
                order = sorted(eligible, key=lambda index: (-ranking_scores[index], self.documents[index]["id"]))
                for rank, index in enumerate(order, start=1):
                    scores[index] += 1.0 / (60 + rank)
            score_kind = "reciprocal_rank_fusion"
        ranked = sorted(candidates, key=lambda index: (-scores[index], self.documents[index]["id"]))
        for index in ranked[:top_k]:
            document = self.documents[index]
            result = {
                "id": document["id"], "source": document["source"],
                "title": document["title"], "score": round(scores[index], 6),
                "score_kind": score_kind, "content": document["text"],
                "synthetic": True,
                "matched_terms": sorted(set(query_tokens) & set(self.tokens[index])),
                "citations": _citations(document, query_tokens),
            }
            if semantic_scores is not None:
                result["semantic_score"] = round(semantic_scores[index], 6)
            response["results"].append(result)
        if not response["results"]:
            response.update(status="no_results", reason="No source passed the demo relevance threshold; try a more specific engineering question.")
        response["relevance_policy"] = (
            "Lexical: at least two matched terms (one for a one-term query), including a non-generic term. "
            "Semantic: cosine similarity >= 0.40. Thresholds are demo heuristics, not confidence probabilities."
        )
        return response

    def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        response: dict[str, Any] = {"status": "not_found", "id": ticket_id, "synthetic": True}
        if not isinstance(ticket_id, str) or not re.fullmatch(r"AG-\d{1,8}", ticket_id):
            response.update(status="invalid_request", reason="Use an exact Jira ID, such as AG-1423.")
            return response
        if ticket_id not in TICKET_IDS:
            response["reason"] = "Ticket is not in the permitted synthetic knowledge index."
            return response
        document = self.by_id[ticket_id]
        response.update(
            status="ok", source=document["source"], title=document["title"],
            content=document["text"], citations=_citations(document),
        )
        return response


@lru_cache(maxsize=1)
def _default_retriever() -> EngineeringRetriever:
    return EngineeringRetriever()


def search_knowledge(query: str, top_k: int = 5, mode: str = "bm25") -> dict[str, Any]:
    return _default_retriever().search(query, top_k, mode)


def get_ticket(ticket_id: str) -> dict[str, Any]:
    return _default_retriever().get_ticket(ticket_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List the six permitted synthetic sources.")
    parser.add_argument("--query", default="Why do Pro controllers fail when schedules have more than 20 zones?")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--mode", choices=MODES, default="bm25")
    parser.add_argument("--prepare-semantic", action="store_true", help="Explicitly download/cache the real MiniLM model.")
    arguments = parser.parse_args()
    if arguments.list:
        for document in load_documents():
            print(f"{document['id']}\t{document['source']}")
        return 0
    retriever = EngineeringRetriever(allow_model_download=arguments.prepare_semantic)
    if arguments.prepare_semantic:
        try:
            retriever._load_semantic()
        except SemanticUnavailable as error:
            print(json.dumps({"status": "unavailable", "reason": str(error)}, indent=2))
            return 2
        print(json.dumps({"status": "ok", "model": MODEL_NAME, "documents_encoded": len(retriever.documents)}))
        return 0
    response = retriever.search(arguments.query, arguments.top_k, arguments.mode)
    print(json.dumps(response, indent=2))
    return 2 if response["status"] in {"invalid_request", "unavailable"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
