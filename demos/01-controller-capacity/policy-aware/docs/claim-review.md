# Review of recorded Claude investigation claims

Codex independently reviewed the six final packets below against their saved citation excerpts and captured source spans. The central decisions are correct: AG-1423 justifies investigating a software mismatch; AG-1424 is an expected rejection; the repository-only comparison correctly leaves the business requirement unknown. All six packets also pass the current mechanical provenance validator.

This is an independent Codex review. Human claim review remains pending. Mechanical validity checks authentic excerpts and successful reads; it does not prove that each excerpt supports every statement attached to it. No saved packet, raw run, or review-status metadata was edited during this review.

## Reviewed runs

| Label | Workspace / ticket / context | Run ID |
|---|---|---|
| R1-23 | rehearsal-1 / AG-1423 / tools | `investigate-20261004T174312-46295c57` |
| R1-24 | rehearsal-1 / AG-1424 / tools | `investigate-20261004T181657-5171cad2` |
| R2-23 | rehearsal-2 / AG-1423 / tools | `investigate-20261004T174952-5155ed68` |
| R2-24 | rehearsal-2 / AG-1424 / tools | `investigate-20261004T182309-1ea4b1c4` |
| Provided | comparison-provided / AG-1423 / provided | `investigate-20261004T174951-88c1b9ae` |
| Repo | comparison-repo-3 / AG-1423 / repo | `investigate-20261004T182335-24faaa6b` |

Earlier partial runs are not substituted for these final results. Their denied reads and invalid output remain recorded separately.

## Claim matrix

| Important claim | Review result | Evidence and limit |
|---|---|---|
| DEV-101 is PRO 3.4.0; DEV-102 is PRO 3.1.0. | Supported for the affected device in each investigation. | Registry excerpts show DEV-101 at `app/devices.json:2–5` and DEV-102 at `:6–9`. R1-23's cross-device recommendation lacks an attached DEV-102 reference; the tool delivered the full registry, but its recorded read spans cover DEV-101 only. |
| Approved policy permits eligible PRO devices up to 50 zones and earlier firmware up to 20. | Supported in the five knowledge-enabled packets; appropriately unknown in Repo. | Policy metadata `:5–10`, capacity rules `:14–18`, and applicability `:28–30` establish approval, effective date, eligibility, and scope. Some individual claims omit references already present elsewhere in their packet. |
| AG-1423 is a mismatch; AG-1424 is an expected rejection. | Correct and evidence-backed as an investigation decision. | Ticket symptoms, the affected registry record, and policy distinguish the two cases. Code explains the rejection. These read-only packets are not executed reproduction results; every packet retains that limitation. |
| Frontend rollout completion does not establish backend enforcement, and Scheduling Backend owns validation. | Supported; a few historical metadata details have incomplete line citations. | AG-981 `:12–14` establishes delivery scope, `:16–18` and design `:16–18` establish ownership. Closed status, dates, and ticket ownership require their metadata spans, rather than scope excerpts. |
| Change the eligible-device capacity logic; do not change the older-device rejection or promise an upgrade. | Appropriate next actions, with attachment gaps noted below. | Capacity rules and policy applicability support the distinction. AG-1424's triage text explicitly lacks an approved upgrade procedure. Neither the packets nor this review claim a deployed customer fix or measured productivity improvement. |

## Citation coverage findings

1. **R1-23 — ticket and historical metadata.** The policy text states AG-1423's date, and the owner text states Support Triage, but the attached `ticket` citation covers only `knowledge/jira/AG-1423.md:11–21`. Inspect the already successfully captured `:5–9` for owner and updated date. The history claim says AG-981 was Closed, owned by Frontend Scheduling, and dated 2026-09-18; `hist981` covers only `AG-981.md:12–14`. Those values exist in the saved search-result metadata, but `AG-981.md:5–10` is outside this run's captured text-read spans. Inspect `evidence.sources["knowledge/jira/AG-981.md"].metadata` as structured evidence; do not expand the original line citation as though those lines had been read.

2. **R1-23 and Provided — second-device recommendation.** Both next-action texts identify DEV-102 as PRO 3.1.0 while their attached references establish policy and DEV-101 facts. Provided recorded a successful full-registry read, so its existing captured `app/devices.json:6–9` supplies the missing reference. R1-23's ledger records only registry `:2–5` and structured device metadata for DEV-101. However, its preserved `get_device("DEV-101")` tool result actually delivered full registry `content` and `numbered_content`, including DEV-102. The DEV-102 statement therefore is not an invented fact; it has a provenance-ledger mismatch and no attached record citation. Inspect the saved raw trace for that exact tool result or perform a separately recorded DEV-102 lookup. Do not silently expand the historical ledger to make it pass a different check.

3. **R2-23 — references available elsewhere are not attached to the whole claim.** The policy claim names `zone_limit_exceeded` but omits its existing `polsave` reference (`controller-capacity-policy.md:24–26`); it states AG-1423's date but omits its existing `ticket_meta` (`AG-1423.md:5–9`). The execution path describes the specific DEV-101 record without attaching `reg`, and the next action's device-specific expected result likewise omits `reg`. The required excerpts are already captured and cited elsewhere in the packet; include them when reviewing those individual claims.

4. **R1-24 and R2-24 — numeric constants in the patched application.** R1-24's `code_validator` starts at `app/schedule_validator.py:11`; R2-24's `val_logic` covers `:24–28`. Both show comparisons using named constants without their definitions. Therefore those selected code excerpts alone do not establish that the implementation uses limits 20/50 and boundary 3.2.0. Inspect the already successfully captured `app/schedule_validator.py:6–8` in each run. Their policy and registry references establish the expected decision, but the constant definitions are needed to confirm the stated implementation behavior.

5. **Repo — ticket-owner reference.** The owner text correctly distinguishes unknown code ownership from Support Triage's ticket ownership, but `tkt` covers `AG-1423.md:11–21` and omits the owner line. Inspect the already successfully captured `AG-1423.md:5–9`. The unknown business requirement is appropriately preserved; no policy value is invented.

6. **All six runs — code-derived HTTP 400.** Their service excerpts show selection of `zone_limit_exceeded` and a call to `_invalid`, but do not include the helper that constructs HTTP 400. Inspect the already successfully captured `app/schedule_service.py:42–43` for that code-path claim. The ticket and approved policy separately support reported and expected HTTP status; neither substitutes for citing the helper when asserting what the implementation returns. R2-24's narrow `svc_flow` also omits persistence lines `:31–35`, which help establish its statement that rejection occurs before storage.

## How to inspect without rewriting history

Open the selected run in the replay viewer or inspect `artifacts/runs/<run-id>/bundle.json`. For a statement, follow its citation IDs into `packet.citations` and inspect the exact stored excerpts. For the supplementary spans listed above, view `evidence.sources[<source>].content` with one-based line numbers and check `spans` before calling them evidence that the agent successfully read.

Keep expected behavior, customer reports, code inference, and executed test results distinct. R1-23 explicitly labels its explanation of how the backend reached this state as a hypothesis; the other final packets do not invent a confirmed change history. The AG-1424 packets retain unknown physical-device freshness and/or missing upgrade evidence. Use the separate reproduction, fix, and verification artifacts for actual execution claims.

Before presenting a claim as human-reviewed, a reviewer should inspect these supplements and record their own decision. Until then, present the packets as mechanically verified model handoffs with this review attached.
