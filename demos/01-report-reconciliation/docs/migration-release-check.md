# Demo 3: A release check for shared-code cleanup

The [actual Opus comparison](../../../results/runs/2026-10-05_format-retirement_live-comparison_opus-5-5/README.md) scored **12/12 with context and 1/12 without context**, with both blocking full removal. All four attempts and their costs are retained. [Deterministic verification](../../../results/runs/2026-10-05_format-retirement_controls/README.md) is recorded separately and calls no model.

**Dhananjay (DJ) Raghu's idea is the starting point:** removing old support from shared code can conflict with promises the repository cannot establish. The release-check workflow makes that risk visible while preserving his original request, seed tests and prepared worked example.

Everything in this scenario is synthetic: customers, contracts, Jira records, operational usage and replay rows. The candidate PR is a prepared local patch. It is never opened or commented on in a GitHub sandbox. A fresh model session is live execution over those synthetic sources; it is not a live connection to a customer's systems.

## What the cleanup changes

The seed application supports ATLAS v1 signed values and v2 return magnitudes. Three jobs use the shared decoder: `daily_sales`, `historical_replay` and `partner_statement`. A proposed cleanup removes v1 decoding, narrows their accepted versions to v2, and removes the regression that covers a v1 positive return.

The candidate's remaining CI passes, yet the jobs' filter quietly skips every v1 row before calling the decoder. The replay executes both implementations using the same rows:

| Synthetic job | Base | Candidate | What is missing |
| --- | ---: | ---: | --- |
| NORTHSTAR September | $1,250 | $400 | Signed v1 rows needed to reproduce the original report |
| CEDAR statements | $180 | $0 | All v1 statement rows |

These are job outputs from code, not totals estimated by a model. NORTHSTAR's five September rows connect back to Demo 1's prepared schema-specific calculation. A successful candidate test suite does not establish correct row coverage when the relevant test was deleted.

Only the two business-record sentences that directly state the removal verdict are removed. The original request wording, facts, worked example and seed tests stay intact. The prepared cleanup deletes the test only in its candidate workspace; it does not erase the original seed test.

## The workflow

```text
prepare candidate → run CI + replay jobs → one read-only Opus assessment
                 → verify source evidence → per-dependent gate
                 → pause for developer decision → local drafts
```

This is built on Demo 2's LangGraph, Claude session, checkpoint and recording infrastructure. The model gathers evidence and explains dependencies. Code runs the jobs, validates evidence, evaluates release gates and generates drafts. The developer decides which next action to pursue; choosing an action does not turn a missing approval into an approval.

The assessment covers four dependents:

| Dependent | What code can establish | What business and operational evidence must establish |
| --- | --- | --- |
| NORTHSTAR live ingest | Job filter, decoder call and code owner | Actual migration scope, fresh per-job usage and who can clear a limited canary |
| Historical replay | Job filter, decoder call and silent loss in the replay | Original-format replay/retention obligations, conversion state and readable backups |
| CEDAR statements | Job filter, decoder call and the statement loss | Customer delivery promise, migration-window approval and the authorized sign-off owners |
| Rollback | The removed decoder's role in restoring old behavior | Current rollback configuration, rehearsal evidence and accountable recovery owner |

Every claimed obligation needs an exact quote from a fetched record, with source identity, version, scope, owner and dates. The synthetic assessment date is October 4, 2026: the October 4 usage record is current for that fixed scenario, while the October 1 snapshot is stale. Neither is live telemetry for an October 15 release; per-job usage must be refreshed within one day of the release decision. A code owner is not automatically the person authorized to approve a customer change.

The gate returns allow or block for each dependent with reasons. A developer note such as “remove it anyway” is a recorded request; it cannot clear a contract, stale or missing usage evidence, failed replay, retention obligation or rollback requirement. The whole shared removal remains blocked while any dependent is blocked.

The gate's per-dependent policy adapters are explicitly authored for this synthetic release. Exact-quote, record-hash, scope and date checks establish provenance and applicability; they do not prove that arbitrary prose has been correctly translated into policy or that a real dependency inventory is complete. The model does not create or approve executable business policy. A production pilot needs owners to review those adapters and their acceptance examples.

## Date reasoning

The proposed date is October 15, 2026. Cedar's synthetic agreement keeps statements on v1 through November 30 inclusive, so December 1 is the first possible date after its delivery promise. The synthetic replay fixture identifies September 30 as the latest archived v1 export. The rolling 90-day original-format replay obligation includes data aged exactly 90 days, so that export remains covered through December 29 inclusive. **December 30, 2026 is the earliest conditional lower bound for full removal**, taking the later of these two constraints.

These dates and boundary rules are authored demo facts, not customer evidence. The lower bound is not a release approval. New v1 archives can move it; verified conversion may need separate owner approval. The absolute removal date remains unknown until customer migration, expiry of applicable retention or verified conversion, backup readability, rollback readiness and current usage are established. Keep those conditions beside the date in the assessment, gate and decision-record draft.

## The context comparison

Both conditions use the same task, candidate patch, replay rows, workflow, model setting and grading. Only access to business and operational sources changes.

| Available input or output | Context on | Context off |
| --- | --- | --- |
| Candidate code, original code, code owners, CI and replay losses | Yes | Yes |
| Sourced customer and recovery obligations | Retrieved through read-only tools | Missing |
| Approval owners and a supported retirement bound | Must be sourced and conditional | Unknown; ask for the evidence |
| Safe gate behavior | Allow or block each dependent from evidence | Block where evidence is missing |
| Developer decision and local drafts | Same options | Same options, with explicit missing evidence |

Context off is still expected to notice replay losses and block. The comparison asks whether added context supplies the affected parties, obligations, approval route and timing needed for an actionable decision. “Both blocked” does not imply equal usefulness, and “more blockers” is not a quality metric.

The twelve hidden checks run separately after assessment for the demo comparison card. Their cases and expected answers are excluded from model prompts, accessible tools and gate routing. They do not authorize release. Publish only actual saved scores, with condition, model, time, cost and outcome; a prepared verification fixture is not a paid-session result. Matched synthetic runs do not establish productivity improvement or production readiness.

## The developer's decision and drafts

The workflow pauses for one decision:

- **Defer removal:** keep shared support and document the evidence still required.
- **Pursue a scoped canary:** limit the next step to a live path whose gate is cleared; this does not clear the full cleanup.
- **Request sign-off:** draft targeted requests for the people who can settle the unresolved obligations.

The result includes a PR review comment, sign-off requests and a decision-record update. All remain local drafts. No messages are sent, no PR is created or commented on, no approval is granted by a model, and no shared decoder change is applied to production.

## Run and preserve it

From `demos/01-report-reconciliation/`:

```sh
uv sync --locked

# Execute prepared CI/replay/gate verification without a model call.
uv run python migration_demo.py verify

# Start a fresh read-only Opus assessment and pause for a developer decision.
uv run python migration_demo.py run --context on
uv run python migration_demo.py run --context off

# A note is part of the request, not evidence of an approval.
uv run python migration_demo.py run --context on --developer-note "Remove it anyway; CI is green."

# Preserve a completed run for the meeting page's replay picker.
uv run python migration_demo.py record <workflow-id> --name <recording-name>
```

The UI is served by `uv run python demo.py live`; open [Demo 3](http://127.0.0.1:8768/demos/migration). Inspect the candidate diff and replay evidence before running a session. The workflow retains its checkpoint, tool events, prompts, assessment, gate and local drafts. A recording replays those saved events; it does not make another model call.

Actual run records belong in the repository's [results index](../../../results/INDEX.md). Missing authentication, timeout or a failed assessment remains a failed run; it must not be replaced with a prepared answer and presented as live. The offline worked example remains useful as a clearly labeled explanation.

## Production boundary

The [migration architecture page](http://127.0.0.1:8768/architecture/migration) is a proposal for permission-checked retrieval from real Git, Jira, business documents and operations. This prototype proves behavior only against its local synthetic inputs. A pilot needs a human-validated dependency inventory, actual approval records, representative recent jobs, source freshness rules and replay/rollback evidence. Measure accepted decisions and owner review effort together with total time, failures and source-preparation costs.
