# Articulate AI

An AI communication coach for software engineers who want to communicate well in English.
Practise real workplace conversations by text or voice, get specific feedback, train your
pronunciation, and track your progress.

> **Status:** Phase 1 (text practice) done — next is
> [Phase 2: feedback engine](docs/tasks/q1-phase-02-feedback-engine.md).

## Features (planned)
- Scenario role-play (stand-ups, PM conversations, interviews, code review, negotiations) — text & voice
- Feedback reports with scores, quotes and better phrasing
- Speaking stats (pace, filler words, pauses) — Deepgram
- Pronunciation practice with per-word and per-sound scores — Azure AI Speech
- Progress dashboard, baseline assessment, coach memory, daily drills
- Writing coach for Slack messages, emails and PR descriptions; custom scenarios
- Q2: accounts, reminder emails, bring-your-own AI key (Anthropic / OpenAI / Gemini)

## Tech
Next.js 16 · FastAPI · PostgreSQL · Redis · Taskiq · Pydantic AI · Ollama (dev) · Deepgram · Azure AI Speech

## Quick start (once Phase 0 is done)
```bash
make setup && make infra-up && make db-migrate && make seed && make dev
```
See [docs/guides/local-development.md](docs/guides/local-development.md).

## Documentation
Start at [docs/README.md](docs/README.md). AI agents: read [AGENTS.md](AGENTS.md).
