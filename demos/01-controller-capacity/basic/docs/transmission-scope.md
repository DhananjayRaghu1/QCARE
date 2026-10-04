# Live rehearsal transmission scope

The live runner starts the installed authenticated Claude Code client. Its model request sends the incoming synthetic ticket, packet instructions/schema and tool responses to the client's configured provider (the installed account uses Anthropic).

Permitted synthetic application files are the prepared copies of:

- app/__init__.py
- app/controller_capabilities.py
- app/device_configuration_service.py
- app/schedule_controller.py
- app/schedule_repository.py
- app/schedule_service.py
- app/schedule_validator.py

The augmented run also exposes the six synthetic records in retriever.py's fixed manifest:

- knowledge/jira/AG-1423.md
- knowledge/jira/AG-981.md
- knowledge/confluence/controller-limits.md
- knowledge/confluence/scheduling-architecture.md
- knowledge/incidents/INC-331.md
- knowledge/prs/PR-719.md

The repository-only comparison receives the same ticket but no knowledge MCP server. Native tools are limited to Read/Glob/Grep. A PreToolUse hook checks paths, narrows searches to app/, rejects writes/shell and rejects knowledge tools in repository-only mode. User/project customizations are disabled; only the user's model preference is carried forward. Absolute practice paths and normal client/account metadata may be included by the client.

No pasted attachments, personal files, real customer records, prepared reference fix or grading material are supplied to the model. This is a tool-level boundary, not an operating-system sandbox. The runner verifies source hashes after execution.

Each onramping run has a shared 180-second model timeout and $2 API-budget cap, with at most two model calls capped at $1 each (subscription billing behavior depends on the client). Onramping runs can only create local run artifacts; they do not merge, deploy or contact other people.

The local preflight/sample/replay/viewer do not call a language model. Historical live verification is recorded in [the comparison](historical-comparison.md). Running the live commands starts a new provider request with the scope above.
