# Learn the onramping workflow before Wednesday

The meeting is **Wednesday, October 7, 2026**. Learn one complete chain: **ticket → evidence acquisition → developer context packet → checked citations → useful first investigation**. The [agreed action plan](action-plan.md) defines the implementation. Use the README for installation and [demo prompts](demo-prompts.md) for the five-minute presentation.

**Current verification boundary:** live Claude execution has not been verified and awaits explicit approval for transmitting the synthetic content to Anthropic after an automatic approval-review rejection. Local preflight, retrieval, protocol checks and the labeled sample are independent of that approval. Do not describe them as a successful live model run.

## Sunday, October 4: understand and run it locally

Spend roughly 90 minutes on the application and the six synthetic knowledge records. Manually reconstruct AG-1423's symptom, likely subsystem, execution path, useful starting files, owner, historical context and one unknown. This gives you a reference for judging the packet; do not feed that prepared answer to the agent.

The actual flow is **ScheduleController → ScheduleService → DeviceConfigurationService → ScheduleValidator → ScheduleRepository**. Read where each responsibility lives and how capability resolution reaches validation. The in-memory repository is a demo choice, not an assumed production database.

From the root, install and check the local stack:

```sh
UV_CACHE_DIR="$PWD/.uv-cache" uv sync --extra semantic
uv run python retriever.py --prepare-semantic
uv run python onramp.py --preflight
uv run python onramp.py --sample
uv run python demo_web.py --port 8765
```

The embedding model download is a separate setup step; cache weights before rehearsal. Preflight checks local dependencies, MCP transport, authentication availability and cached model readiness without launching a model task. Read each reported status. The viewer at `http://127.0.0.1:8765` displays saved validated outputs; it does not initiate an agent run.

Inspect the sample's packet and excerpts. It is an explicit deterministic example, not Claude output. Find one company citation and one code citation, then explain how you would check the associated claims. Understand the unknown rather than treating it as decorative cautious wording.

Explain aloud: “Exact fetch gets the known ticket. Search discovers related records. The model chooses what to inspect. The packet organizes supported context for a developer. Validation checks references; a person still checks the claim.”

## Monday, October 5: verify a live packet and align the handoff

After live execution is approved, run:

```sh
uv run python onramp.py AG-1423
uv run python onramp.py AG-1423 --repo-only
```

Observe actual successful ticket fetches, queries, returned sources and native code reads. A requested or denied call is not acquired evidence. The runner uses hybrid retrieval, excludes editing/shell tools, records the configured model, and limits runtime and API budget. Read the trace and validation outcome before trusting the packet.

Both modes receive the same ticket text and application. Company-knowledge tools are the comparison variable. The repository-only model may find the defect; that is a useful result. Compare correct context, ownership/history, starting locations, unknowns and verification effort. Do not define success as forcing a baseline failure.

Start the working session with the packet, not a new architecture proposal. One presenter explains evidence/RAG/MCP. The other shows how an engineer would continue into reproduction, a bounded change, tests and review. Agree who drives and who takes notes. A separate fixing demo is optional; the onramping runner remains read-only.

## Tuesday, October 6: evaluate, drill failures and rehearse

Keep a small results table: **input, expected useful context, actual packet, correctness, completeness, validation status, elapsed time, checking effort**. Include the main ticket, a second ownership/execution-path question, and an unsupported question. Check missing tickets, unavailable MCP, missing embeddings, absent ownership, malformed packet output and timeout.

For each case, inspect:

- Starting files exist, cited lines match, and the locations help someone begin.
- The execution path describes the actual code.
- Ownership and history have retrieved source support; absent facts remain unknown.
- The first investigation is actionable and follows from the evidence.
- The packet is concise, and citations actually support its claims.
- Failure/partial status is visible; application and source files stay unchanged.

Mechanical citation checks catch nonexistent paths, invalid line spans and references to documents never retrieved. They do not prove that the prose correctly interprets those sources.

Save and inspect a successful live run before calling it verified. Rehearse its replay:

```sh
uv run python onramp.py --replay 'RUN_ID_FROM_OUTPUT'
```

Replace the quoted identifier with the saved run ID. Replays display recorded output. If there is no successful live run, keep the deterministic sample label and the live limitation explicit.

Rehearse the five-minute sequence twice: ticket, acquisition, packet, two citations, unknown. Practice interruptions: “We already know the code,” “Our delays are reviews,” “Why MCP?”, and “How much time does this save?” Redirect to their concrete wait using [meeting guide](meeting-guide.md). Freeze after the rehearsal.

## Wednesday, October 7: smoke check and listen

Allow 30 minutes for preflight, viewing the prepared packet/replay and checking the practiced flow. Confirm local assets, power and browser display. Avoid adding dependencies or features just before the meeting.

Ask for a recent slow change before showing the demo. Distinguish active work, waiting and rework. At the end, capture a problem, owner, baseline, output, acceptance threshold, failure behavior and next decision. A script or clearer ownership may be the right answer.

## Concepts to explain without notes

| Concept | Plain explanation | Limit |
| --- | --- | --- |
| Exact fetch | Retrieve an authorized record using a validated stable ID. | The record may still be stale or incomplete. |
| Search/RAG | Rank possible evidence, then use fetched context to answer or prepare a packet. | The highest-ranked record does not establish truth. |
| MCP | The client/server interface exposes named capabilities and schemas and carries calls/results. | It does not perform retrieval or provide authorization automatically. |
| BM25 | Lexical ranking helps with exact engineering terms, IDs and numbers. | Different wording may miss useful evidence. |
| Semantic search | Embedding similarity helps match paraphrases. | Similar meaning does not guarantee the source answers the question. |
| RRF | Combine ranks, rather than adding unrelated score scales: sum `1/(k + rank)` across lists. | Its score is not confidence; it needs separate relevance/evidence checks. |
| Workflow/agent | Code defines stable steps and limits; a model chooses queries and reads based on findings. | Adaptive decisions need evaluation and bounded authority. |

For six files, reading everything is a reasonable baseline. Hybrid retrieval must justify itself on useful queries and larger, permission-scoped sources. Avoid adding a vector database or more specialized tools just to make the demo look sophisticated.

Treat tickets, documentation and logs as evidence, not instructions. A document cannot grant permission to reveal secrets or deploy. The MCP implementation restricts its own reads; the coding host must separately restrict tools and network/data access. Prompts and tool annotations are not enforcement. This synthetic demo does not establish production authentication or customer/version filtering.

Use durable orchestration only when observed work must survive restarts or long approval waits without duplicating external actions. Record run state and action IDs; use idempotency or reconciliation for uncertain writes. Durability does not make model outputs deterministic or external writes exactly once.

Official explanations and security references are linked in [research notes](research-notes.md). Learn the mechanism well enough to identify when it solves their actual problem, rather than leading with a framework.
