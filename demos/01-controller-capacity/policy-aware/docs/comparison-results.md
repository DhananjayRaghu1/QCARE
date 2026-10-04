# Recorded investigation comparison — October 4, 2026

All six AG-1423 investigation attempts from the named development workspaces are preserved in [comparison.json](../recordings/comparison.json), including two partial repository-only attempts and the first tools run's repair draft. This is a derived recording of actual results, not a new model request or a complete workflow replay. Private raw traces and stderr remain local.

The recordings verify the same actual model (`claude-sonnet-5-5`), incoming ticket hash, and initial application, registry, and starting-test hashes across these attempts. `repo` had the ticket and repository; `provided` also received the five documents directly; `tools` could retrieve those documents through MCP.

**These are development observations, not a controlled speed benchmark.** Prompts and parser behavior changed while resolving issues, some provider calls ran concurrently, and the number of attempts differs by condition. Do not calculate productivity gains from the timings or show only the successful retry.

## Every attempt

| Context | Workspace | Recorded outcome | Total elapsed | Model invocations | Decision in captured packet |
| --- | --- | --- | ---: | ---: | --- |
| Repository | `comparison-repo` | Partial: read denied | 15.96 s | 1 | Insufficient evidence; policy unknown |
| Repository | `comparison-repo-2` | Partial: unavailable tool calls | 25.21 s | 1 | Insufficient evidence; policy unknown |
| Repository | `comparison-repo-3` | Success | 12.89 s | 1 | Insufficient evidence; policy unknown |
| Documents supplied | `comparison-provided` | Success | 19.32 s | 1 | Investigate policy mismatch |
| MCP tools | `rehearsal-1` | Success after reference repair | 36.37 s | 2 | Investigate policy mismatch |
| MCP tools | `rehearsal-2` | Success | 18.84 s | 1 | Investigate policy mismatch |

Total elapsed includes local preflight. Recorded model-phase times are respectively 15.59, 24.57, 12.53, 18.76, 35.78, and 18.46 seconds. These timings describe the observed attempts only.

The first repository run attempted an out-of-scope read and remained partial despite producing a mechanically valid packet. The second attempted unavailable tool names and also remained partial. The successful third run correctly explained the global 20-zone implementation while saying that its correctness could not be decided without the approved requirement. That uncertainty is an appropriate conclusion, not a failure to discover the code behavior.

The first MCP run needed one bounded repair for an uncited history statement. Its first draft had 578 narrative words; the repaired packet had 575. Length remained a warning and did not itself cause the repair. The second MCP run passed reference validation on its first invocation with 284 words. The supplied-document run had 302 words; it succeeded with a length warning and no shortening call.

## What the evidence supports

All conditions identified the straightforward code behavior. With the approved policy available, both directly supplied documents and MCP retrieval justified that DEV-101's Pro 3.4.0 firmware should allow 30 zones and that the global 20-zone implementation contradicts it.

This establishes that external requirements affected the justified decision in this fixture. It does not establish that MCP was necessary: directly supplying the same documents also worked. The retrieval condition demonstrates finding and fetching evidence through tools; a business pilot must measure whether that acquisition step reduces manual effort or interruptions.

Mechanical reference validation passed for all final captured packets, including the partial runs. The partial execution outcomes remain partial. Source checks establish matching captured excerpts and allowed read spans, not semantic support for every sentence. Human claim-review status remains pending in these recordings unless separately reviewed and documented.

## Independent control evidence

[controls.json](../recordings/controls.json) preserves two actual test executions against **prepared fixtures**, with no agent-produced patch or model request:

| Prepared state | Visible tests | Independent policy cases | Outcome |
| --- | --- | --- | --- |
| Reference | 23 passed | 34 passed, 0 failed | Successful verification |
| Unsafe all-Pro-50 | 23 passed | 32 passed, 2 failed | Rejected by independent verification |

The unsafe fixture wrongly accepted 21 zones for DEV-102 on Pro 3.1.0 and for the Pro 3.1.99 boundary fixture. Both should return HTTP 400, but returned 201. Its visible tests—including the reported DEV-101 30-zone regression—passed. This shows why that one regression is insufficient to validate a patch.

The comparison and control bundles deliberately mark workflow and meeting-recording completeness false. They contain investigation or prepared-control evidence, not a completed investigation → failing regression → agent patch → verification rehearsal. Use the separately exported complete rehearsals for the meeting fallback.
