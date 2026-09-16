# Architecture Decision Records (ADRs)

Short records of decisions that shape the codebase. Agents: read the relevant ADR before changing
anything it covers; add a new ADR (next number) when a spike or task makes a new decision.
Never edit an accepted ADR's decision — supersede it with a new one.

| # | Title | Status |
|---|---|---|
| 0001 | [Next.js frontend + FastAPI backend](0001-nextjs-frontend-fastapi-backend.md) | Accepted |
| 0002 | [Ollama for development only; user keys in production](0002-ollama-dev-only-byok-prod.md) | Accepted |
| 0003 | [Deepgram for speech-to-text and text-to-speech](0003-deepgram-for-voice.md) | Accepted |
| 0004 | [Azure AI Speech for pronunciation assessment](0004-azure-pronunciation-assessment.md) | Accepted |
| 0005 | [PostgreSQL + SQLAlchemy 2 (async) + Alembic](0005-postgres-sqlalchemy-alembic.md) | Accepted |
| 0006 | [Taskiq + Redis for background jobs](0006-taskiq-redis-background-jobs.md) | Accepted |
| 0007 | [Single built-in local user until accounts exist](0007-single-local-user-until-accounts.md) | Accepted |
| 0008 | [Pydantic AI behind our own LLMService interface](0008-pydantic-ai-behind-llmservice.md) | Accepted |
| 0009 | [Relay voice audio through the backend](0009-voice-relay-through-backend.md) | Accepted |
| 0010 | [Typed API client generated from OpenAPI](0010-openapi-generated-client.md) | Accepted |
| 0011 | [No raw audio storage](0011-no-raw-audio-storage.md) | Accepted |
| 0012 | Default Ollama model and reference eval results (written in Phase 2, Task 2.5) | Planned |
| 0013 | Deepgram STT model: Flux vs Nova-3 (Phase 3, Task 3.1) | Planned |
| 0014 | Azure integration: REST vs Speech SDK (Phase 4, Task 4.1) | Planned |
| 0015 | [Development-only cloud reference model for evals](0015-cloud-reference-model-for-evals.md) | Accepted |
| 0016 | [Opt out of Deepgram's Model Improvement Program](0016-deepgram-model-improvement-opt-out.md) | Accepted |

## Template

```markdown
# NNNN. Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
What problem or question forced a decision? Include constraints and evidence (spike results, docs links).

## Decision
What we will do, stated plainly.

## Consequences
What becomes easier, what becomes harder, what we must watch.

## Alternatives considered
- Option — why not.
```
