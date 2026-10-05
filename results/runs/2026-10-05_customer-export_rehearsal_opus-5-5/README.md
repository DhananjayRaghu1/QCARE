# Customer export: LangGraph workflow rehearsals (Opus 5.5)

Two live runs of the new Demo 2 engineering workflow on DH-401 (the NORTHSTAR settlement export). Every step used `claude-opus-5-5` through Claude Code. Ishaan's session operated the page and made the developer decisions. These are rehearsals for the meeting, not a benchmark.

| Run | Developer input | Path | Model time | Cost | Hidden checks |
| --- | --- | --- | --- | --- | --- |
| `bcf88063…` | Note: "Use UTC to keep it simple" | Analysis paused before code → developer chose the approved New York rule → re-check → build → review → accepted in 1 round → approved | 210 s | $1.20 | 12/12 |
| `eaf902a3…` | No note; at review, sent back: "close the reviewer's two test gaps" | Build accepted in round 1 → send-back conflict-checked → round 2 built and accepted → approved | 283 s | $1.94 | 12/12 |

## What happened

- **Retrieval.** Both analyses opened EXPORT-NS-1, FIN-SETTLEMENT-2 and the EXPORT-NS-2 draft, searched Jira and Confluence, and read the code and tests. Every quoted requirement was found word-for-word in a record the workflow opened: 19/19 and 20/20, plus 2 inferred requirements each. The analyst also found pending request DH-204 by search and correctly ruled it out of scope.
- **The pause.** With the UTC note, the analyst marked one blocking conflict before any code was written. It showed the concrete effect on the sample (UTC would include N-101 and drop N-102), named Reporting Product as the owner, and recommended the approved rule.
- **Build, review, check.** The engineer wrote the exporter and 16–20 new tests; every test run by the workflow passed. The independent reviewer found only low-severity test gaps. No guard override was needed.
- **Risks the summary flagged for a human:** zero-padded month routing, one bad record blocking the whole export, and Python 3.11+ for `Z` timestamps.

## Caveats

- Two rehearsals on one synthetic fixture, and the same operator answered both decisions. This shows the workflow runs end to end. It does not establish quality or productivity.
- The hidden acceptance checks are this demo's fixture checks. They were not shown to the agents or used for routing, but they are not a substitute for a real team's review.
- The runs used the uncommitted workflow code on branch `ishaan/langgraph-export-workflow` (based on `71b25ec`). Before them, one CLI capability check cost $0.05 (see `results.json`).

The replay recordings from these runs were replaced after the workflow changed (code gate, context switch). The sanitized `results.json` keeps their numbers.
