# Demo 1: Which total can we defend?

A customer says their monthly report is wrong. The application shows **$1,550**; their spreadsheet shows **$1,150**. Approved business definitions and export contracts show that **both are wrong: the correct total is $1,250**.

This is the recommended meeting demo. It makes business context necessary to choose a justified action, rather than adding documents to an obvious code bug. All accounts, transactions, documents and Jira records are synthetic. They do not describe Data Honey's actual systems.

## Run it

Install [uv](https://docs.astral.sh/uv/) and run these commands from this directory. The pinned Python version avoids relying on a system Python installation.

```sh
uv sync --locked
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

The default path is a **working deterministic reconciliation workflow**, with read-only MCP tools and an optional agent interface. Source snapshots contain prose plus **hand-authored structured rules**. The engine selects those rules by customer/profile, schema, approval status and effective month; it does not extract arbitrary prose into reliable executable policy. Preparing and maintaining those adapters is real work.

The recorded fixture checks are:

| Prepared implementation | Correct totals where a total is justified | Correct stops on missing/conflicting/invalid inputs |
| --- | ---: | ---: |
| Current arithmetic | 4/7 | 0/3 |
| Force all returns negative | 3/7 | 0/3 |
| Approved-rule workflow | 7/7 | 3/3 |

The workflow also passes all ten case-level checks for decision, total, affected rows and required source IDs. These are ten hand-authored synthetic cases, not a representative test population. The two arithmetic controls are **not coding-assistant baselines**. Their missing citations are not evidence that an AI or analyst would fail.

[Recorded results](recordings/controls.json), [regression results](recordings/regression.json), and [verification notes](docs/verification.md) preserve what was actually executed. New live Claude comparisons were **blocked by an unauthenticated client**; no new model execution, speedup or employee-productivity result is claimed. The [older controller results](../01-controller-capacity/policy-aware/docs/comparison-results.md) remain intact, including their limitations.

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

Use a new name each time. Every condition receives every case; order rotates, evidence and runner hashes are frozen, and failures stay in the record. No automatic retries or selection of the fastest successful run. Outputs and private traces stay under ignored `artifacts/`. See the [evaluation protocol](docs/evaluation-protocol.md) before interpreting results. The adapter is tested locally; a real provider run remains unverified in this revision.

## Present it and discover the real workflow

Use [the 10-minute meeting script](docs/meeting-guide.md). Lead with DH-301, then show DH-303 and DH-305 to establish that the workflow can explain or stop as well as recommend a fix. Keep the other cases available for questions.

The scope of demo 1 is **one monthly report discrepancy → a reviewable decision and next action**. Live enterprise connectors, automatic policy extraction, general root-cause diagnosis, autonomous deployment and a productivity estimate are outside the implemented scope.

If their reporting rules are stable and code can already answer the question, ordinary software may be the best solution. If people repeatedly search business docs, Jira history and account configuration to decide what should happen, an assistant connected to those sources and reliable calculation tools is a reasonable pilot. The meeting should identify which situation applies.
