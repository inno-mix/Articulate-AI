# Architecture Overview

> Read with: `docs/product-spec.md` (what/why), `data-model.md`, `api-contract.md`,
> `ai-layer.md`, `voice-and-pronunciation.md`, `security-privacy.md`.

## 1. System diagram

```
Browser — Next.js UI (http://localhost:3000)
   │  REST + SSE (JSON)                 │  WebSocket (voice: PCM audio + JSON events)
   ▼                                    ▼
FastAPI (http://localhost:8000, prefix /api/v1)
   ├─ Routers (thin) ─► Services (business logic) ─► Repositories via SQLAlchemy
   ├─ LLMService ─────► Ollama  (dev only, http://localhost:11434)
   │               └──► user's Anthropic / OpenAI / Gemini key (Phase 9)
   ├─ Voice relay ────► Deepgram STT (streaming) + TTS (streaming)
   ├─ Pronunciation ──► Azure AI Speech pronunciation assessment
   ├─► PostgreSQL 17 (Docker, :5432)
   └─► Redis 7 (Docker, :6379) ── Taskiq broker ──► Worker process
                                                     ├─ feedback reports
                                                     ├─ coach memory updates
                                                     └─ (Q2) scheduler: reminder + summary emails ─► SMTP (Mailpit :1025)
```

## 2. Components and responsibilities

| Component | Location | Owns | Must NOT |
|---|---|---|---|
| Web UI | `apps/web` | Pages, components, client state, mic capture, audio playback, calling the API | Hold secrets, call Ollama/Deepgram/Azure directly, contain business rules (scoring, limits) beyond input hints |
| API | `apps/api/app` | HTTP/WS endpoints, validation, auth (Q2), business logic, DB access, provider calls, enqueueing jobs | Render HTML, block the event loop with CPU/sync IO |
| Worker | `apps/api/app/worker` (same codebase, separate process) | Long-running jobs (reports, memory updates), scheduled jobs (Q2 emails) | Serve HTTP |
| Content | `apps/api/content` | Scenario, rubric, pronunciation and drill-template YAML | Contain code |
| Evals | `apps/api/evals` | Report-quality test cases and runner | Run in normal `pytest` (they call real models) |
| Infra | `infra/docker-compose.yml` | Postgres, Redis, (Q2) Mailpit | Run Ollama (Docker on macOS cannot use the Apple GPU) |

## 3. Backend layering (strict)

```
api/v1/<router>.py      → parse/validate request, call ONE service function, map to response schema
services/<domain>.py    → business rules, transactions, calls llm/, voice/, pronunciation/, worker tasks
models/<domain>.py      → SQLAlchemy ORM tables (no logic beyond simple properties)
schemas/<domain>.py     → Pydantic request/response models (API contract)
llm/, voice/, pronunciation/ → provider adapters behind Protocols; fakes live next to real ones
worker/                 → Taskiq broker + task functions that call services
core/                   → config, db session, errors, logging, (Q2) security
```

Rules:
- Routers never touch the ORM directly; services never import FastAPI `Request`/`Response`.
- All provider access goes through a Protocol (`LLMService`, `SpeechToText`,
  `TextToSpeech`, `PrerecordedTranscriber`, `PronunciationAssessor`, (Q2) `EmailSender`).
  Implementations are chosen in one place: `app/deps.py` based on `Settings`.
- Every DB query that returns user data filters by `user_id` (see `security-privacy.md`).

## 4. Key flows

### 4.1 Text practice turn
1. `POST /api/v1/sessions/{id}/messages` `{content}`.
2. Service validates: session active, belongs to user, turn limit, length, crisis check.
3. Saves the user message and **commits**, builds the role-play prompt (scenario + profile + coach
   notes + history); no database connection is held while the reply streams.
4. Streams `LLMService.stream_chat(...)` deltas to the client as SSE `delta` events.
5. On completion saves the assistant message, sends `done`. On provider error sends `error` and
   saves nothing for the assistant turn (the user message stays).

### 4.2 End session → report
1. `POST /api/v1/sessions/{id}/end` → status `ended` (or `abandoned` if < 2 user turns).
2. Creates `feedback_reports` row `status=pending`, enqueues `generate_feedback_report(report_id)`.
3. Worker: loads transcript → (voice) computes speaking stats → calls
   `LLMService.generate_structured(FeedbackAnalysis)` (≤ 2 retries) → drops highlights whose quote is
   not in user messages → computes overall → saves report `ready` → writes `skill_scores` →
   (Phase 5) enqueues `update_coach_memory(report_id)`.
4. UI polls `GET /api/v1/sessions/{id}/report` every 2 s.
5. Failure → `status=failed` with `error_code`; `POST .../report/retry` re-enqueues.

### 4.3 Voice turn
See `voice-and-pronunciation.md` §2 for the full WebSocket protocol and state machine.

### 4.4 Pronunciation attempt
Browser records WAV → `POST /api/v1/pronunciation/attempts` (multipart) → validate WAV →
`PronunciationAssessor.assess(...)` → save attempt + `skill_scores(pronunciation)` → return result.
Synchronous request (Azure short audio responds in ~1–3 s).

## 5. Configuration & provider selection

`app/core/config.py` → `Settings` (pydantic-settings, reads `apps/api/.env`). Provider switches:

| Setting | Values | Default (dev) | Notes |
|---|---|---|---|
| `APP_ENV` | `development` \| `test` \| `production` | `development` | |
| `LLM_PROVIDER` | `ollama` \| `fake` \| `user_credentials` | `ollama` | `ollama`/`fake` forbidden in production (startup error). `user_credentials` arrives in Phase 9 |
| `STT_PROVIDER` / `TTS_PROVIDER` | `deepgram` \| `fake` | `deepgram` | `fake` forbidden in production |
| `PRONUNCIATION_PROVIDER` | `azure` \| `fake` | `azure` | `fake` forbidden in production |
| `AUTH_MODE` | `local_single_user` \| `accounts` | `local_single_user` | `accounts` from Phase 7; `local_single_user` forbidden in production |
| `ALLOWED_HOSTS` | host names | `localhost,127.0.0.1` | checked by the request guard on every HTTP/WebSocket request |
| `EVAL_*_API_KEY` | owner's cloud key | empty | evals only (ADR-0015); never used by the app; rejected in production |

Fakes make the whole app runnable and testable offline (E2E tests use them).

## 6. Local runtime

| Process | Command (via `make dev`) | Port |
|---|---|---|
| Web | `pnpm --filter web dev` | 3000 |
| API | `uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` | 8000 |
| Worker | `uv run taskiq worker app.worker.broker:broker app.worker.tasks` | — |
| Scheduler (Q2) | `uv run taskiq scheduler app.worker.scheduler:scheduler app.worker.tasks` | — |
| Postgres / Redis | `docker compose -f infra/docker-compose.yml up -d` | 5432 / 6379 |
| Mailpit (Q2) | same compose file, profile `mail` | 8025 (UI) / 1025 (SMTP) |
| Ollama | macOS app (native) | 11434 |

The API binds to `127.0.0.1` only — in Q1 there is no login.

## 7. Browser ↔ API communication

- The browser calls FastAPI directly at `NEXT_PUBLIC_API_URL` (`http://localhost:8000/api/v1`).
- CORS allowlist = `CORS_ORIGINS` (`http://localhost:3000`), `allow_credentials=True`.
- `RequestGuardMiddleware` rejects unknown `Host` headers and cross-site `Origin`s on unsafe
  requests and WebSocket handshakes (security rule S15).
- `localhost:3000` and `localhost:8000` are the **same site** (ports don't matter for cookies), so
  Q2 httpOnly auth cookies work with `credentials: "include"` and on the WebSocket handshake.
- Types: FastAPI's OpenAPI is exported to `apps/api/openapi.json` and converted to
  `apps/web/src/lib/api/schema.ts` (`make gen-client`). CI fails if it's stale.
- Next.js server components may call the API too (forwarding cookies in Q2), but most data fetching
  is client-side with TanStack Query.

## 8. Repository layout

```
Articulate AI/                      ← repo root (NOTE: path contains a space — always quote it)
├── AGENTS.md  CLAUDE.md  README.md  Makefile  package.json  pnpm-workspace.yaml  .gitignore  .editorconfig
├── apps/
│   ├── web/                        Next.js 16 app (see coding-conventions.md §3)
│   │   ├── public/worklets/pcm-capture-processor.js
│   │   ├── src/app/…               routes
│   │   ├── src/components/ui/…     shadcn/ui primitives
│   │   ├── src/features/<feature>/ components, hooks, api calls per feature
│   │   ├── src/lib/api/            client.ts, schema.ts (generated), sse.ts, events.ts, errors.ts
│   │   ├── src/lib/                env.ts, query-client.ts, timezones.ts (Q2)
│   │   ├── src/lib/audio/          pcm.ts, mic-capture.ts, pcm-player.ts, wav.ts, voice-socket.ts
│   │   ├── tests/                  Vitest
│   │   └── e2e/                    Playwright
│   └── api/                        FastAPI (uv project)
│       ├── app/{main.py,deps.py}
│       ├── app/core/               config.py, db.py, redis.py, errors.py, logging.py, request_guard.py
│       ├── app/domain/             dimensions.py, enums.py, limits.py, constants.py, safety_phrases.py (no IO)
│       ├── app/auth/               (Q2) passwords, tokens, cookies, csrf, TokenVerifier
│       ├── app/models/  app/schemas/  app/api/v1/  app/services/
│       ├── app/llm/                base.py, errors.py, factory.py, providers.py, generation.py, pydantic_ai_service.py, fake.py, prompts/, outputs.py
│       ├── app/voice/              base.py, deepgram_common.py, deepgram_stt.py, deepgram_tts.py, deepgram_prerecorded.py, fake.py, relay.py, protocol.py, metrics.py, sentences.py, voices.py
│       ├── app/pronunciation/      base.py, azure.py, fake.py, wav.py
│       ├── app/worker/             broker.py, tasks/…, (Q2) scheduler.py
│       ├── app/content/            loader.py (YAML → DB)
│       ├── app/cli.py              management commands (seed, reset, claim-local-data)
│       ├── content/                scenarios/, rubrics/, pronunciation/, drills/
│       ├── evals/                  cases/, run.py
│       ├── spikes/                 throwaway spike scripts (not imported by app)
│       ├── migrations/             Alembic
│       └── tests/                  unit/, integration/, live/, fixtures/, support/
├── backups/                        local database backups (git-ignored)
├── infra/docker-compose.yml
└── docs/                           this documentation
```
