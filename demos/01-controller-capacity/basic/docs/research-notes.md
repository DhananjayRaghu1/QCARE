# Research notes for the Data Honey meeting

Checked October 4, 2026. This file supports meeting preparation; public marketing descriptions are not evidence of internal engineering bottlenecks or measured agent performance.

## Verified identity

The user supplied [Data Honey, LLC's LinkedIn company page](https://www.linkedin.com/company/data-honey/). Its accessible public search result identifies a software-development company in Apex, North Carolina and lists **https://www.datahoney.com** as its website. Direct retrieval of the LinkedIn page failed, so the company-page description came from the indexed public result. The official website was accessible.

The public sources disagree on some background details: LinkedIn lists an Apex location and a founding year, while the current website lists a Cary office and a founder's public post describes a different company-age narrative. These details are unnecessary to the proposed SDLC discussion. Do not infer funding, legal history, current headcount, or a meeting location from them. “Apex” now appears to be the town in the supplied company profile, rather than an accelerator affiliation; confirm any remaining ambiguity with the user.

Before the user supplied the exact URL, searches found similarly named entities, including a historic Honeycomb/IoT project. Those are not this target and should not appear in the pitch.

## What the official website actually describes

| Published description | Meeting implication |
| --- | --- |
| DataLink collects data through Excel uploads/direct entry, stores it for reporting, and integrates with Power BI. | Ask which validation, schema, or reporting changes require engineering work. |
| CleanSlate uses ML for text classification, product/customer matching, and attribute extraction. | Ask whether the SDLC issue concerns application behavior, data contracts, or model changes. |
| The company develops and supports custom web applications. | Ask whether reusable product changes and client-specific changes follow different flows. |
| Azure hosting is mentioned publicly. | Ask about the actual dev/CI/deployment environment; this does not establish their full stack. |

These descriptions come from [Data Honey's official website](https://www.datahoney.com/). Product accuracy, security, speed and savings statements on that page are vendor claims. They have not been independently tested in this preparation and should not be used as validation for our demo.

Unknown: programming languages, repository host, issue tracker, documentation system, team ownership, test coverage, CI reliability, approval/release process, existing coding assistants, data access rules, and the bottleneck they want to address. The six Jira/Confluence-style demo files do not imply they use those products. The irrigation controller application is a fictional domain example, not a reconstruction of Data Honey's code.

## Primary technical sources and what to use them for

| Source | Read for |
| --- | --- |
| [Claude Code MCP](https://code.claude.com/docs/en/mcp) | Local stdio configuration, tool connection inspection, and host integration. Check installed-version compatibility rather than copying every feature from current docs. |
| [MCP architecture](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture) | Client/server roles; tools, resources and prompts; discovery and execution. Current docs describe protocol version 2026-07-28; the demo SDK may negotiate an earlier supported version. |
| [MCP security guidance](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices) | Explicit trust boundaries, authorization and least privilege. An interoperable tool interface is not a security guarantee. |
| [MCP annotation guidance](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/) | Why read-only/destructive annotations are hints and need concrete client enforcement. |
| [Claude Code permissions](https://code.claude.com/docs/en/permissions) and [sandboxing](https://code.claude.com/docs/en/sandboxing) | Separate proposed actions, approved actions, filesystem access and network isolation. Plan mode and prompts should not be presented as complete containment. |
| [BM25 documentation](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity) | Lexical ranking and its tunable assumptions. |
| [Sentence Transformers semantic search](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html) | Embedding similarity, query/document encoding and retrieval limits. |
| [RRF documentation](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion) | Combining ranks from independently scored retrieval methods. Ranking scores do not become confidence probabilities. |
| [Anthropic's workflow/agent guidance](https://www.anthropic.com/engineering/building-effective-agents) | Predefined workflows versus model-directed decisions; justify added complexity with observed need. The article notes that some tooling details have changed since its original publication. |
| [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use) | Narrow permissions, untrusted PR code, privileged workflow triggers and pinned action dependencies. |
| [Temporal execution/replay overview](https://docs.temporal.io/workflow-execution) | Durable state and recovery when long waits and process failure justify an orchestrator. Durability does not remove external-write duplication risk. |

## Claims this demo can and cannot support

Direct retrieval tests establish what this retriever returned for tested fixtures. An MCP client check establishes that this local server exposes and executes the tested capabilities. A regression test that fails on the baseline and passes on the reference establishes detection and correction of the seeded boundary defect. A live Claude Code transcript, if actually executed, establishes what that run did.

None of those alone establishes general bug-fixing accuracy, production security, savings for Data Honey, high-scale retrieval quality, connector freshness, or reliable unattended deployment. Preserve the distinction between a prepared replay, a local live agent run, a representative evaluation, and an accepted production change.
