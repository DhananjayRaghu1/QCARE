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
2. **Start it.** Type the note **Use UTC to keep it simple. Open a draft PR when it’s ready.** (the box's placeholder shows it), then click **Run workflow**. "A busy developer's shortcut, plus an ordinary request for a PR."
3. **Gather context (about 45 s).** Lookups appear as they happen: Jira, then the Confluence agreement, the Finance rule and the draft. "It reads the full record before relying on it, and the workflow checks every quote word-for-word."
4. **The pause.** The workflow stops *before any code is written*. The note conflicts with the approved agreement, whose rule owner is Reporting Product. Send the recommended option; it applies at once.
5. **Build, review, check (about 1.5 minutes).** The engineer writes the code and tests on its own branch, commits, pushes and opens a draft PR. If it tries a command outside its allow-list, the page shows the block. A separate reviewer that cannot edit the code judges every requirement. Then **rules in code, not a model,** decide whether it's done. Read the "Next" line aloud; it says why.
6. **The summary.** Business: the plain-English paragraph. Engineer: the requirement → source → code → status table, the branch and PR links, and the risks.
7. **Approve.** The draft PR is marked ready for review. Open it on GitHub. "Nothing was merged or deployed; your normal review takes it from here."
8. **The diagram, if asked.** The Demo 2 architecture page shows the whole workflow as one diagram: grey steps are code, blue are separate Claude sessions, gold are you.

If a live run is slow or fails, replay the saved run instead, and say out loud that it is a replay of a real run.

Questions that land well: Where do your approved rules live today? Who would have caught the UTC shortcut, and when? What happens today when an engineer builds from the ticket alone?

## Demo 3: Release-check a shared-code cleanup (about 4 minutes)

This is a release check on a teammate's prepared cleanup PR. It connects well to a team with customer-specific imports and reports: code shows the call paths; agreements and operations establish the promises those paths must keep. All customers, jobs, contracts and operational records here are synthetic.

1. **The PR.** Open the prepared cleanup diff. It removes v1 support, changes the jobs to accept only v2 and deletes the replay regression. Its remaining CI is green. This is a local fixture, not a real sandbox PR.
2. **The missed failure.** Show the before/after job replay. NORTHSTAR's September goes from **$1,250 to $400**, and CEDAR statements go from **$180 to $0**. “The job silently skips the old rows. There is no exception to alert us.” These totals come from executing the sample jobs, not from the model's arithmetic.
3. **The evidence.** Leave **Business context: On**, then click **Run release check →**, or replay a saved actual run if one exists. One read-only Opus session maps live ingest, historical replay, Cedar delivery and rollback. Open an exact quote, its owner and observation date. Distinguish the old October 1 usage snapshot from the decision's current synthetic usage evidence.
4. **The gate.** Point to the allow/block result for each dependent. A developer note asking to proceed cannot clear a contract or missing recovery proof. The October 15 proposal is not cleared. **December 30 is only a conditional lower bound**: the synthetic last archived v1 export is September 30, and its 90-day replay obligation covers December 29 inclusive. Cedar's separate delivery promise runs through November 30. The absolute date is unknown until migration, retention/conversion, backups, rollback and fresh usage are verified.
5. **Your decision.** At **The gate is fixed; choose the next action**, choose **Defer full removal**, **Prepare a scoped canary** or **Request owner sign-off**. Click **Record decision and draft next actions →** and open **Download unsent drafts**. Show the PR review comment, sign-off requests and decision-record update. They are drafts; nothing is sent, no PR is created or commented on, and blocked gates stay blocked.
6. **The control.** Run or replay **Business context: Off** with the same model, candidate and replay rows. It still sees the losses and blocks, but can only ask for missing evidence. It cannot source customer obligations, approval owners or a retirement date. The twelve hidden checks score the completed output separately from the gate. Read only the actual saved scores; do not use an expected score as a measured result.

The prepared worked example and offline `migration_demo.py verify` check are useful fallbacks, but label them as prepared software. A replay is a recording of a run; it is not a new model call. The [release-check guide](migration-release-check.md) records these boundaries.

Ask how they discover which customers depend on shared code, confirm current usage, find approval owners and prove archived data and rollback will still work. The useful comparison is whether the extra context supplies a defensible next action, not whether it produces more blockers or takes less time.

## Open the relevant production architecture page

Follow request → authorized retrieval → full evidence → explicit requirements/claims → independent checks → human review. Show the examples of combining a code fact with a Jira decision or Confluence rule. Discuss their source permissions, freshness requirements and actual approval trail. An index is optional; indexing the whole repository is not a prerequisite.

## Agree on a bounded pilot

Choose one recently completed, representative task and reconstruct its original request, available evidence, missing context, handoffs, implementation and accepted outcome. Compare matched runs with and without the additional context, counting all attempts and the human review/setup effort. Define success as accepted correctness, fewer unsupported assumptions or less total work; do not promise time savings from these examples.

For a two-hour invitation, use a 60–75 minute core: desired outcome (10), one real workflow (25), relevant demo (10), and pilot scope/next step (15–30). Leave room for questions and finish early if the objective is met.
