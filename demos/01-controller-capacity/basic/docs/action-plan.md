# Ticket-onramping demo — agreed implementation plan

Updated October 4, 2026. This is the current plan for the demo on Wednesday, October 7. It replaces the earlier rollout-eligibility and PR-review proposal. The onramping runner, revised application, evidence validation and saved-packet viewer are implemented. Historical live augmented and repository-only runs both completed on October 4. The repository-only run was faster; see [the comparison](historical-comparison.md). This is the preserved basic variant; the policy-aware variant is now the main meeting demo.

## Goal and presentation

Turn a ticket ID into a concise developer context packet: relevant code, architecture, history, ownership and a first investigation. The packet may identify a defect when supported, but success does not require fixing it or proving that a repository-only assistant cannot find it.

Use **Claude Code for live execution and a clean packet view for the result**. Show actual evidence acquisition in the terminal; display the validated packet there or in the existing browser. The browser is a thin viewer of the same output, not a second agent implementation.

The five-minute meeting sequence:

1. Show the incoming ticket and unfamiliar application.
2. Run the onramping command; show actual lookups, queries, returned sources and code reads.
3. Show the packet, readable in approximately a minute.
4. Open one company-source citation and one code citation; verify their claims.
5. Highlight an unknown and ask which parts an engineer currently reconstructs manually.

Treat Data Honey's team size and mental-bandwidth bottleneck as discovery hypotheses. Do not claim time savings before measuring them.

## Application and evidence

Keep the small irrigation application. Prefer working behavior, tests and consistent documentation over making it look large. Do not create fictitious project history. A genuine existing class/hackathon project could be reused if suitable, but it is not a prerequisite; building another application is outside this plan.

Rewrite AG-1423 as:

> Some Pro customers cannot save schedules after the recent capacity update. The editor accepts the schedule, but saving returns an error.

Keep the underlying Pro 50/Legacy 20 issue and implement the actual flow:

**ScheduleController → ScheduleService → DeviceConfigurationService → ScheduleValidator → ScheduleRepository**

Use an in-memory repository and document it accurately. Preserve response formats and malformed-input handling. The seeded defect is a missing controller argument during capability resolution, causing the resolver to supply its Legacy default for a Pro request. Remove comments announcing the answer from the practice repository; do not obscure legitimate code evidence.

Update the six synthetic documents together:

| Record | Evidence |
|---|---|
| AG-1423 | Customer symptom and affected product |
| Controller limits | Legacy 20 and Pro 50 requirement |
| Architecture | Executable flow, responsibilities, Scheduling Backend owner |
| AG-981 | Capacity requirement and earlier implementation assumptions |
| PR-719 | Frontend update and unchanged backend |
| INC-331 | Related validation failure and workaround |

Label all fixtures synthetic. Company documents, prepared answers, reference fixes, evaluation expectations and meeting notes stay outside the agent's practice repository.

## Retrieval and live runner

Reuse Python, BM25, cached MiniLM embeddings, RRF and the local MCP server. Keep the two tools: exact ticket lookup and engineering knowledge search. Code inspection uses native repository tools rather than the document index.

Hybrid retrieval is the meeting default. Preflight checks verify dependencies, cached weights and actual MCP transport. Missing semantic dependencies produce an explicit error; a deliberately selected BM25 run is labeled. Ranking scores are not confidence probabilities.

Implement:

```text
python onramp.py AG-1423
python onramp.py AG-1423 --repo-only
python onramp.py --replay <saved-run>
```

Fetch the ticket through MCP. Both comparison modes receive the same ticket text and repository; only the augmented Claude run receives company-knowledge tools. Let the agent choose discovery queries and code reads without giving it the answer or prescribed source filenames.

Launch the installed Claude Code client with native Read/Glob/Grep and the demo MCP configuration. Exclude shell and editing tools from onramping. Supply only the synthetic application and permitted documents; client permissions are separate from prompt instructions and MCP annotations.

Use the existing 180-second timeout and $2 API-budget cap. Keep the user's configured Claude model and record its identifier. Capture actual successful tool results. Save a unique run's packet, trace, elapsed time and validation outcome. Denied tools, missing evidence, timeout or malformed output produce failure/partial states, never verified success.

## Packet and browser view

Request structured output, validate it and render concise Markdown. Target 250–300 words excluding citations; flag oversized packets rather than silently deleting evidence.

The packet contains:

- Ticket summary and likely subsystem.
- Up to three starting files, verified lines and reasons.
- Actual execution path.
- Relevant historical decisions and incidents.
- Source-supported owner, or explicitly unknown.
- One concrete first investigation and remaining uncertainties.
- Citations attached to factual sections.

Validate code paths/line spans against the practice application and document citations against successfully retrieved evidence. Include verified excerpts for inspection. Mechanical reference checks do not prove that a citation supports a claim; review that separately.

Reuse the existing browser to display a saved validated packet and cited excerpts, with the model, run time and status visible. It does not initiate model calls. Label saved output **recorded run/replay**. Label deterministic fallback separately; never present it as model output or silently replace a failed live run. No additional frontend framework is needed.

## Verification and credibility

Check the full application path, seeded defect, Legacy boundaries, malformed inputs and architecture consistency. Test requirement, architecture/ownership and history retrieval, exact IDs, unknown tickets, unsupported questions and real MCP calls. Keep evaluation misses visible.

Check packet correctness, useful starting locations, supported ownership/history, actionable next steps and honest unknowns. Reject invented files, owners or history. Verify source hashes remain unchanged after a run. Attempted or denied calls do not count as evidence acquisition.

Compare the same packet task with and without company knowledge: completeness, correctness, elapsed time and exploration. Do not require the repository-only agent to fail. Test a second question, such as ownership or the execution path, and an unsupported question to demonstrate reuse and limits.

Rehearse missing ticket, unavailable MCP, missing embeddings, missing ownership and model timeout. Inspect an actual successful end-to-end run before claiming live verification.

Describe provenance accurately:

> Our class introduced us to some of these ideas. We explored them further and built this prototype to understand how company knowledge could help developers get oriented to a task.

After successful live verification, say this example was tested end to end. Do not present a newly built fixture as a previously deployed school project or claim production reliability. A curated proof of concept is sufficient when its mechanism and limits are clear.

## Build order and completion

1. Update the application and six documents together.
2. Verify behavior, document consistency, retrieval and MCP.
3. Implement the read-only runner, packet validation and terminal output.
4. Add the thin browser packet view using the same saved output.
5. Complete live/repository-only checks, secondary questions and failure drills.
6. Save a verified replay and rewrite the main runbook around onramping.

The demo should be independently runnable before the Monday working session. Use that session to align how the engineering work continues from the context packet. Freeze after Tuesday rehearsals; Wednesday starts with a smoke check.

Completion means one command produces a verified packet from actual tool evidence, citations are inspectable, failure states are honest, source files stay unchanged and the five-minute demonstration has been rehearsed. The local deliverable and deterministic sample are ready. A successful actual Claude run and repository-only comparison are still required to meet the live completion criterion.

Live Claude execution still awaits explicit approval for transmitting the synthetic content to Anthropic after the earlier automatic approval-review rejection. Local application, retrieval and protocol checks are independent of that approval.

Production customer/version filtering, authenticated connectors and Copilot setup are later work. This demo does not claim production access controls, retrieval of undocumented knowledge or proven savings for Data Honey.

## Implementation status

- Implemented the actual controller/service/configuration/validator/repository path and revised all six synthetic documents.
- Added `onramp.py`, strict packet schema/reference checks, captured read spans, source hashes, actual client trace capture, timeout/budget cap and saved replay.
- Added the read-only browser viewer with current citation revalidation, explicit sample/replay labels and failed-run states.
- Prepared a 251-word, source-reviewed deterministic sample from real local MCP calls and code reads. It is not model output.
- Local verification: 133 tests and 18 subtests; actual MCP semantic/hybrid checks passed; hybrid retrieval 10/11, with its miss retained. See [verification evidence](verification.md).
- Remaining: authorized actual Claude rehearsal, inspection of model-generated claims and fair repository-only comparison. No time-saving claim is established.

The first user-run Claude trace completed evidence acquisition but produced a partial packet with citation errors. One bounded evidence/validator feedback pass is now implemented and locally tested; the earlier partial run is retained. Successful live output and comparison still require rehearsal.
