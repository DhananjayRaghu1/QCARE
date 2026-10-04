> Superseded proposal: use [the ticket-onramping action plan](action-plan.md) and [verification status](verification.md).

# Assessment after the fuller meeting context

The current Pro/Legacy scenario is a useful integration smoke test and a weak centerpiece for demonstrating the additional value of company knowledge. Its simplicity is useful for explaining the components. Its decision is already recoverable from repository evidence.

## Evidence in the implementation

- `app/controller_capabilities.py:6` defines Legacy20 and Pro50.
- `app/schedule_validator.py:69` selects Legacy unconditionally.
- `scripts/check_regression.py:35-40` gives both intended controller boundaries.

A repository-only coding assistant can identify the inconsistency, propose the keyed lookup, and reject the naive global50 patch. Tickets and incidents confirm the symptom. PR history adds a plausible explanation for the missed backend work. That historical explanation is useful, but it is not necessary to select the correct code change here. The claim in the pasted plan that code alone cannot establish the root cause is too strong for this implementation.

Keep this as a short component demonstration, or as a development fixture. No need to discard the working retriever, real embedding model, MCP server, or boundary evaluator.

## Proposed main scenario: a rollout configuration mismatch

Keep irrigation and a small repository. Make the support symptom ambiguous until company evidence resolves it.

Ticket: an eligible Pro customer's schedules over20 zones fail after a frontend rollout. The server applies a conservative per-customer configuration, defaulting to20; the code implements that configuration consistently.

External synthetic evidence supplies these facts:

1. Pro hardware supports50, but the current rollout permits it only for an approved enrollment on gateway protocolv2.
2. A previous incident records truncation above20 on gatewayv1. That is why the safe default remains20.
3. An authoritative enrollment record confirms the ticket's customer is eligible for50. Their deployed configuration is still20.

The correct proposal is a narrow configuration update for that verified customer, with tests and review. A global Pro50 patch fixes the complaint while violating compatibility for other Pro customers. An agent can also identify incomplete enrollment evidence and stop before enabling the feature.

| Case | Required behavior |
|---|---|
| Pro, v2, enrollment verified and approved | Accept21 and50; reject51 |
| Pro, v1 | Preserve20-zone cap |
| Legacy | Preserve20-zone cap |
| Pro with missing/unverified eligibility | Preserve safe behavior and request missing evidence |

This is a proposed end-state, not an implemented or verified scenario. The existing code and six documents still implement the original simple defect. Agree on the scenario contract before changing them.

## Three workflows using the same evidence layer

Investigation: distinguish source-code defect from rollout/configuration mismatch and cite the evidence that resolves it.

PR review: review an apparently reasonable global Pro50 patch against the external compatibility constraint; propose the scoped alternative.

Onboarding: explain the executable scheduling path and the operational reason for the conservative default. Link actual files, distinguish intended architecture from implemented behavior, and identify the owner of rollout eligibility.

The current application uses an in-memory service. Its architecture fixture describes a controller/repository/database flow that is not fully implemented. An onboarding demo must explicitly describe that difference or implement the stated flow before claiming it.

## How to test the value of the added context

Run the same investigation/review request against the same repository with and without access to company knowledge. Do not hide legitimate repository evidence to manufacture dependence on retrieval.

Score the correct diagnosis, change scope, preservation of excluded customers, evidence citations, and handling of missing/conflicting facts. Correct uncertainty is a valid repository-only result. With verified evidence, the augmented run should resolve that uncertainty and make a justified recommendation. If both conditions can justify the same change equally well, the scenario has not demonstrated additional value from retrieval.

Show the actual retrieved records and actual tool outcomes, not a prepared trace presented as model behavior. Evaluate the task result as well as retrieval. The existing ten-query diagnostic currently returns9/10 for BM25 and9/10 for hybrid; both miss the expected architecture evidence for 'Where does the server enforce device capacity?'. This is a small diagnostic, not a general quality estimate, and it should remain visible rather than being tuned away.

For Wednesday, the valuable outcome remains one observed Data Honey bottleneck and a measurable pilot. The stronger scenario should make the engineering judgment clear in a few minutes, leaving time for their actual workflow.
