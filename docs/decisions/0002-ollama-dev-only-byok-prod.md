# 0002. Ollama for development only; user keys in production

- Status: Accepted
- Date: 2026-09-17

## Context
The owner wants free local development and, for real users, each user supplies their own
Anthropic / OpenAI / Gemini key (built last, Phase 9). The dev machine has 8 GB RAM.

## Decision
- `LLM_PROVIDER=ollama` in development with a 3–4B model (`llama3.2:latest` or `qwen3:4b`,
  chosen by evals in Phase 2); `OLLAMA_CONTEXT_LENGTH=8192`.
- `Settings` refuses `ollama`/`fake` when `APP_ENV=production`.
- Phase 9 adds `LLM_PROVIDER=user_credentials`: per-request provider built from the user's
  encrypted key. Development falls back to Ollama when a user has no key; production returns
  `409 llm_not_configured`.

## Consequences
- Small models produce weaker, sometimes invalid structured output → schema-constrained decoding
  (Ollama native structured outputs), validation + retries, and an eval suite are mandatory.
- Latency locally is several seconds; UX must show progress states.
- Going live requires Phase 9.

## Alternatives considered
- App-owned cloud key — rejected by owner (users bring keys).
- Ollama in Docker — rejected: no Apple GPU access in Docker on macOS.

## Related
- ADR-0015 adds a development-only cloud reference model for evals (the app runtime stays on Ollama).
