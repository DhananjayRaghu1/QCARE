"""Allowlisted, synthetic connector snapshots. No arbitrary path or network access."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from app.report import contributions

ROOT = Path(__file__).resolve().parent


def digest(value):
    raw = value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _records(filename):
    records = json.loads((ROOT / "fixtures" / filename).read_text())
    indexed = {record["id"]: record for record in records}
    if len(indexed) != len(records):
        raise ValueError("Duplicate source identifier")
    return indexed


def documents():
    return _records("documents.json")


def cases():
    return _records("cases.json")


def get_document(document_id):
    doc = documents().get(document_id)
    if doc is None:
        return {"status": "not_found", "id": document_id}
    return {"status": "ok", "source_id": document_id, "sha256": digest(doc), "document": doc}


def get_case(case_id):
    case = cases().get(case_id)
    if case is None:
        return {"status": "not_found", "id": case_id}
    ledger = contributions(case["rows"], case["month"], case["deployed_config"])
    code = (ROOT / "app/report.py").read_text()
    related = [doc["id"] for doc in documents().values() if doc["system"] == "jira" and
               (doc["scope"].get("customer") == case["customer"] or
                doc["scope"].get("feed") in {row["feed"] for row in case["rows"]})]
    return {"status": "ok", "case": deepcopy(case), "case_sha256": digest(case),
            "related_ticket_ids": related, "reported_total_cents": sum(r["contribution_cents"] for r in ledger),
            "observed_ledger": ledger, "application": {"source_id": "app/report.py", "sha256": digest(code), "content": code}}


def search_knowledge(query, limit=5):
    if not isinstance(query, str) or not query.strip() or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
        return {"status": "invalid_request", "results": []}
    stop = set("a an the and or for of in to is on what how why are our this customer report".split())
    terms = set(re.findall(r"[a-z0-9]+", query.lower())) - stop
    ranked = []
    for doc in documents().values():
        metadata = " ".join([doc["id"], doc["title"], json.dumps(doc["scope"])])
        title_terms = set(re.findall(r"[a-z0-9]+", metadata.lower()))
        body_terms = set(re.findall(r"[a-z0-9]+", doc["body"].lower()))
        score = 3 * len(terms & title_terms) + len(terms & body_terms)
        if score:
            ranked.append({"source_id": doc["id"], "title": doc["title"], "score": score,
                           "status": doc["status"], "scope": doc["scope"],
                           "effective_from": doc["effective_from"], "effective_to": doc["effective_to"],
                           "excerpt": doc["body"][:240]})
    ranked.sort(key=lambda item: (-item["score"], item["source_id"]))
    return {"status": "ok" if ranked else "no_results", "results": ranked[:limit],
            "note": "Lexical ranking, not confidence. Fetch full documents to inspect complete requirements."}


def snapshot_hashes():
    return {"cases": digest(cases()), "documents": digest(documents()),
            "application": digest((ROOT / "app/report.py").read_text())}
