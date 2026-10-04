# Policy-aware SDLC demo

**Historical demo:** use [customer-report reconciliation](../../01-report-reconciliation/README.md) as the first meeting example. The original controller runs below are preserved as execution evidence, with no productivity claim.

Two customers cannot save 30 zones. DEV-101 is a Pro controller on firmware 3.4.0: the approved policy allows 50. DEV-102 is a Pro controller on 3.1.0: its limit remains 20. The same symptom leads to a software fix for one and an expected rejection for the other.

This is a synthetic prototype, not Data Honey's application or customer data. The seed code uses a global 20-zone limit. Claude investigates the ticket and approved policy, adds a real failing regression, then fixes the application. A separate checker verifies compatibility. Prepared reference and unsafe patches are labeled control fixtures.

## Start with the recorded demo

Two actual Claude rehearsals are included under `replays/`. Both captured a real failing regression, an agent-written patch, 23 passing visible tests, all 34 independent policy checks, and AG-1424's expected rejection. Use `rehearsal-2` for the meeting: it has the shorter main investigation. These are saved executions, with their original results and source snapshots.

```sh
uv sync --locked
uv run python demo.py replay rehearsal-2
uv run python demo.py viewer --port 8766
```

Open [the local viewer](http://127.0.0.1:8766/), choose `rehearsal-2`, and follow its five phases. Recorded replay and the viewer make no model requests and do not need Claude authentication. Read the [observed verification results](docs/verification.md) and [citation review notes](docs/claim-review.md) before presenting. Some generated claims have incomplete citation attachments; the review identifies exact supplementary evidence. Human claim review remains pending.

## Setup and your own full rehearsal

Use Python 3.12, `uv`, and an authenticated Claude Code client. Run from this directory:

```sh
uv sync --locked
uv run python -m pytest -q
uv run python demo.py prepare --name my-rehearsal --state seed
uv run python demo.py preflight --workspace my-rehearsal
uv run python demo.py investigate AG-1423 --workspace my-rehearsal --context tools --timeout 180
uv run python demo.py reproduce --workspace my-rehearsal --timeout 180
uv run python demo.py fix --workspace my-rehearsal --timeout 180
uv run python demo.py verify --workspace my-rehearsal
uv run python demo.py investigate AG-1424 --workspace my-rehearsal --context tools --timeout 180
uv run python demo.py report --workspace my-rehearsal
```

`preflight` checks local MCP access, registry consistency, and client authentication without a model request. `investigate`, `reproduce`, and `fix` invoke Claude and send permitted synthetic context to its configured provider. Existing global model settings remain intact; `--model` provides an optional run-scoped override. Recorded results identify the actual model.

The investigation is read-only. Reproduction can add only the reported-case test, and must capture its real 201-versus-400 capacity failure before application changes. Fixing can edit application Python and add policy tests; original tests, registry, documents, and the captured regression remain protected. The runner executes tests separately. Shell tools are unavailable to the agent; the scope is a tool-level boundary, not an operating-system sandbox.

The fix stage passes visible tests; only `verify` establishes the independent policy results. Failed or partial stages return a nonzero exit and preserve their evidence. A failed regression gate prevents fixing. Use a fresh workspace name to reset; existing workspaces are never overwritten.

## Evidence and presentation

BM25 searches exactly five documents: AG-1423, AG-1424, AG-981, the approved capacity policy, and the validation design. Four MCP tools expose tickets, ranked search excerpts, full documents, and device records. Application and MCP reads use the same workspace registry. Search scores rank results; they are not confidence scores.

Citation references select captured sources and ranges; the runner copies exact excerpts. Checks establish that evidence was acquired and excerpts match. **They do not prove that every claim follows from its citation.** Human review remains separate and explicitly pending until performed.

```sh
uv run python demo.py viewer --port 8766
```

Open [the local viewer](http://127.0.0.1:8766/). It shows saved packets, source excerpts, patches, test outcomes, and failed runs. It never executes models or application code.

After a complete actual agent rehearsal, export a portable, derived recording:

```sh
uv run python demo.py export --workspace my-rehearsal --name my-recording
uv run python demo.py replay my-recording
```

The export goes under `replays/my-recording/` and includes captured source snapshots and recorded results. Private raw traces remain ignored locally. Export requires an actual complete investigation → reproduction → fix → verification workflow and the second-ticket decision; passing prepared controls does not qualify. Inspect the exported files before sharing. Individual local runs can also be inspected with `replay RUN_ID_FROM_OUTPUT`.

Both shipped recordings meet those workflow gates. `rehearsal-1` also preserves an earlier partial second-ticket attempt. Use the [8–10 minute meeting guide](docs/meeting-guide.md), [discovery questions](docs/discovery-guide.md), and [actual comparison results](docs/comparison-results.md). The independent claim review is attached; human review is a separate step.

## Independent controls and fair comparison

The checker outside the practice workspace has 34 fixed acceptance cases: device/version boundaries, numeric ordering, metadata errors, request spoofing, invalid zones, and persistence behavior.

```sh
uv run python demo.py prepare --name reference-check --state reference
uv run python demo.py verify --workspace reference-check
uv run python demo.py prepare --name unsafe-check --state unsafe-pro-50
uv run python demo.py verify --workspace unsafe-check
```

The reference should pass. The unsafe patch grants every Pro controller 50 zones: it passes the starting tests and the reported 30-zone regression but fails older-firmware checks. Its nonzero verification exit is the intended demonstration of rejection, not a successful repair.

Compare AG-1423 investigations in three fresh **seed** workspaces:

```sh
uv run python demo.py prepare --name my-comparison-repo --state seed
uv run python demo.py investigate AG-1423 --workspace my-comparison-repo --context repo
uv run python demo.py prepare --name my-comparison-provided --state seed
uv run python demo.py investigate AG-1423 --workspace my-comparison-provided --context provided
uv run python demo.py prepare --name my-comparison-tools --state seed
uv run python demo.py investigate AG-1423 --workspace my-comparison-tools --context tools
```

All receive the same ticket, code, and registry. `repo` has no company documents; `provided` receives the five documents directly; `tools` retrieves them through MCP. Keep client settings and actual model consistent. Record time, retries, evidence support, conclusions, and unknowns. Correct uncertainty without an external policy is acceptable. The direct-document condition distinguishes having information from automatically finding it; none of these small runs establishes company-wide productivity gains.

Optional hybrid retrieval requires `uv sync --locked --extra semantic` and already cached MiniLM weights. Set `POLICY_DEMO_MODEL_CACHE` to their cache directory if needed, then select `--mode hybrid`. Retrieval does not download weights and returns `unavailable` when the explicit mode cannot run. BM25 is the default meeting path.
