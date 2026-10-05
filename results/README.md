# Results

One place to find every recorded run across every demo: live model comparisons, baselines, rehearsals and deterministic control checks. **Start at [INDEX.md](INDEX.md)**, which lists the newest runs first.

Demos produce runs. This directory records them. Raw traces stay in each demo's git-ignored `artifacts/` and never come here.

## Layout

```text
results/
  README.md          conventions (this file)
  INDEX.md           generated table of every run, newest first
  index.json         the same, machine-readable
  tools/index.py     validates run.json files, rebuilds the index, answers queries
  runs/
    <run-id>/
      run.json       required metadata (schema below)
      README.md      what was run, the result, findings, caveats (new runs; pointer runs may rely on their linked write-up)
      results.json   sanitized record: packets, timings, costs, no raw traces   (optional)
      report.html    shareable human report                                       (optional)
```

## Naming a run

`YYYY-MM-DD_<demo>_<kind>[_<variant>]`, for example `2026-10-04_report-reconciliation_live-comparison_opus-5-5`.

- **date**: the day the run executed.
- **demo**: a stable slug that does not depend on folder numbering. Current slugs: `report-reconciliation`, `controller-capacity-basic`, `controller-capacity-policy`.
- **kind**: `live-comparison`, `baseline`, `rehearsal`, `controls`, `regression`, `preflight` or `historical-comparison`. Add a new kind to `tools/index.py` before using it.
- **variant**: optional. Usually the model (`opus-5-5`, `sonnet-5-5`), and a counter when it repeats on the same day (`opus-5-5-2`).

Folder names sort by date, and `ls runs | grep <demo>` works without the index.

## run.json

```json
{
  "id": "2026-10-04_report-reconciliation_live-comparison_opus-5-5",
  "date": "2026-10-04",
  "demo": "report-reconciliation",
  "demo_path": "demos/01-report-reconciliation",
  "kind": "live-comparison",
  "status": "completed",
  "provenance": "live-model",
  "models": ["claude-opus-5-5"],
  "conditions": ["provided", "retrieval", "workflow"],
  "repo_commit": "f3426aa",
  "command": "uv run python demo.py benchmark ...",
  "headline": "One sentence a reader can act on.",
  "metrics": {"provided_accepted": 10},
  "cost_usd": 2.19,
  "human_review": "pending",
  "owner": "ishaan",
  "tags": ["opus-5-5"],
  "related": ["<other run id>"],
  "files": {"record": "./results.json", "source_doc": "demos/.../docs/x.md"},
  "links": {"live_report": "https://claude.ai/artifact/..."}
}
```

Required fields: `id`, `date`, `demo`, `demo_path`, `kind`, `status`, `provenance`, `models` (empty for deterministic runs), `headline`, `repo_commit`, `files`, `human_review`.

Allowed values:

| Field | Values |
| --- | --- |
| `status` | `completed`, `partial`, `blocked`, `failed`, `aborted` |
| `provenance` | `live-model`, `deterministic`, `historical` |
| `human_review` | `pending`, `done`, `not-applicable` |

Paths in `files` that start with `./` are inside the run folder. Any other path is relative to the repository root. URLs go in `links`, which isn't checked. Local paths let a run point at recordings a demo already keeps, such as `demos/01-report-reconciliation/recordings/controls.json`, without copying them. The index check fails if a path goes missing.

`repo_commit` is the commit the run executed against. Use the protocol or snapshot hashes in the record to show the inputs didn't drift.

## Adding a run

1. Run it from the demo (for example `uv run python demo.py benchmark --name ... --model ...`). Raw output lands in the demo's `artifacts/`.
2. Create `runs/<run-id>/` with `run.json`, a short `README.md` and, for live runs, a sanitized `results.json`. Strip raw traces, local absolute paths and anything credential-like.
3. Keep failed, blocked and partial runs. Don't select the best attempt.
4. Run `python3 results/tools/index.py`, then commit the run folder together with `INDEX.md` and `index.json`.

## Finding runs

```sh
python3 results/tools/index.py find --demo report-reconciliation
python3 results/tools/index.py find --kind live-comparison --model opus
python3 results/tools/index.py --check     # suitable for CI
```

## What stays in the demos

Recordings that a demo's own docs or tests read, such as `recordings/controls.json` and `replays/`, stay where they are, and their runs here point at them. New live comparisons and one-off experiments go directly in `runs/`.
