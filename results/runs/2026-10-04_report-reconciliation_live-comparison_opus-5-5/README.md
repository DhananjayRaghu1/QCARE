# Report reconciliation: first live comparison, Opus 5.5

**Run:** 4 Oct 2026 · `claude-opus-5-5` (verified from the traces in all 30 trials) · Claude Code 2.1.289 · commit `f3426aa` · $2.19

The first real run of the 30-trial plan from PR #2, which had been blocked by authentication ([blocked record](../2026-10-04_report-reconciliation_preflight_blocked/run.json)). The full report is in [report.html](report.html). It's also published as a private [Claude artifact](https://claude.ai/artifact/JZFywvNExmUJ4A8NMkJBZw), viewable once it's shared.

```sh
cd demos/01-report-reconciliation
uv run python demo.py benchmark --name opus55-comparison-1 --repeats 1 --timeout 180 --budget 0.50 --model claude-opus-5-5
```

## Result

| Condition | Correct decision, total, rows | Strict pass | Median time | Avg cost | Avg tool calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| provided | 10/10 | 10/10 | 7.8 s | $0.059 | 0 |
| retrieval | 10/10 | 9/10 | 11.9 s | $0.091 | 6.3 |
| workflow | 10/10 | 8/10 | 9.5 s | $0.069 | 3.2 |

## Findings

1. **The fixture is too easy to compare the conditions.** Opus got every case right, including the three stops, the pending-Jira trap (DH-303) and the cancelling errors (DH-310), however the evidence was delivered.
2. **The strict failures come from how citations are scored.** In `provided`, every document counts as observed, so extra citations are free; Opus added unneeded sources in all 10 provided runs. In the tool conditions, citing a document that wasn't fetched in full fails the trial. All three failures (DH-302 workflow, DH-304 retrieval, DH-307 workflow) were extra, non-required sources. No required source was missing in any trial.
3. **The workflow tool's value here is efficiency.** Compared with retrieval it used half the tool calls, cost about 24% less and took about 20% less median time, with the same correctness.
4. **Runner bug fixed in this commit.** The settings model `opusplan` was passed straight to `claude --print`, where it runs Sonnet. `--model` now overrides it.

## Suggested next runs

- Same plan on `claude-sonnet-5-5` and `claude-haiku-4-5-20251001`, to test whether the workflow tool lets a smaller model match Opus.
- Fix the citation-scoring difference and enlarge the corpus before comparing conditions again.

## Caveats

Ten hand-authored synthetic cases, one repetition, one model. One or two trials in ten is within noise. Human review of explanations is pending. Model wall time is not employee time, and there is no productivity estimate.
