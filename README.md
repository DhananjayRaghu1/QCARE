# Business context → a justified next action

Local, synthetic demos for discovering where code, business documents, Jira history and customer configuration can help a team make better decisions. These are prototypes for discussion, not Data Honey's product or customer records.

## Three demos on one site

| Demo | Why business context matters | Output |
| --- | --- | --- |
| [Investigate a report](http://127.0.0.1:8768/demos/report) | The code and customer disagree; contracts establish the intended interpretation | Justified diagnosis and next action |
| [Build a customer export](http://127.0.0.1:8768/demos/export) | A short request omits timezone, fee, refund and compatibility rules | A live LangGraph workflow: verified requirements, a pause for the developer's decision, a reviewed patch and independent acceptance results |
| [Check a cleanup before release](http://127.0.0.1:8768/demos/migration) | A green cleanup PR silently drops old-format rows; code cannot establish the customer and recovery promises it must preserve | Synthetic job replays, sourced dependencies, per-dependent release gates and drafts for the developer's decision |

```sh
cd demos/01-report-reconciliation
uv sync --locked
uv run python demo.py live
```

Open [the demo hub](http://127.0.0.1:8768/). Each demo has an original request, source documents, working sample code, an optional prepared example, live comparison controls and a production workflow/architecture page. The meeting UI keeps only DH-301 from the original ticket set; the other reporting cases remain regression fixtures.

The reporting raw modes use the same prompt and repository; Docs + Jira adds prose source snapshots. The feature demo captures edits in a temporary workspace and checks the resulting implementation after the model finishes. Demo 3 uses the same release-check workflow with business context on or off: its model session is read-only, while code runs synthetic job replays, applies release gates and prepares local review/sign-off/decision-record drafts. The reporting demo also retains its separately labeled guided MCP/calculator mode. Live calls use the existing Claude Code login; clicking prepared examples does not call a model.

Demo 3 builds on **Dhananjay (DJ) Raghu's shared-decoder cleanup idea**. His original request, worked example and seed tests remain available. The release check adds a prepared candidate patch whose narrowed job filters silently omit v1 rows and whose deleted replay test makes its remaining CI green. See the [release-check guide](demos/01-report-reconciliation/docs/migration-release-check.md) for the comparison, evidence boundaries and conditional retirement date. No sandbox PR is created or commented on by this workflow; drafts stay local.

Architecture pages describe a **proposed production design**, including authorized retrieval from Git, Jira and Confluence, combining evidence by scope and version, independent verification, and human approval. Those enterprise connectors are not deployed in this prototype.

Read the [implementation guide](demos/01-report-reconciliation/README.md) and [meeting script](demos/01-report-reconciliation/docs/meeting-guide.md). No model-generated change is automatically applied, merged or deployed.

## What changed, and what we can claim

The earlier controller example did not establish productivity improvement. Its basic repository-only run found the simple defect faster than the run with extra context. Two successful policy-aware rehearsals showed that the workflow could execute, but two runs—and comparisons with evolving prompts—do not support a productivity estimate.

The new problem makes business context materially change the answer. A reproducible regression rejects both the original implementation and the tempting fix, while a prepared reference passes. The approved-rule workflow passes all ten synthetic case checks, including three cases that must stop and one where row errors cancel in the total.

**This demonstrates verified behavior on these fixtures, not a measured productivity gain.** The guided workflow uses deterministic software and hand-authored structured rules. The live raw modes investigate from code and optional prose documents without that calculator.

A subsequent [actual Codex comparison](demos/01-report-reconciliation/docs/codex-comparison.md) ran the same case with and without prose business documents. Repo-only took **50.5 seconds**, found $1,250 as a possibility, and appropriately asked for the missing rule. With documents took **95.2 seconds**, established $1,250 and proposed code that passed **11 independent checks plus 5 baseline tests**. The benefit was resolving uncertainty and completing a justified proposal; there was no demonstrated speedup. The original Claude preflight record documents an earlier authentication block. The live UI checks current authentication for each attempt.

Read the [verification record](demos/01-report-reconciliation/docs/verification.md), [implementation scope](demos/01-report-reconciliation/README.md), and [evaluation protocol](demos/01-report-reconciliation/docs/evaluation-protocol.md). A future pilot should measure time to an accepted decision, errors, handoffs, human review and setup/maintenance costs on real representative cases.

## Results

Every recorded run across all demos, including live model comparisons, baselines, rehearsals and control checks, is registered in [results/INDEX.md](results/INDEX.md). [results/README.md](results/README.md) explains naming and how to add a run. The first live comparison for Demo 1 ran on Claude Opus 5.5 after this revision: [results/runs/2026-10-04_report-reconciliation_live-comparison_opus-5-5](results/runs/2026-10-04_report-reconciliation_live-comparison_opus-5-5/README.md).

## Earlier controller demos, preserved

- [Policy-aware controller capacity](demos/01-controller-capacity/policy-aware/README.md): two actual recorded Claude rehearsals, failing regressions, agent patches, compatibility checks and documented citation limitations.
- [Basic developer onramping](demos/01-controller-capacity/basic/README.md): the original prototype and its [historical comparison](demos/01-controller-capacity/basic/docs/historical-comparison.md), where repository-only was faster.

Their original recordings remain unchanged. Each demo has its own dependencies and environment. Generated workspaces, virtual environments and private traces remain local and ignored.
