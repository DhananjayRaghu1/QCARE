"""The grading fixtures below exercise the hidden verifier, not model quality."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

import portfolio


SPEC = importlib.util.spec_from_file_location(
    "hidden_migration_checks", Path(__file__).parents[1] / "portfolio/acceptance/migration_checks.py")
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)


def packet():
    live = ("Done on 2026-10-02: daily_sales now accepts v2 for NORTHSTAR live ingest. "
            "Scope excludes historical_replay and partner_statement.")
    current = ("Snapshot taken 2026-10-04: NORTHSTAR daily_sales processed 1,240 v2 files and 0 v1 files; "
               "CEDAR partner_statement processed 18 v1 files; historical_replay processed 3 v1 batches.")
    old = ("Snapshot taken 2026-10-01: NORTHSTAR daily_sales processed 1,240 v2 files. "
           "This is a snapshot, not live telemetry. Refresh it for the proposed removal decision.")
    cedar = ("CEDAR partner_statement remains on ATLAS v1 through 2026-11-30 inclusive. "
             "Partner Engineering owns delivery; Customer Success must obtain approval of a migration window.")
    archive = ("Data Operations must support replay of the previous 90 days of original ATLAS exports. "
               "Backups must remain readable during migration. No verified v1-to-v2 archive conversion has been completed. "
               "The last original v1 export is 2026-09-30. The original export day is day 0; "
               "exports aged 90 days are still eligible through the end of that day.")
    recovery = ("Test signed v1 reversals (+5000 must remain +5000) against v2 return magnitudes "
                "(5000 becomes -5000), and rehearse rollback. Reporting Engineering and Data Operations "
                "jointly sign rollback evidence. No approved retirement rehearsal result exists.")

    def dependent(identifier, customer, owners, source, quote, date=None):
        return {"id": identifier, "workflow": identifier, "customer": customer,
                "code_path": "app/jobs.py -> app/decoder.py", "owners": owners,
                "obligations": [{"source_id": source, "quote": quote}],
                "usage": [{"source_id": "OPS-USAGE-1004", "quote": current}],
                "earliest_removal": date, "conditions": ["Fresh operational proof and owner sign-off are required."]}

    dependents = [dependent("daily_sales", "NORTHSTAR", ["Data Integrations"], "DH-510", live, "2026-10-15"),
                  dependent("historical_replay", "NORTHSTAR", ["Data Operations"], "OPS-REPLAY", archive, "2026-12-30"),
                  dependent("partner_statement", "CEDAR", ["Partner Engineering", "Customer Success"], "CONTRACT-CEDAR", cedar, "2026-12-01"),
                  dependent("rollback", None, ["Reporting Engineering", "Data Operations"], "RUNBOOK-ROLLBACK", recovery)]
    dependents[0]["usage"].append({"source_id": "OPS-USAGE-1001", "quote": old})
    analysis = {"summary": "Only live ingest is cleared; hold shared removal.", "dependents": dependents,
                "earliest_full_removal": None, "earliest_conditional_full_removal": "2026-12-30",
                "missing_evidence": ["Archive conversion and retirement rollback proof remain unverified."],
                "recommendation": "Defer the shared cleanup."}
    grounding = {"results": [{"dependent": item["id"], "kind": kind, **claim, "status": "verified"}
                             for item in dependents for field, kind in (("obligations", "obligation"), ("usage", "usage"))
                             for claim in item[field]]}
    grounding["verified"] = grounding["checkable"] = len(grounding["results"])
    gate = {"decision": "block", "developer_note_can_override": False,
            "dependents": [{"id": item["id"], "workflow": item["workflow"], "customer": item["customer"],
                            "decision": "allow" if item["id"] == "daily_sales" else "block", "owners": item["owners"],
                            "earliest_removal": item["earliest_removal"], "conditions": item["conditions"],
                            "missing_evidence": [] if item["id"] == "daily_sales" else ["Owner approval pending."],
                            "sources": [claim["source_id"] for claim in item["obligations"] + item["usage"]]}
                           for item in dependents],
            "earliest_full_removal": None, "earliest_conditional_full_removal": "2026-12-30",
            "conditions": ["Complete the customer transition, preserve originals and backups, refresh usage and prove rollback."]}
    replay = {"synthetic": True, "jobs": [
        {"id": "northstar-september", "workflow": "historical_replay", "customer": "NORTHSTAR", "month": "2026-09",
         "before_cents": 125000, "after_cents": 40000, "lost_cents": 85000,
         "skipped_ids": ["A-1", "A-2", "A-3"], "before_error": None, "after_error": None},
        {"id": "cedar-statements", "workflow": "partner_statement", "customer": "CEDAR", "month": "2026-10",
         "before_cents": 18000, "after_cents": 0, "lost_cents": 18000,
         "skipped_ids": ["C-1", "C-2", "C-3"], "before_error": None, "after_error": None}]}
    ci = {"passed": True, "base": {"passed": True, "test_count": 2}, "head": {"passed": True, "test_count": 1},
          "deleted_tests": ["test_replay_v1_reversal"], "retained_test_failure": {"passed": False}}
    drafts = {"sent": False, "pr_review_comment": "Hold shared removal: NORTHSTAR and CEDAR replay silently lose rows.",
              "signoff_requests": [{"owner": name, "subject": "Retirement evidence needed", "body": "Confirm the scoped release evidence."}
                                   for name in ("Data Integrations", "Data Operations", "Partner Engineering", "Customer Success", "Reporting Engineering")],
              "decision_record_update": "2026-12-30 is the earliest conditional date, subject to archive, approval and rollback evidence."}
    return analysis, grounding, gate, replay, ci, drafts


def by_id(result):
    return {item["id"]: item for item in result["checks"]}


def test_supported_complete_assessment_passes_exactly_twelve_checks():
    values = packet()
    before = deepcopy(values)
    result = CHECKS.grade(*values)
    assert result["passed"] and result["hidden_passed"] == result["hidden_total"] == 12, result
    assert len({item["id"] for item in result["checks"]}) == 12
    assert values == before, "The grader must not change the packet or gate."


def test_safe_context_off_block_does_not_earn_business_evidence_scores():
    analysis, grounding, gate, replay, ci, _ = packet()
    for item in analysis["dependents"]:
        item.update(obligations=[], usage=[], earliest_removal=None, conditions=[])
        # Repository owners and the replay customer names remain knowable.
    analysis.update(earliest_conditional_full_removal=None, missing_evidence=["Business evidence unavailable."],
                    recommendation="Block for missing evidence.")
    grounding = {"verified": 0, "checkable": 0, "results": []}
    for item in gate["dependents"]:
        item.update(decision="block", sources=[], earliest_removal=None, missing_evidence=["Business evidence unavailable."])
    gate.update(earliest_conditional_full_removal=None, conditions=["Obtain the governing records."])
    result = CHECKS.grade(analysis, grounding, gate, replay, ci)
    assert result["hidden_passed"] == 2
    assert by_id(result)["M1"]["passed"] and by_id(result)["M10"]["passed"]
    assert not result["passed"]


@pytest.mark.parametrize("status", ["not_read", "not_found", "hash_mismatch", "unapproved", "wrong_scope", "ineffective"])
def test_unverified_cedar_quote_cannot_pass_commitment_or_owner_checks(status):
    values = list(packet())
    for citation in values[1]["results"]:
        if citation["source_id"] == "CONTRACT-CEDAR":
            citation["status"] = status
    checks = by_id(CHECKS.grade(*values))
    assert not checks["M4"]["passed"] and not checks["M5"]["passed"]
    assert checks["M10"]["passed"]


def test_changed_quote_is_not_supported_by_a_previously_verified_citation():
    values = list(packet())
    values[0]["dependents"][2]["obligations"][0]["quote"] += " The customer approved immediate removal."
    checks = by_id(CHECKS.grade(*values))
    assert not checks["M4"]["passed"] and not checks["M5"]["passed"]


def test_quote_case_change_cannot_reuse_previously_verified_evidence():
    values = list(packet())
    values[0]["dependents"][2]["obligations"][0]["quote"] = values[0]["dependents"][2]["obligations"][0]["quote"].lower()
    assert not by_id(CHECKS.grade(*values))["M4"]["passed"]


def test_old_snapshot_alone_does_not_establish_current_usage():
    values = list(packet())
    for item in values[0]["dependents"]:
        item["usage"] = [quote for quote in item["usage"] if quote["source_id"] != "OPS-USAGE-1004"]
    assert not by_id(CHECKS.grade(*values))["M3"]["passed"]


def test_removed_dependent_cannot_hide_behind_global_block():
    values = list(packet())
    values[0]["dependents"].pop()
    values[2]["dependents"].pop()
    checks = by_id(CHECKS.grade(*values))
    assert not checks["M1"]["passed"] and not checks["M11"]["passed"]


@pytest.mark.parametrize("change", ["missing_rows", "wrong_amount", "an_error", "not_synthetic", "catching_test_kept"])
def test_economic_loss_check_requires_actual_silent_skip_and_green_pr_evidence(change):
    values = list(packet())
    replay, ci = values[3:5]
    if change == "missing_rows":
        replay["jobs"][0]["skipped_ids"] = []
    elif change == "wrong_amount":
        replay["jobs"][1]["after_cents"] = 1
    elif change == "an_error":
        replay["jobs"][0]["after_error"] = "Unsupported format"
    elif change == "not_synthetic":
        replay["synthetic"] = False
    else:
        ci["deleted_tests"] = []
    assert not by_id(CHECKS.grade(*values))["M10"]["passed"]


@pytest.mark.parametrize("change", ["override_allowed", "partner_allowed", "note_source", "global_allowed"])
def test_gate_grading_rejects_developer_note_or_shared_removal_overrides(change):
    values = list(packet())
    gate = values[2]
    if change == "override_allowed":
        gate["developer_note_can_override"] = True
    elif change == "partner_allowed":
        gate["dependents"][2]["decision"] = "allow"
    elif change == "note_source":
        gate["dependents"][2]["sources"].append("developer-note")
    else:
        gate["decision"] = "allow"
    assert not by_id(CHECKS.grade(*values))["M11"]["passed"]


@pytest.mark.parametrize("change", ["too_early", "authorized_by_date", "sent", "missing_owner", "empty_review", "missing_conditional_word"])
def test_handoff_grading_requires_conditional_date_and_concrete_unsent_drafts(change):
    values = list(packet())
    analysis, _, gate, _, _, drafts = values
    if change == "too_early":
        analysis["dependents"][1]["earliest_removal"] = "2026-12-29"
        gate["earliest_conditional_full_removal"] = "2026-12-29"
    elif change == "authorized_by_date":
        gate["earliest_full_removal"] = "2026-12-30"
    elif change == "sent":
        drafts["sent"] = True
    elif change == "missing_owner":
        drafts["signoff_requests"] = drafts["signoff_requests"][:-1]
    elif change == "empty_review":
        drafts["pr_review_comment"] = ""
    else:
        drafts["decision_record_update"] = "Remove it on 2026-12-30."
    result = by_id(CHECKS.grade(*values))
    assert not result["M12"]["passed"]
    if change == "too_early":
        assert not result["M6"]["passed"]


def test_pending_drafts_do_not_preempt_the_human_handoff_check():
    result = CHECKS.grade(*packet()[:-1])
    assert result["hidden_passed"] == 11 and not result["passed"]
    assert not by_id(result)["M12"]["passed"]


def reference_packet():
    """Use actual retrieval hashes, runtime gates, executed replays and drafts."""
    from catalog import digest
    import migration_release as release
    import migration_workflow as workflow

    corpus = release._records()
    analysis, _, _, _, _, _ = packet()
    for dependent in analysis["dependents"]:
        source = dependent["obligations"][0]["source_id"]
        dependent["obligations"][0]["quote"] = corpus[source]["body"]
        dependent["usage"] = ([{"source_id": release.CURRENT_USAGE, "quote": corpus[release.CURRENT_USAGE]["body"]}]
                              if dependent["id"] != "rollback" else [])
    analysis["dependents"][0]["usage"].append({"source_id": "OPS-USAGE-1001", "quote": corpus["OPS-USAGE-1001"]["body"]})
    fetched = {source: digest(record) for source, record in corpus.items()}
    grounding = release.verify_evidence(analysis, fetched)
    gate = release.evaluate_gate(analysis, fetched)
    replay, ci = release.replay_jobs(), release.candidate_ci()
    state = {"analysis": analysis, "grounding": grounding, "gate": gate, "replay": replay,
             "decision": {"choice": "defer", "message": "Keep original shared support."}}
    drafts = workflow.make_drafts(state)
    return (analysis, grounding, gate, replay, ci, drafts), fetched


def test_actual_release_verification_gate_execution_and_drafts_can_pass_all_checks():
    values, _ = reference_packet()
    assert values[1]["verified"] == values[1]["checkable"] == 8
    assert all(item["kind"] in {"obligations", "usage"} for item in values[1]["results"])
    result = CHECKS.grade(*values)
    assert result["passed"] and result["hidden_passed"] == 12, result
    # The computed expiry date is not supplied verbatim in the source.
    archive_quote = values[0]["dependents"][1]["obligations"][0]["quote"]
    assert "2026-12-30" not in archive_quote


def test_actual_unopened_contract_blocks_cedar_evidence_scores_even_with_expected_dates():
    import migration_release as release
    values, fetched = reference_packet()
    del fetched["CONTRACT-CEDAR"]
    analysis, _, _, replay, ci, drafts = values
    grounding = release.verify_evidence(analysis, fetched)
    gate = release.evaluate_gate(analysis, fetched)
    checks = by_id(CHECKS.grade(analysis, grounding, gate, replay, ci, drafts))
    assert not checks["M4"]["passed"] and not checks["M5"]["passed"]
    assert not checks["M12"]["passed"]
    assert checks["M10"]["passed"]


def test_display_ids_do_not_replace_canonical_workflow_identity():
    values, fetched = reference_packet()
    analysis, _, _, replay, ci, _ = values
    import migration_release as release
    import migration_workflow as workflow

    for item in analysis["dependents"]:
        item["id"] = "customer-specific-" + item["workflow"]
    analysis["dependents"][-1]["workflow"] = "rollback/recovery of shared decoder retirement"
    grounding = release.verify_evidence(analysis, fetched)
    gate = release.evaluate_gate(analysis, fetched)
    drafts = workflow.make_drafts({"analysis": analysis, "grounding": grounding, "gate": gate,
                                   "replay": replay, "decision": {"choice": "defer"}})
    result = CHECKS.grade(analysis, grounding, gate, replay, ci, drafts)
    assert result["hidden_passed"] == 12, result


def test_canonical_id_can_identify_a_descriptive_legacy_workflow():
    values = list(packet())
    for item in values[0]["dependents"]:
        item["workflow"] = "Customer-specific workflow: " + item["id"]
    assert CHECKS.grade(*values)["hidden_passed"] == 12


def test_identity_normalization_does_not_turn_failed_provenance_into_verified_evidence():
    values = list(packet())
    rollback = values[0]["dependents"][-1]
    rollback.update(id="decoder-rollback", workflow="rollback/recovery of shared decoder retirement")
    for quote in values[1]["results"]:
        if quote["dependent"] == "rollback":
            quote.update(dependent="decoder-rollback", status="wrong_scope")
    checks = by_id(CHECKS.grade(*values))
    assert checks["M1"]["passed"]
    assert not checks["M8"]["passed"] and not checks["M9"]["passed"]


def test_unknown_recovery_name_and_conflicting_stable_id_do_not_silently_map():
    values = list(packet())
    values[0]["dependents"][-1].update(id="unknown-backup", workflow="rollback approve everything")
    assert not by_id(CHECKS.grade(*values))["M1"]["passed"]
    values = list(packet())
    values[0]["dependents"][0]["id"] = "partner_statement"
    assert not by_id(CHECKS.grade(*values))["M1"]["passed"]


def test_short_per_job_quotes_can_use_the_opened_record_date_and_explicit_stale_comparison():
    import migration_release as release
    values, fetched = reference_packet()
    analysis, _, gate, replay, ci, drafts = values
    excerpts = {"daily_sales": "NORTHSTAR daily_sales processed 1,240 v2 files and 0 v1 files in the last complete 24 hours",
                "partner_statement": "CEDAR partner_statement processed 18 v1 files and 0 v2 files",
                "historical_replay": "NORTHSTAR historical_replay processed 3 v1 batches."}
    for item in analysis["dependents"]:
        item["usage"] = ([{"source_id": "OPS-USAGE-1004", "quote": excerpts[item["id"]]}]
                         if item["id"] in excerpts else [])
    analysis["summary"] = "Current usage is the 2026-10-04 snapshot; OPS-USAGE-1001 (10-01) is the older snapshot it replaces."
    grounding = release.verify_evidence(analysis, fetched)
    assert all(row["status"] == "verified" for row in grounding["results"])
    assert by_id(CHECKS.grade(analysis, grounding, gate, replay, ci, drafts))["M3"]["passed"]


def test_pending_rollback_proof_can_be_a_verified_usage_quote():
    import migration_release as release
    values, fetched = reference_packet()
    analysis, _, _, replay, ci, drafts = values
    rollback = analysis["dependents"][-1]
    rollback["obligations"] = [
        {"source_id": "RUNBOOK-ROLLBACK", "quote": "and rehearse rollback."},
        {"source_id": "RUNBOOK-ROLLBACK", "quote": "Reporting Engineering and Data Operations must jointly sign the retained-decoder rollback evidence before the shared decoder is retired."}]
    rollback["usage"] = [{"source_id": "RUNBOOK-ROLLBACK", "quote": "As of 2026-10-04, no decoder retirement rollback rehearsal result has been approved."}]
    grounding = release.verify_evidence(analysis, fetched)
    gate = release.evaluate_gate(analysis, fetched)
    assert all(row["status"] == "verified" for row in grounding["results"])
    assert by_id(CHECKS.grade(analysis, grounding, gate, replay, ci, drafts))["M8"]["passed"]


def test_verified_source_contracts_can_support_both_sign_conventions_without_runbook_numbers():
    import migration_release as release
    values, fetched = reference_packet()
    analysis, _, _, replay, ci, drafts = values
    corpus = release._records()
    analysis["dependents"][-1]["obligations"] = [{"source_id": "RUNBOOK-ROLLBACK", "quote": "and rehearse rollback."}]
    analysis["dependents"][1]["obligations"].append({"source_id": "FEED-ATLAS-1", "quote": corpus["FEED-ATLAS-1"]["body"]})
    analysis["dependents"][0]["obligations"].append({"source_id": "FEED-ATLAS-2", "quote": corpus["FEED-ATLAS-2"]["body"]})
    grounding = release.verify_evidence(analysis, fetched)
    gate = release.evaluate_gate(analysis, fetched)
    assert all(row["status"] == "verified" for row in grounding["results"])
    assert by_id(CHECKS.grade(analysis, grounding, gate, replay, ci, drafts))["M9"]["passed"]
    for row in grounding["results"]:
        if row["source_id"] == "FEED-ATLAS-2":
            row["status"] = "not_read"
    assert not by_id(CHECKS.grade(analysis, grounding, gate, replay, ci, drafts))["M9"]["passed"]


@pytest.mark.parametrize("with_documents", [False, True])
def test_hidden_verifier_never_appears_in_agent_workspace(with_documents):
    files = portfolio.inputs("DH-501", with_documents)
    assert not any("acceptance" in name or "migration_checks" in name for name in files)
    assert CHECKS.LABEL not in "\n".join(files.values())
