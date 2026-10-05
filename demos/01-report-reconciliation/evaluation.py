"""Fixture acceptance checks and prepared controls, never model-generated evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json

from catalog import ROOT, cases, documents, digest, get_case, snapshot_hashes
from reconcile import reconcile_case

DECISIONS = ["calculation_defect", "configuration_defect", "configuration_and_calculation_defect", "expected_behavior",
             "insufficient_evidence", "conflicting_policy", "invalid_source_data"]

PACKET_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "case_id": {"type": "string"}, "decision": {"type": "string", "enum": DECISIONS},
        "expected_total_cents": {"type": ["integer", "null"]},
        "problem_rows": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "sources": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "explanation": {"type": "string"}, "next_action": {"type": "string"},
    },
    "required": ["case_id", "decision", "expected_total_cents", "problem_rows", "sources", "explanation", "next_action"],
}


def expectations():
    return json.loads((ROOT / "acceptance/expected.json").read_text())


def score(packet, case_id, observed_sources=None):
    expected = expectations()[case_id]
    if not isinstance(packet, dict):
        packet = {}
    sources = packet.get("sources", [])
    rows = packet.get("problem_rows", [])
    source_shape = isinstance(sources, list) and all(isinstance(item, str) for item in sources)
    row_shape = isinstance(rows, list) and all(isinstance(item, str) for item in rows)
    total = packet.get("expected_total_cents")
    checks = {
        "case_id": packet.get("case_id") == case_id,
        "decision": packet.get("decision") == expected["decision"],
        "total": "expected_total_cents" in packet and (total is None or type(total) is int) and total == expected["expected_total_cents"],
        "problem_rows": row_shape and sorted(rows) == sorted(expected["problem_rows"]),
        "required_evidence": source_shape and set(expected["required_sources"]) <= set(sources),
        "known_sources": source_shape and set(sources) <= set(documents()),
        "observed_evidence": source_shape and (observed_sources is None or set(sources) <= set(observed_sources)),
    }
    return {"passed": all(checks.values()), "checks": checks,
            "limit": "Checks fixture decisions, cents, row IDs and evidence IDs; narrative entailment and human review remain separate."}


def arithmetic_control(case, strategy):
    """Simulate the obvious code-level alternatives without claiming they are AI runs."""
    observed = get_case(case["id"])["observed_ledger"]
    ledger = []
    for row, old in zip(case["rows"], observed, strict=True):
        amount = row["amount_cents"]
        amount = -abs(amount) if strategy == "force_returns_negative" and row["kind"] == "RETURN" else (
            -amount if row["kind"] == "RETURN" else amount)
        ledger.append({"row_id": row["id"], "contribution_cents": amount if old["included"] else 0})
    total = sum(row["contribution_cents"] for row in ledger)
    return {"case_id": case["id"], "provenance": "prepared_arithmetic_control", "expected_total_cents": total,
            "problem_rows": [new["row_id"] for new, old in zip(ledger, observed, strict=True)
                             if new["contribution_cents"] != old["contribution_cents"]],
            "decision": "calculation_defect" if any(new["contribution_cents"] != old["contribution_cents"]
                for new, old in zip(ledger, observed, strict=True)) else "expected_behavior", "sources": []}


def run_controls():
    result = {"provenance": "actual_deterministic_test_execution", "agent_runs": 0,
              "recorded_at": datetime.now(timezone.utc).isoformat(), "snapshot_hashes": snapshot_hashes(),
              "oracle_sha256": digest(expectations()), "cases": [], "summary": {}}
    strategies = ("deployed_arithmetic", "force_returns_negative", "policy_workflow")
    expected = expectations()
    for case_id, case in cases().items():
        row = {"case_id": case_id, "title": case["title"], "expected": expected[case_id], "outcomes": {}}
        for strategy in strategies:
            packet = reconcile_case(case, documents()) if strategy == "policy_workflow" else arithmetic_control(case, strategy)
            row["outcomes"][strategy] = {"packet": packet, "acceptance": score(packet, case_id)}
        result["cases"].append(row)
    for strategy in strategies:
        outcomes = [row["outcomes"][strategy]["acceptance"] for row in result["cases"]]
        numeric = [row for row in result["cases"] if row["expected"]["expected_total_cents"] is not None]
        stops = [row for row in result["cases"] if row["expected"]["expected_total_cents"] is None]
        result["summary"][strategy] = {
            "complete_cases": sum(item["passed"] for item in outcomes), "case_count": len(outcomes),
            "correct_decisions": sum(item["checks"]["decision"] for item in outcomes),
            "correct_known_totals": sum(row["outcomes"][strategy]["acceptance"]["checks"]["total"] for row in numeric),
            "known_total_count": len(numeric),
            "correct_stops": sum(row["outcomes"][strategy]["acceptance"]["checks"]["decision"] and
                                 row["outcomes"][strategy]["acceptance"]["checks"]["total"] for row in stops),
            "stop_count": len(stops),
        }
    result["interpretation"] = (
        "Prepared arithmetic controls are not coding-assistant baselines. Ten hand-authored synthetic cases "
        "establish fixture behavior, not general accuracy, AI superiority, human time savings, or productivity. "
        "The policy workflow is deterministic software using structured approved rules; it requires no LLM."
    )
    return result
