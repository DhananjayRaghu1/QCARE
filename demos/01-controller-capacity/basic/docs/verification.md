# Basic verification — October 4, 2026

The original application, retrieval, MCP transport, packet checks, runner failure handling, and viewer were verified locally. Both a hybrid-augmented Claude run and a repository-only run completed successfully. Source-reference checks passed, but human review found citation-coverage gaps in the augmented packet. [Historical comparison and exact run IDs](historical-comparison.md).

| Check in the original workspace | Observed result |
| --- | --- |
| Pytest suite | 133 tests and 18 viewer subtests passed |
| MCP stdio/tools | 12 checks passed, including locally cached MiniLM semantic/hybrid |
| Retrieval fixture | BM25 11/11, hybrid 10/11, semantic 9/11 |
| Application boundaries | Seeded app 20/22; prepared reference 22/22; two expected Pro failures |
| Authored sample | Mechanical references valid; explicitly labeled not Claude output |
| Viewer | Packet displayed and code/company citations inspected |
| Live hybrid-augmented Claude | 72.63 seconds, 246 words, 2 invocations, 4 application reads |
| Live repository-only Claude | 34.08 seconds, 276 words, 1 invocation, 6 application reads |

These observations precede the clean copy into `basic/`. Model weights, generated workspaces, raw traces, and machine-specific artifact paths are not distributed here. Run local checks from the basic README to verify your checkout; previous successful runs do not prove that a newly configured client or machine will succeed.

The relocated basic checkout was then tested with the existing Python 3.12 environment: **133 tests and 18 subtests passed**, BM25 **11/11**, real stdio MCP **8/8**, and the baseline/reference comparison remained **20/22 versus 22/22**. Browser tests required local loopback access. These relocation checks made no model request and used no copied embedding weights.

The hybrid fixture missed “Where should controller-specific schedule validation happen?” in its first three results. This is a small authored fixture, not a general retrieval benchmark. Its failed evaluations remain failures.

## Preserved failure handling

Tests cover missing ticket/MCP/semantic prerequisites without model launch, timeout with partial trace, denied or out-of-scope tools, final permission denials, fabricated knowledge content, partial native read spans, malformed packets, unknown ownership, stale excerpts, source changes, and viewer path/symlink rejection. Mock client events are parser tests, not live generation evidence.

The first live run recovered a StructuredOutput schema error, but genuinely failed exact excerpt matching and starting-file citation coverage. Its output also exceeded the word target. The corrected runner separates recoverable formatting attempts from access failures, supplies numbered source text, and retains the original draft if one bounded correction is attempted.

The later augmented run's 327-word first draft passed mechanical validation but was shortened through a second invocation to 246 words. This extra invocation contributed to its longer elapsed time. The basic behavior is preserved; the policy-aware variant treats length as a warning instead.

Mechanical checks establish source paths, spans, captured reads, and exact excerpts. They do not establish semantic support for every statement. The augmented human review found three narrow excerpts and retained the original packet unchanged. The repository-only run's recorded human-review status was pending. Both found the straightforward code defect, so the comparison does not support a claim that retrieval improves bug-finding speed.

For new live runs, inspect actual packets and traces, record source support, uncertainty, and time, and use [the transmission scope](transmission-scope.md). A baseline is allowed to succeed. The policy-aware demo adds independent application verification and a direct-document comparison condition.
