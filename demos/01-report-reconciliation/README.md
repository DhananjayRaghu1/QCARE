# Three business-context demos

The [site home](http://127.0.0.1:8768/) contains three separate workflows. Each has an original request, linked sources, inspectable code, a prepared example and a dedicated proposed production architecture page. Demo 1 has raw repo-only and docs-plus-Jira investigations; Demos 2 and 3 lead with workflows whose business context can be switched on or off.

| Demo | Result | Workflow and architecture |
| --- | --- | --- |
| [Investigate a report](http://127.0.0.1:8768/demos/report) | DH-301 only: justify $1,250 rather than either starting total | [Production design](http://127.0.0.1:8768/architecture/report) |
| [Implement a customer export](http://127.0.0.1:8768/demos/export) | LangGraph workflow (ticket → context → conflicts → build → review → check ↺ → developer), patch and independent acceptance checks | [Production design](http://127.0.0.1:8768/architecture/export) |
| [Check a cleanup before release](http://127.0.0.1:8768/demos/migration) | Green candidate CI, synthetic replay losses, sourced dependencies, per-dependent gates and local action drafts | [Production design](http://127.0.0.1:8768/architecture/migration) |

The live ticket selector has been removed; DH-302 through DH-310 remain developer regression fixtures only. Their historical records are preserved. Production pages describe real-system retrieval, permission boundaries, evidence combination, verification and human review; they do not claim those connectors are deployed.

## Demo 1: Which total can we defend?

A customer says their monthly report is wrong. The application shows **$1,550**; their spreadsheet shows **$1,150**. Approved business definitions and export contracts show that **both are wrong: the correct total is $1,250**.

This is the recommended meeting demo. It makes business context necessary to choose a justified action, rather than adding documents to an obvious code bug. All accounts, transactions, documents and Jira records are synthetic. They do not describe Data Honey's actual systems.

## Run it

Install [uv](https://docs.astral.sh/uv/) and run these commands from this directory. The pinned Python version avoids relying on a system Python installation.

```sh
uv sync --locked
uv run python demo.py live
```

Open [the demo hub](http://127.0.0.1:8768/) and choose a workflow. Each **Run investigation** click starts a fresh Claude Code session using your existing Claude login. Sign in with `claude auth login` if needed. No API key is required when your Claude subscription supports the client. The page shows real tool calls and results as the CLI emits them, the model's final answer, elapsed time, reported model and cost, and a downloadable run record. Stop cancels the subprocess. No automatic retries or precomputed substitute answers.

DH-301 has a plain-language title, customer situation, prominent original request, decision to investigate and explanation of why it matters. The page shows both starting amounts in dollars, explains what the difference means, and includes reporting terminology plus transaction dates and deployed settings. Start with DH-301, then compare the two raw modes. These reader guides exist only in the browser page; they are not added to model prompts or task files. Run history is filtered to the selected ticket, and completed answers are labeled with their saved time.

**ATLAS is the fictional upstream system that supplies transaction exports**, separate from the reporting application, the customer and the AI. The page maps that flow and explains every customer, team and data field. Document references in the case, answer and activity log open the complete source with its owner, approval status, scope and effective dates. Each source also has a standalone local page, such as [the ATLAS v1 contract](http://127.0.0.1:8768/documents/FEED-ATLAS-1). A searchable reference desk contains all ten snapshots. These links point to local demo records, not an external Jira account.

The reporting demo also has an optional **worked example**, clearly labeled as a prepared rule-engine explanation rather than a model run. It shows the approved policy, each row's current and required contribution, the calculation and the next action. Missing rules, conflicting agreements and invalid data produce an explicit stop. Opening these reader explanations does not add them to a model session.

| Live mode | What the model receives |
| --- | --- |
| **Raw · repo only** | The customer issue, extracted application code, neutral README and five baseline tests; ordinary file and shell tools |
| **Raw · docs + Jira** | Exactly the same prompt, code and tools, plus ten prose source snapshots as Markdown files |
| **Guided workflow** | The existing prescribed investigation task, structured answer schema, read-only evidence MCP and deterministic reconciliation calculator |

The two raw modes use Claude Code's default system prompt and an editable short user prompt. There is **no diagnostic harness**: no required investigation steps, answer schema, hidden grading, calculator, machine-readable policy rules, reference patch or prior outputs. The browser is a launcher and recorder. A fresh temporary directory, disabled customizations/connectors, a four-minute timeout and a $1 CLI budget bound each attempt. A read-only investigation is requested and changes to supplied files are checked afterward; native shell access is not an OS read sandbox. The raw modes are not an exact reproduction of Sam's personal setup. The five baseline tests are prepared demo tests.

Run both raw modes on the same case without changing the prompt to compare the effect of providing context. An appropriate clarification request is a useful outcome. Guided mode adds software and instructions, so its result cannot establish that retrieval alone helped. All source material remains synthetic; **live model execution does not mean a live Jira or business-doc connector**.

Records, exact raw inputs, prompts and private CLI traces are saved under ignored `artifacts/live/<run-id>/`. The latest 30 finished runs reappear after a server restart. Runs that fail or are cancelled remain visible. The server binds only to `127.0.0.1`, validates request origin and requires a page-issued token to start or cancel a run.

Local browser verification on October 4, 2026 used DH-301 in all three modes. The successful raw repo run took 23.612 seconds, ran all five baseline tests and asked for the schema rule; it also made an overconfident claim about the discrepancy size, so the raw response still needs review. The raw docs run took 25.989 seconds, ran the same tests and supported 125000 cents using the source contracts. The guided run took 14.304 seconds and passed the existing fixture checks, but its input included a scenario title that hinted at the diagnosis. **That historical guided result is not a fair comparison with raw runs.** New guided prompts and the MCP case tool omit these titles; the UI flags affected historical runs without changing their saved files. All three reported `claude-opus-5-5`. An earlier 27.743-second raw attempt encountered a shell permission denial; it is retained as failed in local history, and the launcher was corrected before the successful run. These are implementation smoke tests with one synthetic case, not a controlled productivity study. No model patches were applied.

For an offline presentation with no model calls:

```sh
uv run python demo.py present
```

Open the generated `artifacts/presentation.html` in your browser. It works offline, lets you select all ten cases, shows row contributions, and expands the exact source snapshots. To serve it locally instead:

```sh
uv run python -m http.server 8767 --bind 127.0.0.1 --directory artifacts
```

Then open [the presentation](http://127.0.0.1:8767/presentation.html). No model login, API key, Jira account or hosted service is required for this path.

The terminal version and checks are:

```sh
uv run python demo.py run DH-301
uv run python demo.py document FEED-ATLAS-1
uv run python demo.py reproduce
uv run python demo.py controls
uv run python -m pytest -q
```

`reproduce` runs a real row-level regression in three separate processes. The original implementation and the tempting fix fail; the prepared reference implementation passes. The command itself returns success only if that exact fail/fail/pass pattern occurs. The reference is written in advance and labeled as such; it is not an agent-generated patch.

## The first case, exactly

The input is a September net-sales complaint, the customer's assigned reporting profile, five export rows, the deployed report configuration and the report code. Relevant evidence includes the approved reporting definition, two format contracts and a Jira rollout history. The older signed format and newer magnitude format coexist.

| Row | Export format | Record | Raw amount | Current contribution | Required contribution |
| --- | --- | --- | ---: | ---: | ---: |
| A-1 | Schema 1: signed | Sale | $1,000 | $1,000 | $1,000 |
| A-2 | Schema 1: signed | Return | −$200 | +$200 | −$200 |
| A-3 | Schema 1: signed | Return reversal | +$50 | −$50 | +$50 |
| A-4 | Schema 2: magnitude | Sale | $500 | $500 | $500 |
| A-5 | Schema 2: magnitude | Return | $100 | −$100 | −$100 |
| **Total** | | | | **$1,550** | **$1,250** |

The current code negates every return. A developer might replace that with `-abs(amount)` and reproduce the customer's **$1,150**. That is still wrong: schema 1 says a positive return is a reversal and must remain positive. A generic “returns are negative” rule loses that meaning.

The justified repair is schema-specific normalization. Schema 1 preserves signed amounts; schema 2 converts return magnitudes to negative contributions and rejects negative magnitudes as invalid. The application uses approved versioned configuration; it does not call an LLM while processing transactions. See the [seed application](app/report.py), [prepared reference](controls/reference_report.py), and [independent regression](controls/reported_case.py).

The output is an evidence packet: a decision, exact total or explicit uncertainty, affected row IDs, before/after contributions, source snapshots with hashes, and a next action. The workflow does not change the production application, close tickets or send customers messages.

## Archived reporting regression scenarios

The extra cases below are retained for automated regression coverage and the legacy offline presentation. They are not selectable or runnable through the live meeting site.

| Case | Context that matters | Justified result |
| --- | --- | --- |
| DH-301 | Two approved format contracts; signed reversals | Calculation defect; $1,250, not either proposed total |
| DH-302 | Customer-specific invoice-date addendum | Report's $600 is correct; explain the reporting period |
| DH-303 | Approved definition excludes transfers; Jira request is pending | Report's $800 is correct; a request does not authorize a change |
| DH-304 | Only a draft contract exists for schema 3 | Stop; obtain an approved definition |
| DH-305 | Two equally applicable approved customer definitions conflict | Stop; Reporting Product must resolve the conflict |
| DH-306 | October policy is newer but not effective in September | September's $400 remains correct |
| DH-307 | October policy is effective but old configuration remains deployed | Configuration defect; $600, not $1,000 |
| DH-308 | Schema 2 requires nonnegative magnitudes | Stop; quarantine the invalid source row |
| DH-309 | A positive signed return reverses an earlier return | Calculation defect; $1,000, not $800 |
| DH-310 | Two signed row errors cancel in the aggregate | Calculation defect despite both totals being $1,000 |

This separates engineering work, customer explanation, product approval and data-quality work. The useful hypothesis for the meeting is that assembling this evidence can reduce unnecessary handoffs and incorrect fixes. Whether those benefits occur at Data Honey must be tested on their workflow.

## What is implemented, and what is measured

The guided and offline paths use a **working deterministic reconciliation workflow**, with read-only MCP tools and an optional agent interface. Their source snapshots contain prose plus **hand-authored structured rules**. The engine selects those rules by customer/profile, schema, approval status and effective month; it does not extract arbitrary prose into reliable executable policy. Preparing and maintaining those adapters is real work. Raw live mode receives only the application and optionally prose documents; it has no access to this engine or the structured rules.

The recorded fixture checks are:

| Prepared implementation | Correct totals where a total is justified | Correct stops on missing/conflicting/invalid inputs |
| --- | ---: | ---: |
| Current arithmetic | 4/7 | 0/3 |
| Force all returns negative | 3/7 | 0/3 |
| Approved-rule workflow | 7/7 | 3/3 |

The workflow also passes all ten case-level checks for decision, total, affected rows and required source IDs. These are ten hand-authored synthetic cases, not a representative test population. The two arithmetic controls are **not coding-assistant baselines**. Their missing citations are not evidence that an AI or analyst would fail.

[Recorded results](recordings/controls.json), [regression results](recordings/regression.json), and [verification notes](docs/verification.md) preserve what was actually executed. The original CLI comparison preflight was **blocked by an unauthenticated client**; that is a historical result, not a requirement that live mode remain blocked. A subsequent [actual two-run Codex comparison](docs/codex-comparison.md) found that business documents enabled a justified, tested patch, while repo-only correctly asked for clarification. The document run took longer: 95.2 seconds versus 50.5 seconds. No speedup or employee-productivity result is claimed. The [older controller results](../01-controller-capacity/policy-aware/docs/comparison-results.md) remain intact, including their limitations.

## Optional live agent comparison

With an authenticated Claude Code client, run one investigation:

```sh
uv run python demo.py preflight
uv run python demo.py agent DH-301 --context workflow
```

This sends the synthetic task to Claude's configured provider. It exposes only read-only evidence tools and the optional calculator; native shell/file tools and ambient MCP configurations are disabled. The caller inherits a configured model if present and records the actual model from the trace. This is a tool-level restriction, not an OS sandbox. Human review of the explanation remains separate from automated fixture checks.

Three conditions distinguish different sources of value:

| Condition | Available information and tools | What it tests |
| --- | --- | --- |
| `provided` | Same case, code, current output, and all documents in the prompt | What the model can do when someone has assembled the context |
| `retrieval` | Same case/code/output; same documents through search and full-source tools | Whether automatic evidence acquisition helps |
| `workflow` | Same evidence tools plus deterministic reconciliation | Whether a reusable validated workflow helps execution |

The last condition adds software, so it cannot establish that retrieval alone caused an improvement. The directly supplied documents are a meaningful control; deliberately withholding the required policy would make guessing an unfair baseline.

```sh
# Saves a fixed 30-trial plan without any model calls.
uv run python demo.py benchmark --name rehearsal-plan --plan-only

# Explicitly requests 30 fresh model attempts, subject to timeout and per-attempt budget.
uv run python demo.py benchmark --name comparison-1 --repeats 1 --timeout 180 --budget 0.50
```

Use a new name each time. Every condition receives every case; order rotates, evidence and runner hashes are frozen, and failures stay in the record. No automatic retries or selection of the fastest successful run. Outputs and private traces stay under ignored `artifacts/`. See the [evaluation protocol](docs/evaluation-protocol.md) before interpreting results. The live UI runs are individual investigations, not this full counterbalanced benchmark.

## Present it and discover the real workflow

Use [the meeting script](docs/meeting-guide.md). Lead with DH-301, then choose the export or migration demo based on the audience’s workflow.

The scope of demo 1 is **one monthly report discrepancy → a reviewable decision and next action**. Live enterprise connectors, automatic policy extraction, general root-cause diagnosis, autonomous deployment and a productivity estimate are outside the implemented scope.

If their reporting rules are stable and code can already answer the question, ordinary software may be the best solution. If people repeatedly search business docs, Jira history and account configuration to decide what should happen, an assistant connected to those sources and reliable calculation tools is a reasonable pilot. The meeting should identify which situation applies.


## Demo 2: Requirements become a reviewable implementation

`portfolio/export/` contains a small working invoice exporter, two existing tests, a neutral request and five sample rows. Four source snapshots supply the approved Northstar settlement requirements, Finance rules, Jira scope and a later unapproved draft. The approved behavior uses America/New_York settlement dates, subtracts fees from paid amounts, does not refund processing fees, ignores unsettled records, validates included money/currency and preserves other customers’ invoice exports. September’s prepared CSV contains N-103 at -5000 cents and N-102 at 19400 cents: net $144.

Both live modes can edit `app/exporter.py` and add test files in an isolated temporary workspace. Protected inputs are checked after the run; the resulting patch and generated files are saved under ignored `artifacts/live/<id>/`. The repository is never automatically patched. Twelve independent acceptance checks are supplied only after the model finishes, alongside the repository tests. A clarification-only response has no implementation to grade. A completed model run can still have failing checks.

The prepared reference is not model-generated. It passes all 12 independent checks and both baseline tests; the original exporter passes its baseline tests but fails the new acceptance requirements. No new paid model runs were made to claim a docs-versus-repo outcome for this demo.

### The engineering workflow (LangGraph)

The Demo 2 page leads with a live workflow that takes DH-401 from ticket to a reviewed pull request, with a person in the loop. A **Business context: On / Off** switch runs the same workflow as its own control. The older single-session Repo-only/Docs comparison stays in the code but is no longer shown on the page.

```text
intake → analyze ─┬─ blocking conflict ─→ ask_developer ─┬─ recommended or "I don't know" ─→ implement
                  │                                     └─ other option or a note ─→ analyze (short re-check)
                  └─ ready ─→ implement → review → check_requirements ─┬─ revise (≤ 3 rounds) ─→ implement
                                                                        ├─ needs the rule owner ─→ developer_review
                                                                        └─ accept, or round limit ─→ developer_review
developer_review ─┬─ approve ─→ finalize (draft PR marked ready)
                  └─ instructions ─→ analyze (short re-check) ─→ implement
```

- **One fresh Claude Code session per model step** (`claude_session.py`): analyze, implement and review. Each uses your login, `claude-opus-5-5` by default (`demo.py live --workflow-model` overrides it), only the tools its role needs, a JSON schema for its output, a per-step budget and timeout, and an $8 cap for the whole workflow. The flags are the raw modes' restricted flags, minus `--safe-mode`, which would also disable MCP.
- **Context on vs off.** With context on, code follows the ticket's link to DH-411, and the analyst, engineer and reviewer get read-only Jira/Confluence tools. With it off (the control), they see only the ticket text, the developer's note and the repository. Everything else is identical: model, loop, review, rules, git and grading. The comparison card at the top of the results shows the latest run of each.
- **Retrieval** (`context_mcp.py`). Read-only MCP tools (`jira_search`, `jira_get_issue`, `confluence_search`, `confluence_get_page`) over all 21 synthetic records from the three demos, so the analyst must filter by scope, status and dates. Results carry owner, status, scope, effective dates, version, SHA256 and retrieval time. Demo 1's hand-authored calculator rules are stripped. No vector index; at this size, search then fetch is enough.
- **Requirements.** About 8–12 grouped requirements, each with a word-for-word quote and an acceptance test that follows only from those words. The workflow verifies every quote against a record whose hash shows it was actually opened.
- **Decisions.** The workflow pauses before coding when a conflict needs a person. Choosing the recommended option, or "I don't know; use your best judgment" (recorded as an assumption), is applied in code with no extra model call. Another option, a note, or a send-back after review gets a short delta re-check that returns only what changed. Overriding an approved rule is recorded as needing the owner's sign-off. After two answers it stops asking and builds on recorded assumptions.
- **The acceptance gate is code, not a model** (`guard_reasons`). The independent reviewer judges every requirement as met, unmet or unclear, with evidence. The gate accepts only when the tests the workflow ran pass, every requirement is met, there is no high or medium finding, the tested commit is pushed, nothing is uncommitted, `main` is unchanged, and a PR exists only if one was asked for and is still a draft. If the reviewer marks a finding as one only the rule owner can settle, the gate escalates it to you instead of looping the engineer.
- **The answer key never enters the loop.** The 12 hidden acceptance checks run only for a separately labeled "Demo grading" panel and the comparison card. No prompt or routing decision sees them.
- **Branches and pull requests.** The engineer works in a clone of a sandbox repository on its own branch (`dh-401/workflow-<id>`, or `dh-401/control-<id>`). It commits, pushes, and opens a **draft** PR only when the ticket, a linked record or the developer note asks for one. Its shell is an allow-list (python3, ls, read-only git, `git add/commit/push`, and `gh pr create/view/list` only when a PR was requested); anything else is refused and shown on the page as a blocked action. The reviewer gets a copy with no remote. Approving marks the draft PR ready for review. Nothing is ever merged.
- **Sandbox setup.** By default the workflow pushes to a local bare repository under `artifacts/sandbox/`. To push real branches and PRs, create a private GitHub sandbox once with `uv run python demo.py sandbox-init --repo <you>/datahoney-export-sandbox` (needs `gh auth login`), then start with `uv run python demo.py live --sandbox-repo <you>/datahoney-export-sandbox`. Each clone authenticates through your `gh` login with a repository-local credential helper; global git settings are unchanged.
- **Records and replays.** `artifacts/live/workflows/<id>/` keeps events, the result, and each step's prompt, trace, stderr and output, plus `final.patch`. To save a run for the page's replay picker, use `uv run python demo.py record-workflow <id>`; it accepts a completed run or one stopped at the final review. The committed recordings are one run with context and one without, both on Opus 5.5.

## Demo 3: Release-check a teammate's cleanup

A change in common code can conflict with customer and recovery promises the repository cannot establish. The original retirement request, prepared worked example and two seed tests remain available under `portfolio/migration/`. Only the two sentences that directly state the retirement verdict were removed from the business records; the underlying facts, scope and obligations remain.

The release check reviews a **prepared local candidate PR**, not a real GitHub PR. Its patch removes v1 decoding, narrows the jobs' accepted versions and deletes the replay test that would catch the loss. The remaining repository tests pass. Replaying the same synthetic job rows before and after the patch shows the failure CI misses: **NORTHSTAR September falls from $1,250 to $400; CEDAR statements fall from $180 to $0**. Rows are skipped by the job filter, so the decoder never raises an error.

The LangGraph workflow reuses Demo 2's Claude session, checkpoint and recording infrastructure. One read-only Opus session traces the dependencies and opens evidence through the existing synthetic-source tools. With business context on, its map must tie the live job, historical replay, Cedar delivery and rollback dependencies to exact quotes, current versus stale usage, accountable owners, required sign-offs and a conditional earliest retirement date. Code then returns an **allow or block for each dependent**, using explicitly authored policy adapters for this synthetic scenario. The model does not create or approve executable business policy. A developer note is recorded as a request; it cannot override a missing source, approval, replay proof or rollback requirement.

The workflow pauses for your decision: defer removal, pursue a scoped canary, or request sign-off. It then prepares a PR review comment, sign-off requests and a decision-record update as local drafts. Selecting an option does not grant customer approval or clear blocked dependencies. Nothing is sent, no sandbox PR is created or commented on, and shared support is not removed.

With context off, the same workflow sees the candidate patch, code callers and code owners, CI and synthetic replay results. It can still identify those losses and block for missing evidence. It cannot establish sourced customer obligations, approval owners or retirement dates from those inputs. Twelve hidden checks grade the completed outputs in a separate comparison panel; they are unavailable to the model, prompts and release gate. Do not present a prepared fixture result as a live Opus score.

```sh
# Offline code/fixture verification; no model call.
uv run python migration_demo.py verify

# One read-only model session, then a pause for the developer's decision.
uv run python migration_demo.py run --context on
uv run python migration_demo.py run --context off

# Preserve a completed workflow for browser replay.
uv run python migration_demo.py record <workflow-id> --name <recording-name>
```

**December 30, 2026 is a conditional lower bound, not a promised removal date.** The synthetic replay fixture's latest archived v1 export is September 30; its 90-day original-format replay obligation covers December 29 inclusive, making December 30 the first possible day after that window. Cedar's separate delivery promise runs through November 30. Full removal remains unknown until customer migration, retention expiry or verified conversion, backup readability, rollback readiness and fresh usage are established. Read the [release-check guide](docs/migration-release-check.md) for the workflow, comparison rules and evidence limits. Saved live recordings and their actual scores, when available, belong in the [results index](../../results/INDEX.md).

## Production integration versus local execution

The architecture pages explain a proposed production flow: request and user scope → authorized Git/Jira/Confluence/operations retrieval → full evidence with versions and dates → explicit claims or requirements → independent checks → human approval. An optional permission-aware index helps discovery; it is not necessary to put the entire repository in a vector database.

Locally, the reporting raw modes receive file snapshots. Its separately labeled guided mode uses the local evidence MCP server and prepared calculator. The export and migration workflows use read-only MCP tools over synthetic source snapshots; they do not connect to live Jira, Confluence or operational telemetry. Source pages and prepared examples incur no model calls.
