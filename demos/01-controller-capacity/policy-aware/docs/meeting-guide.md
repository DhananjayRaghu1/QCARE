# Meeting sequence

The point to show is a justified engineering decision: one customer needs a code correction, another needs an explanation of an existing rule. Knowledge gives requirements; the real failing test, patch, and independent checks show whether implementation follows them.

## Prepare before the meeting

Two actual fresh-seed Claude rehearsals are recorded. Start by opening `rehearsal-2`, the shorter main investigation, and reviewing [verification results](verification.md) and [claim-review notes](claim-review.md). Inspect the supplementary spans identified there, including policy approval, effective scope, status-code construction, and patched constants. Record your own human review decision; the stored packets retain their original pending label.

The shipped `rehearsal-2` fallback has been replayed in a relocated directory without original workspaces or artifacts. To practice without a model request, run `uv run python demo.py replay rehearsal-2`. Start the viewer and prepare a fresh `meeting-live` seed workspace:

```sh
uv run python demo.py prepare --name meeting-live --state seed
uv run python demo.py preflight --workspace meeting-live
uv run python demo.py viewer --port 8766
```

The two recordings contain actual model-generated regressions and patches, followed by independent test execution. Prepared reference and unsafe states remain labeled controls. `rehearsal-1` retains an earlier partial second-ticket attempt as well as the successful rerun.

## Main presentation: 8–10 minutes

| Time | Show | Explain |
| --- | --- | --- |
| 0–1 min | AG-1423 and its 30-zone rejection | A developer must establish which behavior is required before changing code. |
| 1–3 min | Live investigation, device registry, approved policy, code location | DEV-101 has Pro 3.4.0; policy allows 50. The current backend still uses 20. |
| 3–6 min | Recorded real reproduction, actual patch, passing regression | The agent added a test against the real service before fixing it. The runner captured the failure and then the passing result. |
| 6–7 min | Independent verification | Older Pro and Legacy behavior still reject excess zones; numeric version ordering and metadata errors are checked. |
| 7–8 min | Recorded AG-1424 packet | DEV-102 has Pro 3.1.0. Its rejection is expected. Do not promise a software fix or invent an upgrade procedure. |
| 8–10 min | Unsafe control result, then a recent-ticket discovery question | An all-Pro-50 patch passes the visible example but violates older-device policy. Ask where their team reconstructs these distinctions today. |

Run the live investigation from a second terminal:

```sh
uv run python demo.py investigate AG-1423 --workspace meeting-live --context tools --timeout 90
```

If it times out or fails, show that recorded outcome and switch to `uv run python demo.py replay rehearsal-2`. Say “This is our recorded rehearsal” when showing its fix and test execution. Use the viewer's actual captured sources and diff. Do not silently replace a live failure or describe prepared controls as agent work.

For a longer session, run reproduction, fixing, and verification live with the README's 180-second per-agent-phase limits. The main presentation uses the rehearsed coding result to keep the discussion predictable.

## Plain-language explanation

“Our class introduced us to some of these concepts. We explored them further and built this synthetic prototype. The agent reads the ticket, code, device facts, and approved requirements. It proposes a next step with evidence. If a change is justified, we capture the failure first and check the patch against requirements beyond that one ticket.”

The earlier basic experiment showed that Claude could find a simple defect faster without retrieval. This version asks whether organizational information justifies the right action, then measures the extra cost of acquiring it. These are controlled prototype observations, not a time-savings claim about Data Honey.

Keep the final discussion grounded in their recent work. Staffing levels, number of customer codebases, internal tooling, and sources of friction remain unconfirmed. Use [the discovery guide](discovery-guide.md) to find a bounded pilot.
