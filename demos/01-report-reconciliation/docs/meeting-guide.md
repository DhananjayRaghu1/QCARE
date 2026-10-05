# Three demos, then discovery

Open the [hub](http://127.0.0.1:8768/). Spend roughly ten minutes on relevant examples, then investigate the team's actual workflow. Do not present three long demonstrations simply because three are available.

## Start with the question

“Code tells us what the software does. Where do people find the agreements and decisions that tell them what it should do? These examples explore what changes when the AI has that context.”

The records and customers are synthetic. Prepared examples are authored references; live buttons run the model. Production architecture pages are proposals for real integrations, not claims about installed infrastructure.

## Demo 1: Investigate the wrong report (3–4 minutes)

Start the server with `uv run python demo.py live --sandbox-repo Ishaan1402/datahoney-export-sandbox`. Single-session runs use Opus 5.5 (`--model`), and the last saved Repo-only and Docs + Jira runs reload, so results are on the page before you click anything.

1. **The ticket.** The app says $1,550; the customer says $1,150. "Who is right?"
2. **Repo only.** Open the saved Repo-only result. It finds the double-negated return on A-2 and explains the $400 gap. Then it suggests the obvious fix, subtracting the absolute value, which reproduces the customer's $1,150. "Plausible, fast, and wrong."
3. **Docs + Jira.** Open the saved Docs + Jira result. Both numbers are wrong; the approved answer is **$1,250**. Under the ATLAS v1 contract, a positive return (A-3) reverses an earlier refund. Open FEED-ATLAS-1 from the evidence cards to show the sentence.
4. **Optional.** The worked example shows the same $1,250 row by row. It is prepared software, not a model run. Run either mode live if there is time; each takes about 20 seconds.

Ask which systems hold their equivalent requirements, who confirms the correct rule, and where work is handed between teams.

## Demo 2: Build the right feature with the engineering workflow (about 5 minutes)

The workflow section at the top of the Demo 2 page runs the whole ticket-to-PR loop with real Claude sessions. With a mixed audience, narrate each step in one plain sentence, and open the details only when the engineer asks.

1. **The ticket.** "One paragraph. It looks like a ten-minute change." Point out the link to DH-411 and the attached sample.
2. **Start it.** Leave **Business context: On**. Click the chips **Use UTC to keep it simple.** and **Open a draft PR when it’s ready.**, then **Run workflow**. "A busy developer's shortcut, plus an ordinary request for a PR."
3. **Gather context (about 45 s).** Lookups appear as they happen: Jira, then the Confluence agreement, the Finance rule and the draft. "It reads the full record before relying on it, and the workflow checks every quote word-for-word."
4. **The pause.** The workflow stops *before any code is written*. The note conflicts with the approved agreement, whose rule owner is Reporting Product. Send the recommended option; it applies at once.
5. **Build, review, check (about 1.5 minutes).** The engineer writes the code and tests on its own branch, commits, pushes and opens a draft PR. If it tries a command outside its allow-list, the page shows the block. A separate reviewer that cannot edit the code judges every requirement. Then **rules in code, not a model,** decide whether it's done. Read the "Next" line aloud; it says why.
6. **The summary.** Business: the plain-English paragraph. Engineer: the requirement → source → code → status table, the branch and PR links, and the risks.
7. **Approve.** The draft PR is marked ready for review. Open it on GitHub. "Nothing was merged or deployed; your normal review takes it from here."
8. **The control (the punchline).** Point to the comparison card: same workflow, same model, business context off. Without the documents, it had to ask what the rules even were. Its own tests still passed, but it scored **0 of 12** on the hidden checks, and the reviewer escalated "don't merge until Reporting Product answers" instead of letting it through. With context: **12 of 12**. To show it, pick **Without context** in the replay picker and replay it (about 30 s, pausing at both decisions).

If a live run is slow or fails, replay **With context** instead, and say out loud that it is a replay of a real run.

Questions that land well: Where do your approved rules live today? Who would have caught the UTC shortcut, and when? What happens today when an engineer builds from the ticket alone?

## Demo 3: Assess retirement risk (optional, 3–4 minutes)

Show the three code consumers of the shared ATLAS decoder. Then read the completed daily-sales Jira ticket, the replay obligation and the Cedar agreement. The ticket only covers one path. Historical replay and partner deliveries remain dependencies. The operational usage snapshot is dated and must be refreshed.

The prepared example runs the tests with current support and after removing v1: replay breaks. The dependency matrix supplies owners and gates; it does not claim to be a live production inventory.

Ask how they discover cross-team dependencies, verify actual usage, obtain customer approval and test recovery before removal.

## Open the relevant production architecture page

Follow request → authorized retrieval → full evidence → explicit requirements/claims → independent checks → human review. Show the examples of combining a code fact with a Jira decision or Confluence rule. Discuss their source permissions, freshness requirements and actual approval trail. An index is optional; indexing the whole repository is not a prerequisite.

## Agree on a bounded pilot

Choose one recently completed, representative task and reconstruct its original request, available evidence, missing context, handoffs, implementation and accepted outcome. Compare matched runs with and without the additional context, counting all attempts and the human review/setup effort. Define success as accepted correctness, fewer unsupported assumptions or less total work; do not promise time savings from these examples.

For a two-hour invitation, use a 60–75 minute core: desired outcome (10), one real workflow (25), relevant demo (10), and pilot scope/next step (15–30). Leave room for questions and finish early if the objective is met.
