# Actual comparison: repo alone versus business documents

**The documents resolved uncertainty and enabled a tested patch. They did not make this run faster.** The repo-only investigation already found the likely sign-handling problem and calculated $1,250 as one possible answer. It appropriately declined to choose that interpretation without evidence.

Two fresh Codex CLI investigations ran on 4 October 2026, using the same prompt and configured `gpt-6-astra`, `xhigh`, `priority` settings. Claude remained signed out, so this is a Codex comparison, not a replication of Sam's exact model or personal workflow. The JSONL trace does not independently report a resolved backend model ID; the requested model and settings are recorded.

| Result | Repo only | Same repo + business documents |
| --- | --- | --- |
| Wall time, including CLI startup and tools | **50.476 seconds** | **95.180 seconds** |
| Reproduced current total | $1,550 | $1,550 |
| Identified unconditional return negation | Yes | Yes |
| Considered $1,250 | Yes, conditional on signed schema 1 and magnitude schema 2 | Yes, established from approved format contracts |
| Final decision | Needs clarification | Supported fix |
| Authoritative replacement total | Undetermined | $1,250 |
| Proposed code | None; asked a precise business-rule question | Complete proposed replacement |
| Independent patch checks | Not applicable: no patch proposed | **11/11 passed**, plus all 5 baseline tests |

The repo-only response distinguished two plausible interpretations: making every return negative produces $1,150; preserving signed schema 1 amounts produces $1,250. It asked what A-2 and A-3 should mean. This is a good response to incomplete requirements, not a failed coding assistant.

The document response read the approved schema contracts, September reporting policy and Jira rollout history. It preserved the +$50 return reversal, rejected the customer's total, and proposed schema-specific normalization. It also checked the newer October policy and other customers' addenda instead of applying them indiscriminately. The customer spreadsheet's actual formula was unavailable, and the response explicitly said so.

## What was controlled

The demo repository itself contains the answers, reference patch and recordings. Giving either trial that entire repository would leak the expected result. Instead, each fresh temporary directory contained the identical application code, issue data, a neutral README and five prepared baseline tests. The diagnostic fixture title was removed from both conditions. These tests represent existing-behavior coverage; they are not historical production tests.

Only the second directory added the ten business/Jira documents, as prose plus scope, approval, ownership and effective-date metadata. Neither trial received structured `rules` objects, the reference implementation, the answer key, prior results or the reconciliation calculator. The prompt allowed either a justified fix or a precise clarification; it did not force a patch.

Both trials used fresh sessions and read-only tools. Web search, connectors, plugins, memories and subagents were disabled. Audit of the five repo-only commands and six document-run commands found reads of the supplied files, tests and local calculations only. All task commands exited successfully. The client emitted a development-feature warning and an unspecified sandbox warning; these are retained in the exported audit notes. This is trace-audited isolation, not proof of a strict OS-level read boundary.

The fixed order was repo first, documents second. No attempt was retried or replaced. Input files, prompt, runner hash, timings, usage, exact final answers and command transcripts are preserved in the [recording directory](../recordings/codex-repo-vs-docs/). Private full traces remain ignored. Trial directory paths in exported records were replaced with `<trial-workspace>`; answer text, code and tool outputs are otherwise unchanged. The runner follows the [official non-interactive Codex interface](https://learn.chatgpt.com/docs/non-interactive-mode).

## Independent verification

The document run executed its proposed code in memory against the five baseline tests and ten tests it wrote. Separately, the outer runner executed the returned code in a new directory against [eleven checks withheld from both trials](../controls/compare_patch_checks.py), prepared before either final answer was inspected. All eleven passed, including the mixed-schema rows, positive reversal, cancelling row errors, existing filtering, negative magnitude rejection and unknown-contract rejection. The five baseline tests passed again.

See the [independent result](../recordings/codex-repo-vs-docs/patch-verification.json) and [exact proposed code](../recordings/codex-repo-vs-docs/business_docs.proposed_report.py). This is a proposal, not a deployed repair. It validates source contracts for included rows; broader input validation and upstream quarantine still require application review. The seeded demo application remains unchanged so the discrepancy can be reproduced.

## What this means for the meeting

The supported claim is: **“The repo assistant can identify the likely fix. Connecting approved business context can let it decide whether that fix is justified and complete a reviewable proposal without asking someone to supply the missing rule.”**

There is no demonstrated speedup. The document run took longer and performed additional work, including writing and testing a patch. The repo-only run stopped at a valid clarification, so these are different completion states. Waiting for a person, finding documents, reviewing the answer and maintaining the source material were not measured.

If Sam already knows the rules and gives them to his assistant, this example does not establish a meaningful advantage over his current process. It also does not prove that an MCP layer, RAG or a custom agent is needed: the benefit here came from having authoritative information available as ordinary files. The next useful test is a real case where finding or obtaining that information creates repeated effort or handoffs. One synthetic case with two runs cannot estimate productivity.

To repeat this exact two-condition protocol with a new run name:

```sh
uv run python codex_compare.py --name another-comparison --timeout 300
```

It uses the local Codex authentication and configured model, makes two fresh model investigations, and stores every attempt under ignored `artifacts/`. Do not select the fastest or most favorable rerun when reporting results.
