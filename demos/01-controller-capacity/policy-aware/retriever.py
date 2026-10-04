"""Read-only evidence retrieval for five explicitly synthetic engineering records.

BM25 is the offline default. Optional hybrid retrieval uses a locally cached
MiniLM model and never downloads weights. Scores rank sources, not confidence.
The index excludes application code, evaluation fixtures, and generated runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Plus

ROOT = Path(__file__).resolve().parent
KNOWLEDGE = ROOT / "knowledge"
SOURCES = {
    "AG-1423": "knowledge/jira/AG-1423.md",
    "AG-1424": "knowledge/jira/AG-1424.md",
    "AG-981": "knowledge/jira/AG-981.md",
    "controller-capacity-policy": "knowledge/confluence/controller-capacity-policy.md",
    "schedule-validation-design": "knowledge/confluence/schedule-validation-design.md",
}
TICKET_IDS = frozenset({"AG-1423", "AG-1424", "AG-981"})
MODES = ("bm25", "hybrid")
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
STOPWORDS = frozenset(
    "a an and are as at be because been before by can cannot could did do does "
    "for from has have how i in into is it its me must no not of on or our "
    "should so than that the their them there these they this to up us use "
    "using was we were what when where which who why will with would you your "
    "synthetic demonstration fixture data honey customer record".split()
)
NORMALIZE = {
    "controllers": "controller", "zones": "zone", "schedules": "schedule",
    "scheduling": "schedule", "models": "model", "versions": "version",
    "limits": "limit", "maximum": "limit", "max": "limit",
    "eligible": "eligibility", "validation": "validate", "validator": "validate",
    "requests": "request", "requirements": "requirement", "rules": "rule",
    "errors": "error", "rejects": "reject", "rejected": "reject",
    "owns": "owner", "ownership": "owner", "metadata": "metadata",
}
GENERIC_TERMS = frozenset({"support", "information", "work", "issue", "change", "system"})


def tokenize(text: str) -> list[str]:
    terms = re.findall(r"[A-Za-z]+-\d+|\d+\.\d+\.\d+|[A-Za-z]+|\d+", text.lower())
    return [NORMALIZE.get(term, term) for term in terms if term not in STOPWORDS]


def numbered_content(content: str) -> str:
    return "\n".join(f"{number}: {line}" for number, line in enumerate(content.splitlines(), 1))


def _safe_knowledge_path(relative: str) -> Path:
    path = ROOT / relative
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(ROOT)):
        raise ValueError("Knowledge sources cannot be symlinks.")
    if not path.resolve().is_relative_to(KNOWLEDGE.resolve()):
        raise ValueError("Knowledge source escaped the fixed index.")
    return path


def _section_spans(content: str) -> dict[str, dict[str, int]]:
    lines = content.splitlines()
    headings = [(index, line[3:].strip()) for index, line in enumerate(lines, 1) if line.startswith("## ")]
    spans = {"metadata": {"line_start": 1, "line_end": headings[0][0] - 1 if headings else len(lines)}}
    for position, (start, heading) in enumerate(headings):
        identifier = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
        if identifier in spans:
            raise ValueError("Document sections must have unique stable IDs.")
        end = headings[position + 1][0] - 1 if position + 1 < len(headings) else len(lines)
        while end > start and not lines[end - 1].strip():
            end -= 1
        spans[identifier] = {"line_start": start, "line_end": end}
    return spans


def load_documents() -> list[dict[str, Any]]:
    documents = []
    for document_id, source in SOURCES.items():
        content = _safe_knowledge_path(source).read_text(encoding="utf-8")
        metadata = {}
        for key, value in re.findall(r"^([A-Za-z ]+): (.+)$", content, re.MULTILINE):
            metadata[key.lower().replace(" ", "_")] = value
        if metadata.get("document_id") != document_id:
            raise ValueError("Document ID disagrees with the manifest.")
        for required in ("version", "status", "owner", "updated"):
            if required not in metadata:
                raise ValueError(f"Document {document_id} is missing {required} metadata.")
        metadata["synthetic"] = True
        documents.append({
            "status": "ok", "id": document_id, "document_id": document_id,
            "title": content.splitlines()[0].lstrip("# "), "source": source,
            "metadata": metadata, "synthetic": True, "content": content,
            "numbered_content": numbered_content(content), "sections": _section_spans(content),
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })
    return documents


class SemanticUnavailable(RuntimeError):
    """An explicitly requested cached embedding mode is unavailable."""


class EngineeringRetriever:
    def __init__(self) -> None:
        self.documents = load_documents()
        self.by_id = {document["document_id"]: document for document in self.documents}
        self.tokens = [tokenize(document["content"]) for document in self.documents]
        self.bm25 = BM25Plus([
            tokens + 2 * tokenize(document["title"])
            for document, tokens in zip(self.documents, self.tokens)
        ], delta=0)
        self._model = None
        self._embeddings = None

    def _semantic_scores(self, query: str) -> list[float]:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                model_cache = Path(os.environ.get("POLICY_DEMO_MODEL_CACHE", str(ROOT / ".models")))
                self._model = SentenceTransformer(
                    MODEL_NAME, cache_folder=str(model_cache), local_files_only=True,
                    trust_remote_code=False,
                )
                self._embeddings = self._model.encode(
                    [document["content"] for document in self.documents],
                    normalize_embeddings=True, show_progress_bar=False,
                )
            except Exception as error:
                self._model = None
                self._embeddings = None
                raise SemanticUnavailable(
                    f"Cached MiniLM is unavailable ({type(error).__name__}). "
                    "Install the semantic extra and provide cached weights; BM25 remains available. "
                    "No weights were downloaded."
                ) from error
        try:
            embedding = self._model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
            return [float(score) for score in self._embeddings @ embedding]
        except Exception as error:
            raise SemanticUnavailable(f"Cached MiniLM query failed ({type(error).__name__}).") from error

    def _excerpts(self, document: dict[str, Any], terms: set[str]) -> list[dict[str, Any]]:
        lines = document["content"].splitlines()
        spans = []
        for section_id, span in document["sections"].items():
            if section_id == "metadata":
                continue
            content = "\n".join(lines[span["line_start"] - 1:span["line_end"]])
            spans.append((len(terms & set(tokenize(content))), {
                "section_id": section_id, **span, "text": content,
            }))
        ranked = sorted(spans, key=lambda item: (-item[0], item[1]["line_start"]))
        selected = [item[1] for item in ranked if item[0] > 0][:2]
        # A semantic-only match still exposes an exact, limited excerpt.
        return selected or [item[1] for item in ranked[:1]]

    def search(self, query: str, top_k: int = 3, mode: str = "bm25") -> dict[str, Any]:
        response = {"status": "ok", "query": query, "mode": mode, "synthetic": True, "results": []}
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            return {**response, "status": "invalid_request", "reason": "Use a nonempty query of at most 2000 characters."}
        if mode not in MODES:
            return {**response, "status": "invalid_request", "reason": "Mode must be bm25 or hybrid."}
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 5:
            return {**response, "status": "invalid_request", "reason": "top_k must be an integer from 1 to 5."}
        tokens = tokenize(query)
        terms = set(tokens)
        if not terms:
            return {**response, "status": "no_results", "reason": "Query contains no searchable terms."}
        scores = [float(score) for score in self.bm25.get_scores(tokens)]
        candidates = {
            index for index, document_tokens in enumerate(self.tokens)
            if len(terms & set(document_tokens)) >= min(2, len(terms))
            and (terms - GENERIC_TERMS) & set(document_tokens)
        }
        score_kind = "bm25"
        if mode == "hybrid":
            try:
                semantic = self._semantic_scores(query)
            except SemanticUnavailable as error:
                return {**response, "status": "unavailable", "reason": str(error)}
            semantic_candidates = {index for index, value in enumerate(semantic) if value >= 0.40}
            fused = [0.0] * len(self.documents)
            for values, eligible in ((scores, candidates), (semantic, semantic_candidates)):
                ranked = sorted(eligible, key=lambda index: (-values[index], self.documents[index]["document_id"]))
                for rank, index in enumerate(ranked, 1):
                    fused[index] += 1 / (60 + rank)
            candidates |= semantic_candidates
            scores, score_kind = fused, "reciprocal_rank_fusion"
        order = sorted(candidates, key=lambda index: (-scores[index], self.documents[index]["document_id"]))
        for index in order[:top_k]:
            document = self.documents[index]
            response["results"].append({
                "id": document["document_id"], "document_id": document["document_id"],
                "title": document["title"], "source": document["source"],
                "metadata": document["metadata"], "excerpts": self._excerpts(document, terms),
                "score": round(scores[index], 6), "score_kind": score_kind,
            })
        response["relevance_policy"] = (
            "BM25: two matched terms, or one for a one-term query, with a non-generic term. "
            "Hybrid also admits cosine similarity >= 0.40 and combines ranks. "
            "These are demo relevance heuristics, not confidence probabilities."
        )
        if not response["results"]:
            response.update(status="no_results", reason="No indexed source met the demo relevance threshold.")
        return response


@lru_cache(maxsize=2)
def _cached_retriever(fingerprint: tuple[tuple[str, int, int], ...]) -> EngineeringRetriever:
    return EngineeringRetriever()


def _default_retriever() -> EngineeringRetriever:
    fingerprint = tuple((source, (path := _safe_knowledge_path(source)).stat().st_mtime_ns, path.stat().st_size) for source in SOURCES.values())
    return _cached_retriever(fingerprint)


def _read_document(document_id: str) -> dict[str, Any]:
    if not isinstance(document_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,100}", document_id):
        return {"status": "invalid_request", "reason": "Use a document ID, not a path.", "synthetic": True}
    if document_id not in SOURCES:
        return {"status": "not_found", "document_id": document_id, "reason": "Document is outside the five-record manifest.", "synthetic": True}
    try:
        return next(document for document in load_documents() if document["document_id"] == document_id)
    except (OSError, ValueError, UnicodeError) as error:
        return {"status": "unavailable", "document_id": document_id, "reason": f"Knowledge could not be read ({type(error).__name__}).", "synthetic": True}


def get_document(document_id: str) -> dict[str, Any]:
    return _read_document(document_id)


def get_ticket(ticket_id: str) -> dict[str, Any]:
    if not isinstance(ticket_id, str) or not re.fullmatch(r"AG-\d{1,8}", ticket_id):
        return {"status": "invalid_request", "reason": "Use an exact Jira ID, such as AG-1423.", "synthetic": True}
    if ticket_id not in TICKET_IDS:
        return {"status": "not_found", "ticket_id": ticket_id, "reason": "Ticket is outside the permitted manifest.", "synthetic": True}
    document = _read_document(ticket_id)
    if document["status"] != "ok":
        return {**document, "ticket_id": ticket_id}
    return {**document, "ticket_id": ticket_id, "body": document["content"], "updated_date": document["metadata"]["updated"]}


def search_knowledge(query: str, top_k: int = 3, mode: str = "bm25") -> dict[str, Any]:
    try:
        return _default_retriever().search(query, top_k, mode)
    except (OSError, ValueError, UnicodeError) as error:
        return {"status": "unavailable", "reason": f"Knowledge index unavailable ({type(error).__name__}).", "results": [], "synthetic": True}


def validate_registry_path(registry_path: Path | str) -> Path:
    """Only a fixed, locally configured app/devices.json is ever exposed.

    MCP callers cannot choose this path. CLI configuration can select a prepared
    workspace, including a temporary test workspace. Symlink files or app dirs
    are rejected instead of following them to another data source.
    """
    path = Path(registry_path).absolute()
    if path.name != "devices.json" or path.parent.name != "app":
        raise ValueError("Registry must be a configured app/devices.json file.")
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Registry file and app directory cannot be symlinks.")
    if path.is_relative_to(ROOT) and any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(ROOT)):
        raise ValueError("Registry workspace cannot contain symlinks.")
    return path


def _record_span(content: str, controller_id: str) -> tuple[int, int, dict[str, dict[str, int]]]:
    lines = content.splitlines()
    match = re.search(r'^\s*"' + re.escape(controller_id) + r'"\s*:\s*\{', content, re.MULTILINE)
    if match is None:
        # Valid compact JSON also has exact evidence, spanning its single line.
        match = re.search(r'"' + re.escape(controller_id) + r'"\s*:\s*\{', content)
    if match is None:
        raise ValueError("Registry record cannot be located in source text.")
    opening = content.index("{", match.start())
    depth, in_string, escaped = 0, False, False
    closing = None
    for offset, char in enumerate(content[opening:], opening):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                closing = offset
                break
    if closing is None:
        raise ValueError("Registry record is incomplete.")
    start = content[:match.start()].count("\n") + 1
    end = content[:closing].count("\n") + 1
    fields = {}
    for field in ("model", "firmware"):
        for number in range(start, end + 1):
            if re.search(r'"' + field + r'"\s*:', lines[number - 1]):
                fields[field] = {"line_start": number, "line_end": number}
                break
    return start, end, fields


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Registry cannot contain duplicate JSON keys.")
        result[key] = value
    return result


def get_device(controller_id: str, registry_path: Path | str | None = None) -> dict[str, Any]:
    base = {"controller_id": controller_id, "synthetic": True}
    if not isinstance(controller_id, str) or not re.fullmatch(r"DEV-\d{1,8}", controller_id):
        return {**base, "status": "invalid_request", "reason": "Use an exact controller ID, such as DEV-101."}
    try:
        path = validate_registry_path(registry_path or ROOT / "seed" / "app" / "devices.json")
        content = path.read_text(encoding="utf-8")
        records = json.loads(content, object_pairs_hook=_unique_object)
        if not isinstance(records, dict) or any(not isinstance(value, dict) for value in records.values()):
            raise ValueError("Registry must be an object of device records.")
        if controller_id not in records:
            return {**base, "status": "not_found", "reason": "Controller is not in the configured device registry."}
        start, end, fields = _record_span(content, controller_id)
        return {
            **base, "id": controller_id, "status": "ok", "record": records[controller_id],
            "source": "app/devices.json", "content": content,
            "numbered_content": numbered_content(content), "line_start": start, "line_end": end,
            "field_references": fields, "registry_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
    except (OSError, ValueError, UnicodeError) as error:
        return {**base, "status": "unavailable", "reason": f"Configured registry unavailable ({type(error).__name__})."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="Pro controller firmware capacity policy")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--mode", choices=MODES, default="bm25")
    parser.add_argument("--list", action="store_true")
    arguments = parser.parse_args()
    result = {"sources": SOURCES, "synthetic": True} if arguments.list else search_knowledge(arguments.query, arguments.top_k, arguments.mode)
    print(json.dumps(result, indent=2))
    return 2 if result.get("status") in {"invalid_request", "unavailable"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
