# Business context → a justified next action

Local, synthetic demos for discovering where code, business documents, Jira history and customer configuration can help a team make better decisions. These are prototypes for discussion, not Data Honey's product or customer records.

## Demo 1: Which total can we defend?

**Start with [customer-report reconciliation](demos/01-report-reconciliation/README.md).** The application reports **$1,550** and the customer expects **$1,150**. Approved reporting rules and two export contracts show that **both are wrong: the correct total is $1,250**.

A tempting `-abs()` fix matches the customer but mishandles a return reversal. The workflow identifies the affected rows, cites the applicable sources and recommends a schema-specific repair. Other cases produce a customer explanation, a configuration correction, or an explicit stop when evidence is missing or conflicting. A pending Jira request does not silently become approved policy.

```sh
cd demos/01-report-reconciliation
uv sync --locked
uv run python demo.py present
```

Open the generated `artifacts/presentation.html` in a browser. The interactive walkthrough runs offline and includes ten cases with expandable business/Jira source snapshots. For terminal output and verification:

```sh
uv run python demo.py run DH-301
uv run python demo.py reproduce
uv run python demo.py controls
uv run python -m pytest -q
```

Use the [10-minute meeting script](demos/01-report-reconciliation/docs/meeting-guide.md) to connect the demonstration to discovery. The scope is one support discrepancy → a reviewable decision and next action. Ask how the team currently finds the relevant evidence, decides which source governs, and validates the outcome.

## What changed, and what we can claim

The earlier controller example did not establish productivity improvement. Its basic repository-only run found the simple defect faster than the run with extra context. Two successful policy-aware rehearsals showed that the workflow could execute, but two runs—and comparisons with evolving prompts—do not support a productivity estimate.

The new problem makes business context materially change the answer. A reproducible regression rejects both the original implementation and the tempting fix, while a prepared reference passes. The approved-rule workflow passes all ten synthetic case checks, including three cases that must stop and one where row errors cancel in the total.

**This demonstrates verified behavior on these fixtures, not a measured productivity gain.** The default workflow uses deterministic software and hand-authored structured rules. An LLM is optional for retrieving evidence and explaining the result; it is not required for the calculation. The new live Claude comparison was blocked by missing client authentication, and no new model run is claimed.

Read the [verification record](demos/01-report-reconciliation/docs/verification.md), [implementation scope](demos/01-report-reconciliation/README.md), and [evaluation protocol](demos/01-report-reconciliation/docs/evaluation-protocol.md). A future pilot should measure time to an accepted decision, errors, handoffs, human review and setup/maintenance costs on real representative cases.

## Results

Every recorded run across all demos, including live model comparisons, baselines, rehearsals and control checks, is registered in [results/INDEX.md](results/INDEX.md). [results/README.md](results/README.md) explains naming and how to add a run. The first live comparison for Demo 1 ran on Claude Opus 5.5 after this revision: [results/runs/2026-10-04_report-reconciliation_live-comparison_opus-5-5](results/runs/2026-10-04_report-reconciliation_live-comparison_opus-5-5/README.md).

## Earlier controller demos, preserved

- [Policy-aware controller capacity](demos/01-controller-capacity/policy-aware/README.md): two actual recorded Claude rehearsals, failing regressions, agent patches, compatibility checks and documented citation limitations.
- [Basic developer onramping](demos/01-controller-capacity/basic/README.md): the original prototype and its [historical comparison](demos/01-controller-capacity/basic/docs/historical-comparison.md), where repository-only was faster.

Their original recordings remain unchanged. Each demo has its own dependencies and environment. Generated workspaces, virtual environments and private traces remain local and ignored.
