# Demo 1: Which total can we defend?

A customer says their monthly report is wrong. The application shows **$1,550**; their spreadsheet shows **$1,150**. Approved business definitions and export contracts show that **both are wrong: the correct total is $1,250**.

This is the recommended meeting demo. It makes business context necessary to choose a justified action, rather than adding documents to an obvious code bug. All accounts, transactions, documents and Jira records are synthetic. They do not describe Data Honey's actual systems.

## Run it

Install [uv](https://docs.astral.sh/uv/) and run these commands from this directory. The pinned Python version avoids relying on a system Python installation.

```sh
uv sync --locked
uv run python demo.py live
```

Open [the live investigation UI](http://127.0.0.1:8768/). Each **Run investigation** click starts a fresh Claude Code session using your existing Claude login. Sign in with `claude auth login` if needed. No API key is required when your Claude subscription supports the client. The page shows real tool calls and results as the CLI emits them, the model's final answer, elapsed time, reported model and cost, and a downloadable run record. Stop cancels the subprocess. No automatic retries or precomputed substitute answers.

| Live mode | What the model receives |
| --- | --- |
| **Raw · repo only** | The customer issue, extracted application code, neutral README and five baseline tests; ordinary file and shell tools |
| **Raw · docs + Jira** | Exactly the same prompt, code and tools, plus ten prose source snapshots as Markdown files |
| **Guided workflow** | The existing prescribed investigation task, structured answer schema, read-only evidence MCP and deterministic reconciliation calculator |

The two raw modes use Claude Code's default system prompt and an editable short user prompt. There is **no diagnostic harness**: no required investigation steps, answer schema, hidden grading, calculator, machine-readable policy rules, reference patch or prior outputs. The browser is a launcher and recorder. A fresh temporary directory, disabled customizations/connectors, a four-minute timeout and a $1 CLI budget bound each attempt. A read-only investigation is requested and changes to supplied files are checked afterward; native shell access is not an OS read sandbox. The raw modes are not an exact reproduction of Sam's personal setup. The five baseline tests are prepared demo tests.

Run both raw modes on the same case without changing the prompt to compare the effect of providing context. An appropriate clarification request is a useful outcome. Guided mode adds software and instructions, so its result cannot establish that retrieval alone helped. All source material remains synthetic; **live model execution does not mean a live Jira or business-doc connector**.

Records, exact raw inputs, prompts and private CLI traces are saved under ignored `artifacts/live/<run-id>/`. The latest 30 finished runs reappear after a server restart. Runs that fail or are cancelled remain visible. The server binds only to `127.0.0.1`, validates request origin and requires a page-issued token to start or cancel a run.

Local browser verification on October 4, 2026 used DH-301 in all three modes. The successful raw repo run took 23.612 seconds, ran all five baseline tests and asked for the schema rule; it also made an overconfident claim about the discrepancy size, so the raw response still needs review. The raw docs run took 25.989 seconds, ran the same tests and supported 125000 cents using the source contracts. The guided run took 14.304 seconds and passed the existing fixture checks. All three reported `claude-opus-5-5`. An earlier 27.743-second raw attempt encountered a shell permission denial; it is retained as failed in local history, and the launcher was corrected before the successful run. These are implementation smoke tests with one synthetic case, not a controlled productivity study. No model patches were applied.

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

## Why documents and Jira change the action

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

Use [the 10-minute meeting script](docs/meeting-guide.md). Lead with DH-301, then show DH-303 and DH-305 to establish that the workflow can explain or stop as well as recommend a fix. Keep the other cases available for questions.

The scope of demo 1 is **one monthly report discrepancy → a reviewable decision and next action**. Live enterprise connectors, automatic policy extraction, general root-cause diagnosis, autonomous deployment and a productivity estimate are outside the implemented scope.

If their reporting rules are stable and code can already answer the question, ordinary software may be the best solution. If people repeatedly search business docs, Jira history and account configuration to decide what should happen, an assistant connected to those sources and reliable calculation tools is a reasonable pilot. The meeting should identify which situation applies.
