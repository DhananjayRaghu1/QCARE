# Basic developer onramping demo

This preserves the original synthetic application and six engineering documents. Claude Code turns a ticket into a briefing with starting files, execution flow, history, ownership, and a first investigation. Python retrieves evidence, checks references, and saves the packet; a local browser displays saved packets.

Use the [policy-aware variant](../policy-aware/README.md) for the main meeting. The basic defect is easy to find in code. In the two historical live runs, repository-only found it faster: **34.08 seconds versus 72.63 seconds** with hybrid retrieval. The augmented packet added useful organizational information, but human review found attached excerpts narrower than some claims. [Historical comparison](docs/historical-comparison.md).

## Setup and local checks

Run these commands inside this directory with Python 3.12 and `uv`:

```sh
uv sync --locked
uv run python onramp.py --preflight --mode bm25
uv run python -m pytest -q
uv run python scripts/check_retrieval.py --mode bm25
uv run python scripts/check_regression.py
```

The seeded application intentionally fails two Pro boundary checks. `check_regression.py` compares that baseline against the prepared reference and reports both; a baseline-only failure is expected.

For optional hybrid retrieval, install and download the model explicitly:

```sh
uv sync --locked --extra semantic
uv run python retriever.py --prepare-semantic
```

Weights are not included in the repository. Subsequent semantic/hybrid searches use the local cache; unavailable embeddings remain an explicit failure. Choose `--mode bm25` for a portable setup without model weights.

## Live and local sample flows

The following live commands require an installed, authenticated Claude Code client and send the documented synthetic context to its configured provider. [Transmission scope](docs/transmission-scope.md).

```sh
uv run python onramp.py AG-1423 --mode bm25
uv run python onramp.py AG-1423 --repo-only
```

Both runs receive the same ticket and application snapshot. Augmented has two read-only company-knowledge MCP tools; repository-only has none. Native tools are Read/Glob/Grep, with a hook restricting reads to the synthetic application. This is a tool-level boundary. Existing model settings are retained; execution records the actual model, tool calls, timing, hashes, and failures.

For a deterministic local sample, without an agent request:

```sh
uv run python onramp.py --sample --mode bm25
uv run python demo_web.py --port 8765
```

Open [the viewer](http://127.0.0.1:8765/). Samples are labeled **not Claude output**. The viewer does not launch models or edit code. Saved successful, partial, and failed runs remain distinct.

```sh
uv run python onramp.py --replay RUN_ID_FROM_OUTPUT
```

Basic replay uses the original generated workspace and current source paths. Keep that workspace if replaying locally. Historical machine-specific logs were deliberately not copied into this repository; the comparison document is a summary, not a portable replay. The policy-aware variant captures source snapshots for portable replay.

## Verification limits

The copied application, retrieval, packet checks, runner, and viewer retain the original behavior. Preparation and the auxiliary reviewer now reuse the command's Python interpreter, so they work in a relocated checkout without assuming a particular `.venv` path.

Mechanical validation checks source references, exact excerpts, read spans, and unchanged source hashes. It does not prove that every sentence is supported by its citation. The original bounded correction can retry an oversized packet; the new variant treats length as a warning to avoid that extra delay.

The earlier small-fixture retrieval results were BM25 11/11, hybrid 10/11, and semantic 9/11. They establish fixture behavior, not broad retrieval accuracy or company time savings. [Detailed verification](docs/verification.md), [demo prompts](docs/demo-prompts.md), and [meeting guide](docs/meeting-guide.md).
