from copy import deepcopy

import pytest

from catalog import cases, documents, digest, get_document, search_knowledge
from controls.reference_report import contributions
from demo import reproduce, money
from evaluation import expectations, score, run_controls
from reconcile import reconcile_case


@pytest.mark.parametrize("case_id", sorted(cases()))
def test_independent_acceptance_matrix(case_id):
    packet = reconcile_case(cases()[case_id], documents())
    assert score(packet, case_id)["passed"], packet
    assert all(snapshot["sha256"] == digest(snapshot["document"]) for snapshot in packet["source_snapshots"].values())


def test_actual_regression_rejects_both_seed_and_naive_patch():
    result = reproduce()
    assert result["passed"], result
    assert "total_cents=155000" in result["runs"]["seed"]["stdout"]
    assert "total_cents=115000" in result["runs"]["naive"]["stdout"]
    assert "total_cents=125000" in result["runs"]["reference"]["stdout"]


def test_row_errors_cannot_hide_behind_matching_aggregate():
    packet = reconcile_case(cases()["DH-310"], documents())
    assert packet["reported_total_cents"] == packet["expected_total_cents"] == 100000
    assert packet["decision"] == "calculation_defect"
    assert packet["problem_rows"] == ["J-2", "J-3"]
    assert [row["difference_cents"] for row in packet["ledger"]] == [0, 20000, -20000]


def test_missing_contract_is_not_inferred_from_jira_or_sample():
    docs = documents()
    del docs["FEED-ATLAS-1"]
    packet = reconcile_case(cases()["DH-301"], docs)
    assert packet["decision"] == "insufficient_evidence"
    assert packet["expected_total_cents"] is None


def test_customer_addendum_cannot_apply_to_another_customer():
    case = cases()["DH-302"]
    case["customer"] = "NORTHSTAR"
    packet = reconcile_case(case, documents())
    assert packet["decision"] == "insufficient_evidence"
    assert packet["expected_total_cents"] is None


def test_future_policy_does_not_rewrite_a_historical_report():
    packet = reconcile_case(cases()["DH-306"], documents())
    assert packet["expected_total_cents"] == 40000
    assert "REPORT-STD-SEP" in packet["sources"]
    assert "REPORT-STD-OCT" not in packet["sources"]
    packet = reconcile_case(cases()["DH-307"], documents())
    assert packet["decision"] == "configuration_defect"
    assert packet["expected_total_cents"] == 60000
    assert "REPORT-STD-OCT" in packet["sources"]


def test_request_and_draft_do_not_authorize_changes():
    jira = reconcile_case(cases()["DH-303"], documents())
    assert jira["expected_total_cents"] == 80000
    assert "DH-204" in jira["sources"]
    assert "pending_approval" in jira["messages"][0]
    draft = reconcile_case(cases()["DH-304"], documents())
    assert draft["decision"] == "insufficient_evidence"
    assert draft["expected_total_cents"] is None


@pytest.mark.parametrize("invalid", ["invoice_date", None])
def test_unknown_policy_semantics_stop(invalid):
    docs = documents()
    docs["REPORT-STD-SEP"]["rules"]["date_basis"] = invalid
    assert reconcile_case(cases()["DH-301"], docs)["decision"] == "insufficient_evidence"


def test_missing_inclusion_rule_cannot_silently_produce_zero():
    docs = documents()
    del docs["REPORT-STD-SEP"]["rules"]["included_kinds"]
    assert reconcile_case(cases()["DH-301"], docs)["expected_total_cents"] is None


def test_conflicting_format_contract_stops():
    docs = documents()
    conflicting = deepcopy(docs["FEED-ATLAS-1"])
    conflicting.update(id="FEED-CONFLICT", rules={"encoding": "magnitude"})
    docs["FEED-CONFLICT"] = conflicting
    packet = reconcile_case(cases()["DH-301"], docs)
    assert packet["decision"] == "conflicting_policy"
    assert packet["expected_total_cents"] is None


@pytest.mark.parametrize("amount", [True, 1.2, "2000"])
def test_amounts_require_exact_integer_cents(amount):
    case = cases()["DH-301"]
    case["rows"][0]["amount_cents"] = amount
    with pytest.raises(ValueError, match="integer cents"):
        reconcile_case(case, documents())


def test_duplicate_ids_reject_ambiguous_lineage():
    case = cases()["DH-301"]
    case["rows"][1]["id"] = case["rows"][0]["id"]
    with pytest.raises(ValueError, match="Duplicate"):
        reconcile_case(case, documents())


def test_prepared_reference_matches_independent_totals_and_problem_rows():
    for case_id, expected in expectations().items():
        if expected["expected_total_cents"] is None:
            continue
        case = cases()[case_id]
        config = {"date_basis": "invoice_on" if case_id in {"DH-302", "DH-307"} else "posted_on",
                  "included_kinds": ["SALE", "RETURN"]}
        result = contributions(case["rows"], case["month"], config,
                               {("ATLAS", "1"): "signed", ("ATLAS", "2"): "magnitude"})
        assert sum(row["contribution_cents"] for row in result) == expected["expected_total_cents"]
    with pytest.raises(ValueError, match="quarantine"):
        case = cases()["DH-308"]
        contributions(case["rows"], case["month"], case["deployed_config"], {("ATLAS", "2"): "magnitude"})


def test_search_and_exact_source_allowlist():
    assert search_knowledge("schema ATLAS signed")["results"][0]["source_id"] == "FEED-ATLAS-1"
    assert search_knowledge("zzzznomatch")["status"] == "no_results"
    assert search_knowledge("ATLAS", True)["status"] == "invalid_request"
    assert get_document("../../acceptance/expected.json")["status"] == "not_found"


def test_recorded_controls_have_honest_provenance():
    result = run_controls()
    assert result["agent_runs"] == 0
    assert result["summary"]["policy_workflow"]["complete_cases"] == 10
    assert result["summary"]["force_returns_negative"]["correct_known_totals"] == 3
    assert result["summary"]["deployed_arithmetic"]["correct_known_totals"] == 4
    assert "not coding-assistant baselines" in result["interpretation"]


def test_currency_format_avoids_float_rounding():
    assert money(10000000000000001) == "$100,000,000,000,000.01"
    assert money(-1) == "-$0.01"
