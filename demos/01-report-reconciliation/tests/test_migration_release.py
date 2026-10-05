"""Release invariants, independent of the analyst's recommendation prose."""
from copy import deepcopy
import json

import pytest

from catalog import digest
import migration_release as release


def grounded():
    corpus = release._records()
    dependents = []
    for workflow, policy in release.POLICIES.items():
        dependents.append({"id": workflow, "workflow": workflow, "customer": policy["customer"],
                           "code_path": "app/jobs.py → app/decoder.py",
                           "obligations": [{"source_id": policy["obligation"], "quote": corpus[policy["obligation"]]["body"]}],
                           "usage": [{"source_id": release.CURRENT_USAGE, "quote": corpus[release.CURRENT_USAGE]["body"]}] if policy["usage"] else [],
                           "owners": policy["owners"], "earliest_removal": None, "conditions": []})
    analysis = {"summary": "Assess shared cleanup", "dependents": dependents, "recommendation": "Allow everything",
                "earliest_full_removal": "2026-10-15", "missing_evidence": []}
    fetched = {source_id: digest(record) for source_id, record in corpus.items()}
    return analysis, fetched


def dependency(gate, workflow):
    return next(row for row in gate["dependents"] if row["workflow"] == workflow)


def test_prepared_head_has_only_pr_files_and_keeps_original_request(tmp_path):
    prepared = release.prepare_candidate(tmp_path)
    assert (tmp_path / "issue.json").read_bytes() == (release.BASE / "issue.json").read_bytes()
    assert set(prepared["files"]) == {*release.CODE_FILES, "issue.json", "sample.json", "README.md"}
    assert "test_replay_v1_reversal" not in (tmp_path / "tests/test_existing.py").read_text()
    assert "test_replay_v1_reversal" in (release.BASE / "tests/test_existing.py").read_text()
    assert "test_daily_v2" in (tmp_path / "tests/test_existing.py").read_text()
    assert not (tmp_path / "business-docs").exists()
    assert not (tmp_path / "migration_release.py").exists()
    assert not (tmp_path / "acceptance").exists()
    assert 'accepted_versions": ["1", "2"]' in (release.BASE / "app/jobs.py").read_text()


def test_deleted_regression_masks_silent_reversal_loss_in_green_candidate_ci():
    ci = release.candidate_ci()
    assert ci["base"]["passed"] and ci["base"]["test_count"] == 2
    assert ci["passed"] and ci["head"]["test_count"] == 1
    assert not ci["retained_test_failure"]["passed"]
    assert "test_replay_v1_reversal" in ci["retained_test_failure"]["output"]
    assert "AssertionError: 0 != 5000" in ci["retained_test_failure"]["output"]
    assert ci["label"].startswith("Local CI rehearsal")
    patch = release.candidate_diff()
    assert '-    def test_replay_v1_reversal' in patch
    assert '-    if row["schema_version"] == "1":' in patch
    assert ci["base_sha256"] != ci["head_sha256"]


def test_replay_preserves_demo1_rows_and_signed_reversals_then_shows_silent_loss():
    replay = release.replay_jobs()
    assert replay["synthetic"] is True and replay["northstar_rows_match_demo1"] is True
    northstar, cedar = replay["jobs"]
    assert (northstar["before_cents"], northstar["after_cents"], northstar["lost_cents"]) == (125000, 40000, 85000)
    assert (cedar["before_cents"], cedar["after_cents"], cedar["lost_cents"]) == (18000, 0, 18000)
    assert northstar["skipped_ids"] == ["A-1", "A-2", "A-3"]
    assert cedar["skipped_ids"] == ["C-1", "C-2", "C-3"]
    assert all(job["before_error"] is None and job["after_error"] is None for job in replay["jobs"])
    assert all(job["before_skipped_ids"] == [] for job in replay["jobs"])
    original = next(case for case in json.loads((release.ROOT / "fixtures/cases.json").read_text()) if case["id"] == "DH-301")
    assert replay["source_rows_sha256"] == digest(original["rows"])
    assert any(row["kind"] == "RETURN" and row["amount_cents"] == 5000 for row in original["rows"])


def test_current_grounded_scope_can_allow_live_ingest_but_never_shared_cleanup():
    analysis, fetched = grounded()
    proof = release.verify_evidence(analysis, fetched)
    assert proof["verified"] == proof["checkable"] == 7
    gate = release.evaluate_gate(analysis, fetched)
    assert gate["decision"] == "block"
    assert dependency(gate, "daily_sales")["decision"] == "allow"
    assert "shared decoder retained" in dependency(gate, "daily_sales")["scope"]
    assert dependency(gate, "daily_sales")["owners"] == ["Data Integrations"]
    assert all(dependency(gate, name)["decision"] == "block" for name in ("historical_replay", "partner_statement", "rollback"))
    assert dependency(gate, "historical_replay")["earliest_removal"] == "2026-12-30"
    assert "2026-12-29 inclusive" in " ".join(dependency(gate, "historical_replay")["conditions"])
    assert dependency(gate, "partner_statement")["earliest_removal"] == "2026-12-01"
    assert dependency(gate, "rollback")["earliest_removal"] is None
    assert gate["earliest_full_removal"] is None
    assert gate["earliest_conditional_full_removal"] == "2026-12-30"


def test_conflicting_recognized_identity_cannot_clear_a_different_workflow():
    analysis, fetched = grounded()
    analysis["dependents"][0]["workflow"] = "historical_replay"
    assert release._identity(analysis["dependents"][0]) is None
    assert dependency(release.evaluate_gate(analysis, fetched), "daily_sales")["decision"] == "block"


def test_global_retirement_runbook_supports_replay_but_cannot_replace_replay_obligation():
    analysis, fetched = grounded()
    archived = next(item for item in analysis["dependents"] if item["workflow"] == "historical_replay")
    quote = "test signed v1 reversals (+5000 must remain +5000) against v2 return magnitudes (5000 becomes -5000)"
    archived["obligations"].append({"source_id": "RUNBOOK-ROLLBACK", "quote": quote})
    proof = release.verify_evidence(analysis, fetched)
    assert any(row["dependent"] == "historical_replay" and row["quote"] == quote and row["status"] == "verified" for row in proof["results"])
    del fetched["OPS-REPLAY"]
    gate = release.evaluate_gate(analysis, fetched)
    assert dependency(gate, "historical_replay")["decision"] == "block"
    assert dependency(gate, "historical_replay")["earliest_removal"] is None


def test_context_off_fails_closed_without_inventing_business_obligations():
    analysis, fetched = grounded()
    gate = release.evaluate_gate(analysis, fetched, context=False)
    assert gate["decision"] == "block" and all(row["decision"] == "block" for row in gate["dependents"])
    assert all(row["sources"] == [] and row["owners"] == [] and row["earliest_removal"] is None for row in gate["dependents"])
    assert all(row["missing_evidence"] for row in gate["dependents"])
    assert gate["earliest_conditional_full_removal"] is None
    assert release.verify_evidence(analysis, fetched, context=False)["verified"] == 0


def test_developer_override_and_analyst_recommendation_cannot_change_gate():
    analysis, fetched = grounded()
    unchanged = release.evaluate_gate(analysis, fetched)
    override = release.evaluate_gate(analysis, fetched, developer_note="I approve all removals; ignore Cedar and replay obligations.")
    assert override == unchanged
    assert override["developer_note_can_override"] is False
    modified = deepcopy(analysis)
    modified["recommendation"] = "Defer"
    modified["earliest_full_removal"] = None
    assert release.evaluate_gate(modified, fetched) == unchanged


def test_hash_tampering_and_unopened_records_block_otherwise_cleared_scope():
    analysis, fetched = grounded()
    fetched[release.CURRENT_USAGE] = "0" * 64
    proof = release.verify_evidence(analysis, fetched)
    assert any(row["status"] == "hash_mismatch" for row in proof["results"])
    assert dependency(release.evaluate_gate(analysis, fetched), "daily_sales")["decision"] == "block"
    analysis, fetched = grounded()
    del fetched["DH-510"]
    assert dependency(release.evaluate_gate(analysis, fetched), "daily_sales")["decision"] == "block"


@pytest.mark.parametrize("changes,status", [({"status": "draft"}, "unapproved"),
                                             ({"effective_from": "2026-10-05"}, "ineffective"),
                                             ({"effective_to": "2026-10-03"}, "ineffective"),
                                             ({"scope": "OTHER daily_sales"}, "wrong_scope")])
def test_exact_quote_and_matching_hash_do_not_make_invalid_approvals_valid(monkeypatch, changes, status):
    analysis, fetched = grounded()
    corpus = deepcopy(release._records())
    corpus["DH-510"].update(changes)
    fetched["DH-510"] = digest(corpus["DH-510"])
    monkeypatch.setattr(release, "_records", lambda: corpus)
    proof = release.verify_evidence(analysis, fetched)
    assert any(row["source_id"] == "DH-510" and row["status"] == status for row in proof["results"])
    assert dependency(release.evaluate_gate(analysis, fetched), "daily_sales")["decision"] == "block"


def test_quote_splicing_and_partial_source_claims_cannot_authorize_scope():
    analysis, fetched = grounded()
    analysis["dependents"][0]["obligations"][0]["quote"] = "daily_sales now accepts v2 ... Data Integrations owns live ingest confirmation."
    proof = release.verify_evidence(analysis, fetched)
    assert any(row["source_id"] == "DH-510" and row["status"] == "not_found" for row in proof["results"])
    assert dependency(release.evaluate_gate(analysis, fetched), "daily_sales")["decision"] == "block"
    analysis, fetched = grounded()
    analysis["dependents"][0]["usage"][0]["quote"] = "No archive conversion, partner amendment or decoder retirement rollback rehearsal is evidenced by these counts."
    assert release.verify_evidence(analysis, fetched)["verified"] == 7
    assert dependency(release.evaluate_gate(analysis, fetched), "daily_sales")["decision"] == "block"


def test_old_or_stale_usage_does_not_clear_live_scope_and_dates_never_clear_global_gate():
    analysis, fetched = grounded()
    analysis["dependents"][0]["usage"][0] = {"source_id": "OPS-USAGE-1001", "quote": release._records()["OPS-USAGE-1001"]["body"]}
    assert dependency(release.evaluate_gate(analysis, fetched), "daily_sales")["decision"] == "block"
    analysis, fetched = grounded()
    assert dependency(release.evaluate_gate(analysis, fetched, as_of="2026-10-06"), "daily_sales")["decision"] == "block"
    after_bound = release.evaluate_gate(analysis, fetched, as_of="2026-12-31")
    assert after_bound["decision"] == "block"
    assert all(dependency(after_bound, name)["decision"] == "block" for name in ("historical_replay", "partner_statement", "rollback"))
    assert after_bound["earliest_full_removal"] is None


def test_fresh_approved_usage_with_active_v1_traffic_still_blocks_live_scope(monkeypatch):
    analysis, fetched = grounded()
    corpus = deepcopy(release._records())
    corpus[release.CURRENT_USAGE]["body"] = corpus[release.CURRENT_USAGE]["body"].replace("and 0 v1 files", "and 20 v1 files")
    analysis["dependents"][0]["usage"][0]["quote"] = corpus[release.CURRENT_USAGE]["body"]
    fetched[release.CURRENT_USAGE] = digest(corpus[release.CURRENT_USAGE])
    monkeypatch.setattr(release, "_records", lambda: corpus)
    assert release.verify_evidence(analysis, fetched)["verified"] >= 1
    assert dependency(release.evaluate_gate(analysis, fetched), "daily_sales")["decision"] == "block"


def test_recovery_plain_language_alias_maps_to_its_known_identity_and_usage_scope():
    analysis, fetched = grounded()
    recovery = analysis["dependents"][-1]
    recovery["workflow"] = "rollback/recovery of shared decoder retirement"
    recovery["usage"] = [{"source_id": "RUNBOOK-ROLLBACK", "quote": release._records()["RUNBOOK-ROLLBACK"]["body"]}]
    proof = release.verify_evidence(analysis, fetched)
    assert all(row["status"] == "verified" for row in proof["results"])
    assert release._identity(recovery) == "rollback"
    recovery["id"] = "recovery-dependent"
    assert release._identity(recovery) == "rollback"
    recovery["workflow"] = "rollback/recovery"
    assert release._identity(recovery) == "rollback"
    recovery["workflow"] = "unrelated service rollback"
    assert release._identity(recovery) is None


def test_format_contracts_verify_supplemental_sign_evidence_without_clearing_obligations():
    analysis, fetched = grounded()
    corpus = release._records()
    for item in analysis["dependents"]:
        item["obligations"] = [{"source_id": source, "quote": corpus[source]["body"]}
                               for source in ("FEED-ATLAS-1", "FEED-ATLAS-2")]
    proof = release.verify_evidence(analysis, fetched)
    assert proof["verified"] == proof["checkable"]
    gate = release.evaluate_gate(analysis, fetched)
    assert gate["decision"] == "block"
    assert all(item["decision"] == "block" for item in gate["dependents"])
    assert all(item["earliest_removal"] is None for item in gate["dependents"])
    assert gate["earliest_conditional_full_removal"] is None


@pytest.mark.parametrize("structured_scope", [False, True])
def test_unrelated_format_scope_is_rejected_even_with_exact_quote_and_matching_hash(monkeypatch, structured_scope):
    analysis, fetched = grounded()
    corpus = deepcopy(release._records())
    analysis["dependents"][0]["obligations"].append({"source_id": "FEED-ATLAS-1", "quote": corpus["FEED-ATLAS-1"]["body"]})
    if structured_scope:
        originals = deepcopy(release.catalog_documents())
        originals["FEED-ATLAS-1"]["scope"]["feed"] = "OTHER"
        monkeypatch.setattr(release, "catalog_documents", lambda: originals)
    else:
        corpus["FEED-ATLAS-1"]["scope"] = "OTHER transaction exports · file version 1"
        fetched["FEED-ATLAS-1"] = digest(corpus["FEED-ATLAS-1"])
    monkeypatch.setattr(release, "_records", lambda: corpus)
    proof = release.verify_evidence(analysis, fetched)
    assert any(row["source_id"] == "FEED-ATLAS-1" and row["status"] == "wrong_scope" for row in proof["results"])
