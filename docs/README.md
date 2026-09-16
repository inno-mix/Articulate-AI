# Documentation Map

Start here if you are a person **or** an AI agent.

| I need to… | Read |
|---|---|
| Understand the product, scope and decisions | [product-spec.md](product-spec.md) |
| Know what to build next and how | [tasks/README.md](tasks/README.md) → the current phase file |
| Follow the working rules for agents | [guides/agent-workflow.md](guides/agent-workflow.md) |
| See how the system fits together | [architecture/overview.md](architecture/overview.md) |
| Look up tables and columns | [architecture/data-model.md](architecture/data-model.md) |
| Look up endpoints, errors, SSE | [architecture/api-contract.md](architecture/api-contract.md) |
| Work on prompts, LLM calls, evals | [architecture/ai-layer.md](architecture/ai-layer.md) |
| Work on voice, speech stats, pronunciation | [architecture/voice-and-pronunciation.md](architecture/voice-and-pronunciation.md) |
| Handle secrets, auth, privacy | [architecture/security-privacy.md](architecture/security-privacy.md) |
| Set up and run locally | [guides/local-development.md](guides/local-development.md) |
| Write code the house way | [guides/coding-conventions.md](guides/coding-conventions.md) |
| Write and run tests | [guides/testing-strategy.md](guides/testing-strategy.md) |
| Understand why something is the way it is | [decisions/README.md](decisions/README.md) |
| Decode a term | [glossary.md](glossary.md) |

## Source-of-truth order
1. `product-spec.md` — what and why.
2. `architecture/*` — binding contracts (API, data, protocols, interfaces).
3. `decisions/*` — why the architecture is this way.
4. `tasks/*` — the order of work and the detailed steps.
5. Code.

If two sources disagree, stop and ask the owner; then fix the wrong one in the same change.
