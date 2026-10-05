# Report reconciliation: Repo only vs Docs + Jira on Opus 5.5 (single session)

Two live runs from the Demo 1 page after single-session runs were forced to `claude-opus-5-5`. Before this, `opusplan` in the settings made them run on Sonnet.

- **Repo only** (21 s, $0.08). It found that `app/report.py:10` negates A-2, a v1 return that is already negative, and explained the 40,000-cent gap. It noted that the sign convention isn't documented. It then suggested subtracting `abs(amount)`, which reproduces the customer's 115,000. That fix is wrong.
- **Docs + Jira** (22 s, $0.10). It established 125,000 cents ($1,250) from FEED-ATLAS-1 and FEED-ATLAS-2: A-2 keeps its sign, and A-3 is a positive return reversal that increases sales. Both starting numbers are wrong.

Full answers are in `results.json`. Both runs reload on the Demo 1 page when the server starts. Caveat: one run per condition on a synthetic fixture.
