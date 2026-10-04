# Wednesday meeting guide

**Wednesday, October 7, 2026.** Aim to understand one real development bottleneck and agree on a small, measurable experiment. The demo now focuses on **ticket onramping**: helping a developer reconstruct the code, architecture, history and ownership needed to start a task. It does not require writing a patch or proving that a repository-only assistant fails.

The supplied [LinkedIn profile](https://www.linkedin.com/company/data-honey/) identifies Data Honey, LLC and links to [datahoney.com](https://www.datahoney.com/). Public product descriptions support asking about DataLink, CleanSlate or custom-client software. Their stack, team responsibilities and bottlenecks remain discovery questions; see [research notes](research-notes.md). The irrigation application and six knowledge records are synthetic.

## A useful 40-minute agenda

| Time | Purpose |
| --- | --- |
| 0–4 min | Establish their product/team context and a useful outcome for the discussion. |
| 4–14 min | Trace one recent change that was slow or required repeated clarification. |
| 14–19 min | Five-minute ticket-onramping demonstration. |
| 19–24 min | Inspect citations and discuss what the packet adds to repository-only context. |
| 24–34 min | Map the technique onto their actual wait, missing information or rework. |
| 34–40 min | Write one pilot with an owner, baseline, acceptance criteria and failure behavior. |

For a shorter meeting, shorten the introduction and comparison. For a longer meeting, inspect a second anonymized real example. Ishaan drives onramping; your friend takes notes and explains how an engineer would continue from the packet into reproduction, coding, tests and review. Align that handoff on Monday.

Opening:

> “We built a small prototype that turns a ticket into a developer context packet using code and company evidence. The example is fictional. We'd like to understand what your engineers reconstruct before starting work, and where that effort or the later handoffs cause delay.”

## Start with an example

Ask: **“Could you walk us through one recent change from request to release that took longer than it should have?”** Follow the evidence rather than reading a questionnaire.

- What triggered it, and how did you know what finished meant?
- What context did the developer need before acting? Where did it live?
- Who knew the history or business rule? What happened when they were unavailable?
- Where did work wait, who was expected to act next, and why?
- What was repeated, reopened or clarified? Can you show another similar case?
- Was the missing input a documented fact, an undocumented fact, or a decision nobody had made?
- What would you trust a system to prepare? What would still need approval?

Record **step, owner, active work, waiting, rework reason**. Ticket status duration is not active effort: a PR waiting for a reviewer differs from a developer spending two hours reconstructing a requirement. Do not treat a small team's mental bandwidth as a confirmed problem until they describe it.

## The five-minute demonstration

Use [demo prompts](demo-prompts.md) for commands and the task. Run preflight before the meeting. The basic variant has two historical live runs; see [the comparison](historical-comparison.md). Fresh runs still require the configured client and runtime. A deterministic sample must be labeled as a sample.

1. **40 seconds:** show AG-1423's vague symptom and the small unfamiliar application. Ask what a developer needs before investigating.
2. **Up to two minutes:** run onramping and show actual ticket lookup, search queries, returned evidence and code reads. The agent chooses discovery steps; the tool implementation fetches and ranks evidence.
3. **One minute:** show the concise packet: relevant files, actual execution path, history, supported owner, first investigation and uncertainties.
4. **50 seconds:** open one company citation and one code citation. Check the claim against the excerpt and lines.
5. **30 seconds:** highlight a meaningful unknown and ask which context they currently reconstruct manually.

The application executes **ScheduleController → ScheduleService → DeviceConfigurationService → ScheduleValidator → ScheduleRepository**. The repository is in memory. The packet should discover what matters through actual evidence; do not seed the agent's prompt with the broken function or requirement threshold.

If the live run stalls, use a previously verified saved run and announce that it is recorded. If only the local deterministic sample exists, show it with that label. Retain the failure state and return to discovery rather than debugging credentials in front of the customer.

Compare augmented and repository-only packets fairly: both receive the same MCP-fetched ticket and repository. The augmented run also has company-knowledge tools. The repository-only run may find the code defect. Compare **correctness, context completeness, useful starting points, ownership/history, unknowns, elapsed time and checking effort**. More text or more tool calls is not automatically better.

Provenance:

> “Our class introduced us to some of these ideas. We explored them further and built this prototype to understand how company knowledge could help developers get oriented to a task.”

Use “tested end to end” only after a successful live run has actually been inspected. This is a curated prototype, not evidence of production reliability or customer time savings.

## Adapt to what they describe

Use **recent example → actual wait → missing input → smallest intervention → pilot**. Reflect the diagnosis back before prescribing architecture.

| Pain | Clarify first | Candidate intervention and measurement |
| --- | --- | --- |
| Slow task onramping | Finding code, reconstructing history, ownership, or missing decisions? | Read-only context packet; correct context and total time including verification. |
| Vague requirements | Which decisions are missing, and who can make them? | Draft acceptance criteria and unresolved questions; clarification rounds/reopens. |
| CI failures | Code defect, flaky test, dependency outage, or runner capacity? | Deterministically collect logs, then draft an evidence-backed diagnosis; diagnosis accuracy/time. |
| Long PR queues | Reviewer unavailable or reading/context effort too high? | Fix routing/ownership first where needed; otherwise prepare a concise cited summary; wait and active review time separately. |
| Stale docs | Which accepted changes should update which authoritative documents? | Draft doc changes for the owner; missed and incorrect updates. |
| Repetitive releases | Stable checks versus go/no-go decisions? | Script stable checks and draft notes; preparation time, omissions and recovery. |
| Work spans days/approvals | Must it survive restart without repeating writes? | Persist state; add durable orchestration only if demonstrated recovery needs justify it. |

A retrieval system cannot recover undocumented facts or settle an undecided requirement. Faster patch generation cannot create an available reviewer. A stable script may solve the problem. Say so when the evidence points there.

## Capture one pilot

Fill this together:

```text
Problem and recent examples:
Accountable owner and human reviewer:
One trigger and one useful output:
Allowed sources/repositories and identities:
Allowed actions; actions needing approval:
Baseline: comparable cases, active effort, waiting, correctness:
Success target and correctness threshold:
Evaluation: historical cases, unseen/shadow cases, failure drill:
Failure behavior: unknown/escalation, retry limit, run record, recovery:
Stop conditions and next decision date:
```

If discovery supports onramping, a candidate is one service, read-only access, ten historical tasks and five new shadow cases. The output is a short packet with inspectable evidence and unresolved questions. Include failed runs and human checking time in the comparison. Agree targets after measuring the baseline; the fixture demo supplies no ROI estimate.

## Answers to rehearse

| Question | Honest answer |
| --- | --- |
| “Why not paste everything into a chat?” | That may be enough for six files. Tools become useful when evidence changes, access varies, or locating the correct sources is recurring work. Compare the simpler baseline. |
| “Why an agent rather than a script?” | Scripts enforce stable steps. A model can choose queries and next code reads based on findings. Use that flexibility only where needed. |
| “Does MCP make it safe?” | MCP defines a capability interface. Actual server/host permissions enforce access. Read-only annotations and prompt instructions alone do not. |
| “Can it hallucinate?” | Yes. Inspect citations, check usefulness/correctness, record errors and preserve unknowns. Mechanical citation validation does not prove semantic support. |
| “What if company docs are wrong?” | Surface conflicts and freshness; ask the authoritative owner. Do not silently convert stale text into a requirement. |
| “Will it save us time?” | We do not know yet. Measure reconstruction plus checking and failure recovery on comparable tasks. |
| “Can it fix or deploy the change?” | This runner only prepares context. Your existing implementation, review and release process remains the handoff; broader actions require a separate demonstrated need. |

Primary technical guidance is linked in [research notes](research-notes.md). The meeting's main result is an evidence-backed bottleneck and a reviewable pilot definition.
