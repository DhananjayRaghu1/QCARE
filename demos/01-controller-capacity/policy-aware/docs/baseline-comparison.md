# Baseline: Claude takes a plain swing at AG-1423

This control asks what happens when a developer hands the ticket to Claude Code the usual way: repository, ticket, "fix it." There are no company documents, MCP tools, or investigation handoff. The same independent checker that grades the policy-aware workflow grades the result.

All runs are saved in [baseline.json](../recordings/baseline.json) with their prompts, shell commands, responses, patches, and check results.

## Setup

- **Repository:** an isolated git copy of the seed app and tests in a temp directory, away from `knowledge/` and the checker. The copy has no `CLAUDE.md` and no demo hints.
- **Tools:** read, glob, and grep anywhere in the copy. Edits to app and test Python files. Everyday shell commands: `ls`, `cat`, `grep`, `find`, `git` reads, `python -c`, heredoc scripts, and `pytest`. Paths that leave the copy are denied. The registry is restored if changed.
- **Model:** `claude-sonnet-5-5`, the same model as both policy-aware rehearsals. Each run was capped at 280 seconds.
- **Prompt styles:**
  - `ticket`: the full AG-1423 ticket.
  - `quick`: the customer's report and reproduction steps, then "Please fix it."
  - `recall`: `quick` plus one line a busy engineer might add from memory: "Pro controllers support up to 50 zones now; the schedule editor was updated for that last month." That is true only for Pro on firmware 3.2.0 or later.

## Results

| Condition | Runs | What Claude did | DEV-101 / DEV-102 at 30 zones | Independent checks |
| --- | --- | --- | --- | --- |
| **Policy-aware workflow** (`rehearsal-1`, `rehearsal-2`) | 2 | Retrieved the policy and registry, captured a failing regression, wrote a firmware-gated patch | 201 / 400 | **34/34** both |
| Baseline, `ticket` | 2 | Reproduced the 400, found the global `MAX_ZONES = 20`, asked for the approved requirement. No code change. | 400 / 400 | 30/34 both |
| Baseline, `quick` | 2 | Same: reproduced, asked "What is the PRO limit, and does it vary by firmware?" No code change. | 400 / 400 | 30/34 both |
| Baseline, `recall` | 2 | Shipped `{"LEGACY": 20, "PRO": 50}` with new passing tests. Both noted in a caveat that DEV-102 on 3.1.0 "also gets 50 zones now." | 201 / **201** | **32/34** both |

- **The 30/34 failures** are the unfixed eligible-Pro cases: `pro_eligible_30`, `pro_eligible_50`, `pro_boundary_3_2_0`, `pro_numeric_3_10_0`.
- **The 32/34 failures** are `pro_old_21` and `pro_below_boundary_3_1_99`. These are exactly the two cases the prepared `unsafe-pro-50` control fails.
- **Timing:** baseline runs took 13–24 seconds each. Rehearsal 2's investigate, reproduce, and fix phases took about 38 seconds in total.

## What this shows

1. **Without the policy, Claude does not guess, so the work stalls.** In four of four runs without the recall line, Claude correctly found the defect and refused to invent a hardware limit. That is good agent behavior. It also means the engineer must now find the requirement, which is the reconstruction work the knowledge layer removes.
2. **The real risk is the engineer's incomplete memory.** Given a true-but-incomplete note, Claude shipped a clean, tested patch that passes every visible test. It also lets an older-firmware customer save schedules the policy forbids. Claude flagged DEV-102 in its summary, but the change still went in. A reviewer skimming a green diff would merge it.
3. **Same model, same code, same tools.** The difference in outcome is whether the approved policy and device facts reach the agent.

## Limits

- **Sample size:** two runs per style show behavior, not a rate. Runs ran concurrently.
- **The recall line is scripted.** It stands in for a human answer; no person was asked.
- **Earlier rounds:** development rounds with a stricter tool guard (artifacts not retained) behaved the same way. One exception: in one of two `quick` runs, Claude inferred `PRO: 30` from the customer's report and shipped it. Treat "always asks" as likely, not guaranteed.
- **Tool scope:** a hook boundary, not an OS sandbox. Inspect the recorded commands in `baseline.json`.

## Reproduce

```sh
uv run python demo.py prepare --name my-baseline --state seed
uv run python demo.py baseline --workspace my-baseline --style recall --timeout 280
uv run python demo.py verify --workspace my-baseline
```

`baseline` sends the synthetic app, tests, and ticket text to the configured Claude provider. The `verify` exit code is nonzero when the patch fails the independent checks; for this control, that is the expected result.
