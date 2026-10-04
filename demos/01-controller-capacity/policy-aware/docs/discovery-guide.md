# Finding a useful pilot

Start with a recent real ticket: “Can you walk us through a change or support request where someone had to interrupt a teammate to reconstruct a customer rule, previous decision, or configuration?” Follow the concrete case before proposing tools.

Data Honey publicly describes custom application work/support, Excel-to-database reporting, and CleanSlate product/customer matching. These suggest places to ask about configuration and requirements, not proof of internal engineering bottlenecks. [Data Honey](https://www.datahoney.com/)

| Possible work | Ask about | Bounded pilot if they confirm the problem |
| --- | --- | --- |
| Customer-specific application support | Where do customer behavior, deployed versions, and exceptions live? | One support ticket to a cited expected-versus-observed handoff, followed by a checked regression. |
| Excel/database/reporting integration | Who remembers a customer's mappings, source assumptions, and compatibility constraints? | Retrieve approved mappings and decisions for one integration change; verify with that customer's fixtures. |
| Product/customer matching configuration | Which accepted matching rules and edge cases guide a change? | Link a proposed rule change to approved examples and run a frozen evaluation set. |
| Developer onboarding or task handoff | What does the experienced engineer explain repeatedly? | A concise briefing with code entry points, prior decisions, ownership, and honest unknowns. |

## Questions that change the design

- Which parts required active work, waiting, interruptions, or rework? Which step would they actually want to shorten?
- What source is authoritative for the required behavior? Who approves it, and how are stale or conflicting records handled?
- Does behavior vary by customer, configuration, version, or deployment? How is the affected environment identified?
- What can existing Claude or Copilot already do reliably? Where does manually supplying documents work well?
- What evidence would convince them the proposed next step is correct? Can that become an independent test or replayable example?
- Which repository and records can a pilot access, and what must remain separated between customers?
- Who reviews the handoff or patch, and which action still requires their approval?

Do not assume their staffing, repository count, agent subscription, or internal stack. Confirm those only when relevant to the identified case. If the same context is already captured in a maintained repository document, start with supplying that document rather than adding retrieval infrastructure.

## Agree on one measurable experiment

Choose one recent ticket and one owner. Capture the current path and compare a fresh assisted path with the same available facts. Measure time to a justified next step, teammate interruptions, missing or stale facts, rework, and review effort. Record both successes and failures; correct uncertainty counts as a useful result when evidence is missing.

The demo's three-way comparison separates repository facts, directly supplied documentation, and MCP retrieval. A pilot should make the same distinction. Decide whether the gain comes from consolidating information, retrieving it, generating the handoff, or verifying changes before investing in a larger workflow.

Customer release readiness—checking deployment, feature flags, completed work, and whether a delivery promise is justified—is a separate future idea. It is not implemented in this demo and needs its own authoritative data sources and acceptance contract.
