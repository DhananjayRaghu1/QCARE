# Verification status

This document distinguishes local component checks, prepared control behavior, and actual Claude execution. A working CLI or passing reference fixture does not prove the live investigation-to-fix workflow succeeds.

On 2026-10-04, two actual fresh-seed Claude rehearsals completed the investigation → real failing regression → agent patch → independent verification sequence, followed by AG-1424's expected-rejection decision. Both are exported under `replays/`. Use `rehearsal-2` as the meeting fallback. Human claim review remains pending; the independent Codex [claim review](claim-review.md) documents incomplete citation attachments and supplementary evidence.

## Local verification contract

Run `uv run python -m pytest -q` from the policy-aware directory. Local coverage should exercise the application, real MCP transport, retrieval, evidence matching, tool boundaries, timeout/failure handling, prepared control states, and portable replay/viewer validation. Tests using authored client events are parser and orchestration checks, not model-generation evidence.

The independent checker contains **34 fixed acceptance cases**, outside the practice application and retrieval index. It checks eligible/older/Legacy capacities, exactly 3.2.0, numeric 3.10.0, malformed/missing metadata, unknown devices, request overrides, invalid zones, and rejected-request persistence and ID allocation.

| Code state | Required observation |
| --- | --- |
| Seed | Starting tests pass; eligible-Pro expansion checks fail. |
| Reference fixture | Visible tests and all 34 independent cases pass. |
| Unsafe all-Pro-50 fixture | Starting tests and the reported 30-zone regression pass; independent older-firmware cases fail. |
| Actual Claude patch | Captured real regression first fails on seed, passes unchanged after the patch, and all independent checks pass. |

The unsafe verification command returns a nonzero exit intentionally. A failure for the expected reason is evidence that the independent checker catches an invalid patch; it is not a passing application result.

## Live acceptance and review

Complete two fresh seed rehearsals. For each, record investigation, reproduction, fix, and verification run IDs, actual model, context/retrieval mode, elapsed time, retries, and outcome. The reproduction must be the actual reported-case capacity assertion failure, not a test import error. Protected tests, registry, and policy must remain unchanged; the reported regression must remain unchanged through fixing.

Review whether citations support entire claims, not only whether ranges exist. Check the approved policy status/effective scope, affected device model/firmware, expected behavior, backend code, ownership, history, and unknowns. AG-1423 should establish a mismatch when evidence is available. AG-1424 should establish expected rejection; neither justifies inventing a firmware-upgrade procedure.

An investigation's source verification does not mark human claim review complete. A fix that passes visible tests is still awaiting independent verification. Denials, timeouts, schema/reference failures, stale sources, and partial stages remain visible. A length warning alone must not trigger another model request.

## Reproducibility and comparison

Export a complete actual rehearsal and inspect its source snapshots, patches, test results, and provenance labels. Test its replay after the original workspace is unavailable. The exported bundle is derived from the recording, with paths normalized; raw traces remain local. The viewer and replay must validate captured evidence rather than depend on current application paths.

For AG-1423, compare `repo`, `provided`, and `tools` in fresh seed workspaces using the same model and inputs. `repo` lacks external policy; honest uncertainty is acceptable. `provided` has the same five documents as `tools`, supplied directly. Record justified conclusions, evidence quality, latency, and retries. These small checks do not establish generalized retrieval quality or business productivity gains.

## Observed results — 2026-10-04

The final local suite passed **312 tests** (`.venv/bin/python -m pytest -q`). This includes authored-event parser checks, failure/timeout handling, source verification, permissions, application states, MCP/retrieval, and viewer/replay tests. These local checks supplement the actual executions below.

Every recorded model phase used actual model `claude-sonnet-5-5`. Both rehearsals used the same initial seed and device registry, with BM25/MCP investigation. Elapsed time includes the phase's orchestration; validation attempts refer to evidence packet attempts, not separate full rehearsals.

| Phase | Rehearsal 1 run | Rehearsal 2 run | Observed outcome |
| --- | --- | --- | --- |
| AG-1423 investigation | `investigate-20261004T174312-46295c57` — 36.37s, 2 validation attempts | `investigate-20261004T174952-5155ed68` — 18.84s, 1 attempt | Read-only mismatch decision; captured policy, affected registry record, and backend code. |
| Reported regression | `reproduce-20261004T174423-cb702220` — 8.66s | `reproduce-20261004T181627-973edfbb` — 10.22s | Actual agent-created test failed with HTTP 400 versus expected 201; one assertion failure, zero import/runtime errors. Application unchanged. |
| Fix | `fix-20261004T174732-25241842` — 13.91s | `fix-20261004T182021-6b57d3e8` — 9.20s | Actual agent patch derives limits from model/firmware with numeric version ordering. Original tests, regression, registry, and policy unchanged. All 23 visible tests passed. |
| Independent verification | `verify-20261004T174929-a92358a0` | `verify-20261004T182236-c9849f78` | 23 visible tests and all 34 independent policy cases passed for each patch. |
| AG-1424 investigation | `investigate-20261004T181657-5171cad2` — 36.50s, 2 validation attempts | `investigate-20261004T182309-1ea4b1c4` — 30.13s, 2 attempts | Expected rejection for DEV-102 PRO 3.1.0, with approved policy. No firmware-upgrade procedure invented. |

Rehearsal 1 also contains the preserved partial AG-1424 attempt `investigate-20261004T175004-06c31371` (29.19s). It did not fetch the approval/applicability details needed to establish policy. Its original output and status remain visible. Retrieval instructions were clarified before the successful rerun. The main Rehearsal 1 packet needed one bounded citation correction and exceeded the narrative-length target; length remained a warning. Rehearsal 2's main packet was valid on its first attempt.

The reference control `verify-20261004T174237-2e1d8eac` passed 23 visible and 34 policy checks. The unsafe all-Pro-50 control `verify-20261004T174237-b2d59c91` passed all 23 visible tests but failed `pro_old_21` and `pro_below_boundary_3_1_99`, giving 32/34. Both are preserved in [control recordings](../recordings/controls.json) and explicitly labeled prepared fixtures. The seed's local state checks show its visible tests pass while eligible-Pro expansion is missing.

Both recordings export and validate their captured evidence. `rehearsal-2` was copied with only the replay runtime modules into a fresh `/private/tmp` directory: no original workspaces, artifacts, knowledge directory, or seed files were present. The replay command exited 0. Both investigation packets revalidated, source hashes and the ordered patch chain matched, and the captured regression remained unchanged. Exported JSON and Markdown scanned clean for private absolute paths, credential patterns, and raw trace/stderr filenames. The loopback viewer API separately validated all five phases, the actual red failure, patch diff, passing tests, and second-ticket decision.

All comparison attempts, including failures, are documented in [comparison results](comparison-results.md) and [their captured bundles](../recordings/comparison.json). Repository-only correctly abstained on the unknown business rule; providing or retrieving the policy justified the mismatch decision. Development changed instructions and output parsing between attempts, and some calls ran concurrently. Timings are observed rehearsal costs, not a controlled speed benchmark or productivity result.

The remaining presentation step is **your human review** of the recorded claims and the [citation supplements](claim-review.md). Automated provenance and test success do not establish every narrative claim. The viewer retains that distinction.
