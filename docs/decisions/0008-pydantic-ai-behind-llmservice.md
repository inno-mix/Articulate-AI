# 0008. Pydantic AI behind our own LLMService interface

- Status: Accepted
- Date: 2026-09-17

## Context
We need Ollama now and Anthropic/OpenAI/Gemini with per-user keys later, streaming text and
validated structured output, plus easy testing.

## Decision
Use Pydantic AI v2 (`OllamaModel` + `NativeOutput` for Ollama; `AnthropicModel`,
`OpenAIChatModel`, `GoogleModel` with per-request provider objects later) wrapped by
`PydanticAILLMService`, which implements our `LLMService` Protocol (`stream_chat`,
`complete_text`, `generate_structured`). App code depends only on the Protocol;
`FakeLLMService` implements it for tests.

## Consequences
- Library upgrades are contained in one adapter file.
- Agents must check Pydantic AI docs (Context7) before editing the adapter.

## Alternatives considered
- LiteLLM — broad provider coverage, but weaker typed structured-output story for our needs.
- Direct provider SDKs — three adapters to maintain plus Ollama.
- Vercel AI SDK in Next.js — conflicts with ADR-0001.
