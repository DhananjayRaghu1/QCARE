# Agentic SDLC demos

Local, synthetic prototypes for discussing how application code, company decisions, and customer configuration can support a developer's next action. These fixtures are not Data Honey's product or customer records. Our class introduced some of the concepts; these demos were built afterward to explore them.

## Start with demo 1

[Controller capacity](demos/01-controller-capacity/README.md) contains two independent variants:

- [Policy-aware](demos/01-controller-capacity/policy-aware/README.md): two similar support tickets lead to different decisions. The workflow gathers evidence, captures a failing regression, fixes eligible devices, and checks compatibility independently.
- [Basic](demos/01-controller-capacity/basic/README.md): the original task-onramping prototype, preserved with its [historical comparison](demos/01-controller-capacity/basic/docs/historical-comparison.md). Repository-only found the same defect faster; added context supplied ownership and history, with citation limitations.

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). Each variant owns its dependencies; run commands inside its directory:

```sh
cd demos/01-controller-capacity/policy-aware
uv sync --locked
uv run python demo.py replay rehearsal-2
uv run python demo.py viewer --port 8766
```

Two actual Claude rehearsals are included: both captured a real failing regression, an agent patch, 23 passing visible tests, all 34 independent checks, and the older-device ticket's expected rejection. Open [the local viewer](http://127.0.0.1:8766/) and select `rehearsal-2`. Replay requires no Claude login or model request. Read the [verification results](demos/01-controller-capacity/policy-aware/docs/verification.md) and [citation review](demos/01-controller-capacity/policy-aware/docs/claim-review.md); human claim review remains pending.

Follow the policy-aware README to run your own fresh rehearsal and fair comparisons. Live agent phases require an authenticated Claude Code client and send the listed synthetic context to its configured provider. Prepared control states and samples are explicitly labeled; they do not count as Claude execution.

The repository contains no credentials, virtual environments, embedding weights, or private raw traces. Generated workspaces and run artifacts stay local.
