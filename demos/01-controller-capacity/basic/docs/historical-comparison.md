# Historical Claude comparison — October 4, 2026

These are measured outcomes from two actual Claude Code runs of the basic fixture, recorded before it was copied into this repository. The underlying private machine-specific traces remain in the original workspace. This document contains a comparison summary, not replayable Claude output or a new benchmark.

| Observation | Augmented | Repository-only |
| --- | --- | --- |
| Original run ID | `20261004T075702989072Z-c2de3058` | `20261004T080855136073Z-933b8898` |
| Actual model | `claude-sonnet-5-5` | `claude-sonnet-5-5` |
| Elapsed model phase | 72.63 s | 34.08 s |
| Model invocations | 2, including a shortening correction | 1 |
| Final narrative | 246 words | 276 words |
| Application files read | 4 | 6 |
| Company documents returned | All 6, through hybrid retrieval | None |
| Mechanical reference validation | Passed | Passed |
| Source hashes | Unchanged | Unchanged |

Both found the same capability-resolution omission: [the service](../app/schedule_service.py) calls the configuration lookup without the schedule's controller type. [Configuration](../app/device_configuration_service.py) consequently defaults to Legacy capacity, although [the capability table](../app/controller_capabilities.py) contains both limits. The repository-only packet provided useful starting files, request flow, and a concrete investigation, while leaving ownership and history unknown.

The augmented packet added team ownership and previous decisions. That is added information, not evidence of faster defect discovery. It also performed a second invocation solely to shorten a mechanically valid 327-word first draft, which helped make the run slower. These two runs are too small a sample to support a productivity estimate.

## Human review limitations

The augmented packet's attached citation ranges did not fully support three claims, although the statements appeared elsewhere in the retrieved documents:

- Editor acceptance needed [AG-1423](../knowledge/jira/AG-1423.md), lines 10–11; its attached excerpt covered lines 13–15.
- The expansion to 50 needed [AG-981](../knowledge/jira/AG-981.md), lines 9–10; its attached excerpt covered lines 12–14.
- The incident workaround and resolution needed [INC-331](../knowledge/incidents/INC-331.md), lines 14 and 7/16–17; its attached excerpt covered lines 9–12.

The original packet was left unchanged and marked with citation-coverage gaps. The repository-only run's recorded claim-review state was pending. Correct source locations do not prove complete claim support, and the code defect alone did not establish the actual customer's affected payload.

## What this changed in the next demo

The policy-aware variant makes external policy materially relevant to the decision, compares supplied-document and MCP contexts, keeps word count as a warning, materializes exact captured evidence, and checks older-device behavior independently. Baselines may succeed, and missing evidence should lead to uncertainty instead of an invented rule.
