# Demo 3 deterministic verification

`python migration_demo.py verify` executed the actual LangGraph, original/candidate CI commands and synthetic job replays twice, with an author-prepared assessment standing in for the model. **No model was called.** The prepared source-enabled assessment scored 12/12; the prepared source-disabled assessment scored 2/12. Both blocked full removal and generated only local drafts after the scripted defer decision.

BASE passes two tests; the prepared candidate passes its remaining test; restoring the deleted v1 reversal test fails. The same synthetic rows produce NORTHSTAR $1,250 → $400 and Cedar $180 → $0 with no job error. The records include source, input and software hashes.

This checks the harness and adapters. It is not a model comparison. [Executed results](./results.json) and [the actual Opus comparison](../2026-10-05_format-retirement_live-comparison_opus-5-5/README.md) are distinct.
