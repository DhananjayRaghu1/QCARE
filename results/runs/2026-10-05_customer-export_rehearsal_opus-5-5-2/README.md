# Customer export: workflow rehearsal with a branch and a draft PR (Opus 5.5)

One live run after the engineer step learned to commit, push and open a draft PR on request. The note was "Use UTC to keep it simple. Open a draft PR when it's ready." The workflow pushed to the private sandbox `Ishaan1402/datahoney-export-sandbox`, never to the main project repository.

- The analyst found the PR request in the developer note, and the workflow verified the quote. It paused on the UTC conflict before any code was written; the operator chose the approved New York rule.
- The engineer committed `774b7d1` to `dh-401/workflow-ccb6a082` and pushed it. Its first `gh pr create`, with a multi-line markdown body, was refused by the shell allow-list and shown on the page as a blocked action; the retry with a one-paragraph body opened draft PR #1. The workflow confirmed that the remote branch matched the tested commit, `main` was unchanged and the PR was a draft.
- 20/20 tests run by the workflow passed. The review found only low-severity test gaps. 12/12 hidden acceptance checks passed.
- Approval marked PR #1 ready for review. It was not merged.
- 222 s of model time, $1.31.

Caveats: a single rehearsal by the same operator, on a synthetic fixture, using uncommitted code on `ishaan/langgraph-export-workflow`. Branches and PRs accumulate in the sandbox; close or delete them there when they're no longer needed.

The replay recordings from these runs were replaced after the workflow changed (code gate, context switch). The sanitized `results.json` keeps their numbers.
