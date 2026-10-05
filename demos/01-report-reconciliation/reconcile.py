"""Bounded reconciliation: approved structured rules, integer arithmetic, explicit stops.

These rules are hand-authored fixture contracts. This is not an LLM extraction
system, a general policy interpreter, or proof of any production integration.
"""
from __future__ import annotations

from datetime import date
import re

from app.report import contributions
from catalog import cases, documents, digest


def _active(doc, as_of):
    return (doc["status"] == "approved" and doc["effective_from"] <= as_of
            and (doc["effective_to"] is None or as_of < doc["effective_to"]))


class InvalidSourceData(ValueError):
    def __init__(self, message, rows=()):
        super().__init__(message)
        self.rows = list(rows)


def _validate(case):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", case["month"]):
        raise InvalidSourceData("Invalid reporting month")
    ids = set()
    for row in case["rows"]:
        if row["id"] in ids:
            raise InvalidSourceData("Duplicate row ID; cannot produce unambiguous lineage", [row["id"]])
        ids.add(row["id"])
        if type(row["amount_cents"]) is not int:
            raise InvalidSourceData("amount_cents must be integer cents, not floats or booleans", [row["id"]])
        if row["kind"] not in {"SALE", "RETURN", "TRANSFER"}:
            raise InvalidSourceData("Unrecognized record kind", [row["id"]])
        for field in ("invoice_on", "posted_on"):
            try:
                valid = date.fromisoformat(row[field]).isoformat() == row[field]
            except (ValueError, TypeError, KeyError):
                valid = False
            if not valid:
                raise InvalidSourceData("Invalid date: " + field + " must use a real YYYY-MM-DD date", [row["id"]])


def reconcile_case(case, docs):
    """Return a reproducible evidence packet, never modify the application or inputs."""
    report = {"case_id": case["id"], "provenance": "deterministic_workflow_execution",
              "reported_total_cents": None,
              "customer_claim_cents": case["customer_claim_cents"], "expected_total_cents": None,
              "decision": None, "problem_rows": [], "sources": [], "ledger": [], "messages": [],
              "source_snapshots": {}, "case_sha256": digest(case), "human_review": "pending"}

    def cite(items):
        for doc in items:
            if doc["id"] not in report["sources"]:
                report["sources"].append(doc["id"])
                report["source_snapshots"][doc["id"]] = {"sha256": digest(doc), "document": doc}

    def stop(decision, message):
        report["decision"] = decision
        report["messages"].append(message)
        report["next_action"] = {
            "insufficient_evidence": "Obtain the missing approved contract from the source owner; do not invent a total.",
            "conflicting_policy": "Reporting Product must resolve the conflicting approved definitions before recalculation.",
            "invalid_source_data": "Data Integrations must quarantine the invalid rows and obtain a corrected export.",
        }[decision]
        return report

    try:
        _validate(case)
    except (ValueError, TypeError, KeyError) as error:
        report["problem_rows"] = getattr(error, "rows", [])
        return stop("invalid_source_data", str(error))
    as_of = case["month"] + "-01"
    observed = contributions(case["rows"], case["month"], case["deployed_config"])
    report["reported_total_cents"] = sum(row["contribution_cents"] for row in observed)

    scoped = [doc for doc in docs.values() if doc["kind"] == "report_policy" and
              doc["scope"].get("profile") == case["report_profile"] and
              doc["scope"].get("customer") in {"*", case["customer"]} and
              doc["scope"].get("metric") == case["metric"]]
    policies = [doc for doc in scoped if _active(doc, as_of)]
    if not policies:
        cite(scoped)
        return stop("insufficient_evidence", "No approved, effective policy for the assigned customer reporting profile.")
    cite(policies)
    if len({digest(doc["rules"]) for doc in policies}) != 1:
        return stop("conflicting_policy", "Equally applicable approved reporting documents disagree; recency is not precedence.")
    rules = policies[0]["rules"]
    kinds = rules.get("included_kinds")
    if (rules.get("date_basis") not in {"invoice_on", "posted_on"} or
            not isinstance(kinds, list) or not kinds or
            not all(isinstance(kind, str) and kind in {"SALE", "RETURN", "TRANSFER"} for kind in kinds)):
        return stop("insufficient_evidence", "Approved policy contains an unsupported rule; extend and validate the adapter first.")
    report["policy"] = {"source_id": policies[0]["id"], **rules}

    formats = {}
    for key in sorted({(row["feed"], row["schema_version"]) for row in case["rows"]}):
        candidates = [doc for doc in docs.values() if doc["kind"] == "feed_contract" and
                      (doc["scope"].get("feed"), doc["scope"].get("schema_version")) == key]
        approved = [doc for doc in candidates if _active(doc, as_of)]
        cite(approved or candidates)
        if not approved:
            return stop("insufficient_evidence", f"No approved format contract for {key[0]} schema {key[1]}; a draft does not authorize an interpretation.")
        if len({digest(doc["rules"]) for doc in approved}) != 1:
            return stop("conflicting_policy", f"Approved format contracts disagree for {key}.")
        encoding = approved[0]["rules"].get("encoding")
        if encoding not in {"signed", "magnitude"}:
            return stop("insufficient_evidence", f"Unsupported encoding in {approved[0]['id']}.")
        formats[key] = approved[0]

    # Include relevant pending decisions as evidence, without using them as policy.
    pending = [doc for doc in docs.values() if doc["kind"] == "change_request" and
               doc["scope"].get("customer") == case["customer"] and
               doc["scope"].get("metric") == case["metric"]]
    if any(row["kind"] == "TRANSFER" for row in case["rows"]):
        cite(pending)
        for doc in pending:
            report["messages"].append(f"{doc['id']} is {doc['status']}; it is not an approved reporting amendment.")

    invalid = [row["id"] for row in case["rows"] if
               formats[(row["feed"], row["schema_version"])]["rules"]["encoding"] == "magnitude" and row["amount_cents"] < 0]
    if invalid:
        report["problem_rows"] = invalid
        return stop("invalid_source_data", "Negative magnitudes are invalid; do not silently normalize with abs().")

    for row, actual in zip(case["rows"], observed, strict=True):
        contract = formats[(row["feed"], row["schema_version"])]
        in_period = row[rules["date_basis"]][:7] == case["month"]
        included = in_period and row["kind"] in rules["included_kinds"]
        signed = row["amount_cents"]
        if contract["rules"]["encoding"] == "magnitude" and row["kind"] == "RETURN":
            signed = -signed
        expected = signed if included else 0
        reason = "outside_policy_month" if not in_period else "excluded_record_kind" if not included else "included"
        report["ledger"].append({"row_id": row["id"], "raw_amount_cents": row["amount_cents"],
            "observed_cents": actual["contribution_cents"], "expected_cents": expected,
            "difference_cents": actual["contribution_cents"] - expected, "included": included,
            "reason": reason, "policy_source": policies[0]["id"], "feed_source": contract["id"]})
    report["expected_total_cents"] = sum(row["expected_cents"] for row in report["ledger"])
    report["problem_rows"] = [row["row_id"] for row in report["ledger"] if row["difference_cents"] != 0]
    config_differs = (case["deployed_config"]["date_basis"] != rules["date_basis"] or
                      set(case["deployed_config"]["included_kinds"]) != set(rules["included_kinds"]))
    # Reapply the approved filters to isolate arithmetic errors from selection
    # errors. A settings mismatch must not conceal a sign defect as well.
    with_correct_settings = contributions(case["rows"], case["month"], rules)
    arithmetic_rows = [row["row_id"] for row, actual in zip(report["ledger"], with_correct_settings, strict=True)
                       if row["expected_cents"] != actual["contribution_cents"]]
    report["configuration_mismatch"] = config_differs
    report["calculation_problem_rows"] = arithmetic_rows
    report["problem_rows"] = list(dict.fromkeys(report["problem_rows"] + arithmetic_rows))
    report["decision"] = ("configuration_and_calculation_defect" if config_differs and arithmetic_rows else
                          "configuration_defect" if config_differs else
                          "calculation_defect" if arithmetic_rows else "expected_behavior")
    report["next_action"] = {
        "configuration_and_calculation_defect": "Reporting Engineering must correct the report configuration and the schema-specific sign handling; fixing settings alone will leave incorrect row contributions.",
        "configuration_defect": "Reporting Engineering should update this report configuration to the applicable approved policy and rerun acceptance checks.",
        "calculation_defect": "Reporting Engineering should reproduce the row errors and implement schema-specific normalization; preserve signed reversals.",
        "expected_behavior": "Explain the applicable reporting definition and reconciliation to support; a customer discrepancy alone does not justify changing code.",
    }[report["decision"]]
    report["delta_cents"] = report["reported_total_cents"] - report["expected_total_cents"]
    if report["problem_rows"] and report["delta_cents"] == 0:
        report["messages"].append("The aggregate agrees only because row errors cancel. Matching totals do not prove correct normalization.")
    return report


def reconcile(case_id):
    case = cases().get(case_id)
    if case is None:
        return {"status": "not_found", "id": case_id}
    return {"status": "ok", "report": reconcile_case(case, documents())}
