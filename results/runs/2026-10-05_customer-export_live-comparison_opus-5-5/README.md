# Customer export: the same workflow with and without business context (Opus 5.5)

These runs come after the redesign: the requirements check is now code, there is a context switch, and short re-checks replace full re-analysis. Every step used `claude-opus-5-5`, and all branches and PRs went to the private sandbox. The note was always "Use UTC to keep it simple. Open a draft PR when it's ready." All four attempts are kept.

| Attempt | Context | What happened | Hidden checks | Model time | Cost |
| --- | --- | --- | --- | --- | --- |
| `1688c099` | On | One decision (the recommended option). The analyst wrote a self-contradictory acceptance example for R6 (invoice-ID ordering), so the reviewer and the engineer disagreed for 3 rounds. It was handed over, and a developer send-back settled it with an 11-second re-check. PR #2. | 12/12 | 435 s | $2.57 |
| `49c55ca2` (recorded) | On | One decision, built in one round, accepted by the code gate, PR #3 marked ready. | 12/12 | 152 s | $0.75 |
| `e33bad18` | Off | Asked 4 questions it could not answer ("I don't know"), built on assumptions, own tests 15/15. The reviewer escalated "don't merge". The scripted driver approved anyway (operator error), PR #4. | 0/12 | 153 s | $0.77 |
| `74c4e605` (recorded) | Off | Asked 2 questions it could not answer, own tests 14/14, reviewer escalated. Stopped at the developer review, as a presenter would. | 0/12 | 138 s | $0.60 |

What the first attempt changed: the analyst prompt now requires acceptance tests to follow only from the quoted words. Reviewers can mark a finding as needing the rule owner, and the code gate escalates such findings to the developer instead of looping the engineer.

Caveats: one synthetic fixture and one operator. The decisions were scripted to match a presenter. The control's 0/12 is expected by design, because the ticket alone does not contain the rules; this illustrates what missing context costs and is not a benchmark. The code was uncommitted on `ishaan/langgraph-export-workflow` (based on `71b25ec`).
