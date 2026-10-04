# Evaluation: correctness first, productivity only with appropriate evidence

## What the fixture experiment establishes

Ten synthetic cases have separately specified decisions, totals, problem rows and required sources in `acceptance/expected.json`. The MCP server exposes the cases and source documents, never this answer file. Acceptance checks are outside the agent's tools. They are independent of the execution path but authored as part of the same demo, so they are not blind external validation.

The seeded application, naive sign change and prepared policy workflow are deterministic controls. They establish that a locally plausible patch can be wrong and that total-only checking can miss cancelling errors. They are not estimates of analyst or assistant performance.

Source hashes establish which content was acquired, not whether every claim follows from it. The evaluator checks exact decisions, cents, row sets and source IDs. Human reviewers must still assess the explanation, source applicability, meaningful omissions and whether the next action is useful.

## The live model comparison

Freeze all ten cases, documents, application, oracle and runner before running. The CLI writes the plan before any attempt and rejects drift between trials. Use the same provider settings, model and resource limits. Actual model IDs are recorded; a comparison with differing or unrecorded models is not a verified same-model comparison.

All conditions receive the same ticket, raw input, account profile, deployed configuration, code and executed current ledger:

1. **Provided:** the entire document corpus is also in the prompt. This controls for having the necessary information.
2. **Retrieval:** that corpus is available through search/full-document tools. No reconciliation tool is exposed.
3. **Workflow:** the same tools plus the deterministic reconciliation engine. Any difference includes the benefit and cost of prepared workflow software.

Do not use “repo-only guessed incorrectly” as proof of intelligence or productivity. Without an approved business definition, reporting uncertainty may be the correct response. Likewise, with ten short documents, direct context may be faster than retrieval; retain that result if observed.

The runner rotates condition order across cases and repetitions, uses fresh client sessions, runs sequentially, and keeps failed attempts and their elapsed time. A failed tool call, denied tool, timeout, invalid output or changed evidence is recorded as failure. There are no automatic repair retries. Each planned repeat adds 30 attempts; repeating the same ten cases does not create more independent business cases. Provider caching, service load and model nondeterminism remain possible influences.

Raw traces remain local and ignored. Summaries include every attempted duration, total attempted time, accepted counts, actual model IDs and an explicit null productivity estimate. “Completed” means the client returned valid output; acceptance is a separate field. “Accepted” means automated fixture checks passed; human approval is separate again.

Before sharing a run, inspect its structured packet, source evidence and private trace. Preserve failed runs. Do not publish credentials or unrelated context from logs. The committed preflight and blocked-comparison records show zero actual model attempts for this revision.

## A pilot that can test business value

Pick one workflow after discovery, then collect resolved, appropriately approved cases with final resolutions withheld from investigators. Include ordinary, difficult and no-action cases; sample from the actual mix instead of selecting only demonstrations that favor the new tool.

Compare the team's current process (including tools they already use) with the proposed workflow. Counterbalance case order and personnel where practical so familiarity does not simply favor the second attempt. Agree success criteria before seeing results. Obtain sufficient independent cases based on observed variation and the minimum worthwhile improvement; two runs do not support a productivity estimate.

Measure **time to an accepted decision**, including document acquisition, waiting, human review, corrections and retries. Also record wrong-fix rate, inappropriate escalation or refusal, correct missing-evidence stops, reopened cases and handoffs. Separate active work from elapsed waiting time.

Report preparation and maintenance costs: document normalization, rule approval, connector configuration, permissions, source freshness, validation and review. A pilot can save per-case time and still have poor economics at low case volume. If existing SQL, tests or a simple validator solve the stable problem cheaply, use them. An agent is most plausible where evidence acquisition and coordination vary enough to justify it.

Keep the result phrased at its actual scope: “On these cases, under this process, accepted decisions took X with Y errors and Z setup cost.” Do not turn model latency or a selected successful run into a claim about employee productivity.
