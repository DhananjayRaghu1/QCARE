# Verification record — 4 October 2026

**Subsequent live comparison:** [two actual Codex investigations](codex-comparison.md) are now recorded: repo-only 50.476 seconds, documents 95.180 seconds. The proposed document-backed patch passed 11 independent checks and 5 baseline tests. The complete new-demo suite now has 42 passing tests. The initial Claude block and initial 40-test results below remain a historical record; they do not imply the later Codex runs were blocked.

## Executed locally

Environment: macOS, managed CPython 3.12.10, locked dependencies. An initial attempt with the machine's Anaconda 3.12.2 crashed while importing `readline` during pytest startup; the demo pins the managed interpreter used for the successful runs. No application workaround was introduced for that environment problem.

| Check | Observed result |
| --- | --- |
| New demo: `uv run python -m pytest -q` | 40 passed |
| Existing policy-aware controller suite | 312 passed |
| Existing basic controller suite | 133 passed; 18 subtests passed |
| Ten-case approved-rule workflow | 10/10 decisions, totals/stops, affected rows and required source checks passed |
| DH-301 regression against original code | Failed: 155000 cents; wrong contributions for A-2 and A-3 |
| Same regression against prepared `-abs()` control | Failed: 115000 cents; wrong contribution for A-3 |
| Same regression against prepared reference | Passed: 125000 cents; all five contributions correct |
| MCP subprocess integration | Full-document hash and case calculation verified; retrieval-only mode excludes calculator; no arbitrary file read tool |
| Client failure handling | Real local subprocess timeout and failure-to-launch preserved as failures using test stubs, with no model requests |
| Browser walkthrough | DH-301 rendered correctly; selection changed to DH-303 and DH-305; Jira evidence expanded; conflict displayed an undetermined total |

Tests cover customer scope, historical effective dates, signed reversals, invalid magnitudes, missing/draft contracts, conflicting policies, missing inclusion semantics, exact integer amounts, duplicate IDs, offsetting row errors, source acquisition checks, fixed comparison schedules and blocked authentication. The independent reported-case regression checks row contributions as well as the total.

See [executed controls](../recordings/controls.json), [regression subprocess output](../recordings/regression.json), and the [rendered DH-301 evidence packet](../recordings/DH-301.md). Only the local absolute directory in regression traceback paths was replaced with `<demo>` for portability. Exit codes, assertion text and values are preserved.

## Model execution status

Claude Code 2.1.186 was installed but not authenticated. The [preflight record](../recordings/preflight.json) and [blocked comparison record](../recordings/comparison-readiness.json) show the actual state. The fixed comparison contains 30 planned trials, **zero actual model attempts**, no model IDs, no elapsed model times and a null productivity estimate.

The live adapter is exercised with local tests and actual MCP subprocesses; it has **not been validated against a real authenticated provider in this revision**. Test stubs are not counted as agent executions. The original controller's historical agent recordings remain unchanged and cannot be used as results for this new task.

## Scope of the evidence

The default demonstration is implemented and reproducible without an LLM. It uses an intentionally faulty seeded report, synthetic connector snapshots, approved structured rules authored by hand, exact arithmetic, explicit stop conditions and captured sources. It is not a live Jira/Docs integration, an automatic arbitrary-policy extractor, or a deployed repair.

All ten synthetic cases are part of a designed fixture set. Passing them does not establish general accuracy, safety on unseen business data, or superiority over another assistant or a human analyst. Citation ID and source hash checks do not establish narrative entailment. Human review remains pending.

The new example supports a narrower, useful conclusion: a code-level sign change or a matching customer total can still be wrong, and applicable business evidence can distinguish a repair from an explanation or escalation. Measure time savings only in a separate pilot with representative cases, human review and setup/maintenance costs included.
