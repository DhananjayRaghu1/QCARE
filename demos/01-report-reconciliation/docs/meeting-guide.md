# Meeting script: 10 minutes, then discovery

## 0–1 min: Frame the problem

“A customer says a report is wrong. We need to know whether to fix code, correct configuration, explain the business definition, or ask someone to resolve missing information. This example is synthetic. We want to learn whether you have an equivalent workflow.”

Open the generated presentation and select DH-301. Point to the $1,550 report, $1,150 customer claim and $1,250 rule-based result. Ask the audience how they would establish the correct definition before touching code.

## 1–4 min: Establish why the sources matter

Expand FEED-ATLAS-1 and FEED-ATLAS-2. Schema 1 is signed; schema 2 is magnitude. Walk through A-2 and A-3: the current code flips a real −$200 return and a +$50 reversal. The positive reversal must remain positive. `-abs()` matches the customer's spreadsheet but is still wrong.

Expand REPORT-STD-SEP to show that the reporting month uses posted date, SALE/RETURN only, for this profile and period. Source approval, scope and dates are part of the decision. A search hit or Jira status alone does not establish the rule.

Run `uv run python demo.py reproduce` if the group wants implementation evidence. Explain that seed and naive fixes actually fail the same independent row regression and the prepared reference passes. This reference was written ahead of time; do not present it as a live agent writing code.

## 4–6 min: Show a case that should not create engineering work

Select DH-303. The customer wants $1,100, but the approved report is $800 because transfers are excluded. Expand DH-204: it is a pending request to include them. The right output is a source-backed explanation and a product decision if the definition should change.

Ask: “When someone requests a different number, how does your team distinguish a defect from a different business definition? Where is approval recorded?”

## 6–8 min: Show an honest stop

Select DH-305. Two approved customer policies conflict over which date defines the reporting month. The workflow returns no authoritative total and routes the decision to Reporting Product. It does not pick the newest-looking source or manufacture certainty.

If engineers ask about test strength, show DH-310: two row errors cancel, so a matching total alone misses the defect. If data integrations are more relevant, show DH-308's invalid magnitude and quarantine action.

## 8–10 min: Explain the feasible architecture and ask for a real case

“The calculation and rule checks are deterministic. The rules here were normalized by hand from synthetic documents. An assistant can gather evidence, invoke this workflow and explain the next step. We have tested the fixtures; we have not established time savings or run a fresh authenticated model comparison in this revision.”

Ask for one recently resolved discrepancy that crossed teams. Reconstruct the actual ticket, data, documents, decisions, handoffs, time spent and final resolution. Agree who can confirm the authoritative rule and whether the same case recurs. Do not assume they need an agent before understanding that process.

## Discovery notes to capture

| Question | Evidence to obtain | Workflow design consequence |
| --- | --- | --- |
| What starts this work? | Actual support ticket or analyst request | Trigger and minimum input |
| What decision must be made? | Example final resolution and owner | Output and approval boundary |
| Where is the answer scattered? | Docs, Jira records, raw exports, account settings, code | Required read-only connectors |
| Which source wins when they disagree? | Approval trail, customer scope, effective dates | Precedence and stop rules |
| What makes a case take a long time? | Searches, handoffs, blocked time, repeat corrections | Pilot metric and intervention |
| How is an answer accepted? | Regression, reconciliation, policy owner review | Independent acceptance criteria |
| How often does it occur? | Recent case count and distribution | Whether adapter maintenance is worthwhile |

QCARE can structure the conversation: Question, Context, Actions, Risk, Evaluation. Treat it as a checklist for understanding work, not a method that proves root causes. Observing cases and verifying the resulting hypothesis does that work.

For a two-hour invitation, propose a 60–75 minute core: introductions and desired outcome (10), one real workflow (25), relevant demo (10), pilot shape and next step (15–30). Keep the remaining time available for deeper discussion, with an explicit option to finish early. Coworkers from different functions can clarify the handoffs; they do not require a two-hour presentation.
