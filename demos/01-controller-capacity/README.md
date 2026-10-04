# Demo 1: Controller capacity

Two customers report that saving 30 zones fails. A Pro controller on firmware 3.4.0 should accept it; a Pro controller on firmware 3.1.0 should reject it under the approved policy. Code, device facts, and policy together determine the justified next step.

| Variant | What it demonstrates | Start here |
| --- | --- | --- |
| Policy-aware | Ticket investigation, a real failing regression, a policy-consistent patch, and independent compatibility checks | [Instructions](policy-aware/README.md) |
| Basic | Developer orientation with code and retrieved engineering history | [Instructions](basic/README.md) |

The policy-aware variant is the main presentation. The basic variant is preserved as an earlier experiment: its repository-only Claude run found the simple defect in 34.08 seconds; the augmented run took 72.63 seconds and added useful history and ownership. [Comparison and limits](basic/docs/historical-comparison.md).

Run each variant from its own directory with `uv sync --locked` and `uv run python ...`. They have independent environments and fixtures. Reset by preparing a fresh named workspace; keep prior results for comparison.

All controllers, tickets, policy documents, and code are synthetic. Customer-specific compatibility is a possible business use case to discuss, not an assertion about Data Honey's internal systems. Company knowledge can justify a decision; verification must still exercise the application.
