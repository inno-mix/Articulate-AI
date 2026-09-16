# Testing Strategy

## 1. Layers

| Layer | Tool | Location | Runs in `make check` | Needs |
|---|---|---|---|---|
| Backend unit | pytest + pytest-asyncio | `apps/api/tests/unit/` | ✅ | nothing |
| Backend integration | pytest + httpx `AsyncClient(ASGITransport)`; WebSockets via `httpx-ws` (`ASGIWebSocketTransport`, same event loop) | `apps/api/tests/integration/` | ✅ | `make infra-up` (Postgres `articulate_test`, Redis db 1) |
| Backend live | pytest marker `live` | `apps/api/tests/live/` | ❌ (`make test-live`) | Ollama running; Deepgram/Azure keys |
| Frontend unit/component | Vitest + Testing Library + jsdom | `apps/web/tests/` | ✅ | nothing |
| End-to-end | Playwright (Chromium) | `apps/web/e2e/` | ❌ (`make test-e2e`, required before closing a phase) | `make dev-fake` servers + fake mic |
| LLM quality | eval runner | `apps/api/evals/` | ❌ (`make eval`, `make eval-cloud`) | Ollama; the owner's eval key for the reference run |

## 2. Backend details

### Configuration (`apps/api/pyproject.toml`)
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"   # asyncpg connections belong to one event loop
testpaths = ["tests"]
pythonpath = ["."]
markers = [
  "live: calls real external services (Ollama, Deepgram, Azure); excluded by default",
]
addopts = "-m 'not live' --strict-markers"
```

### Core fixtures (`tests/conftest.py`)
- The first lines of `tests/conftest.py` set `os.environ["APP_ENV"] = "test"` (and the fake
  provider variables) **before** importing anything from `app`, because the Taskiq broker is built
  from settings at import time (test → `InMemoryBroker`).
- `settings` — `Settings(APP_ENV="test", DATABASE_URL=TEST_DATABASE_URL, REDIS_URL=redis db 1,
  LLM_PROVIDER="fake", STT_PROVIDER="fake", TTS_PROVIDER="fake",
  PRONUNCIATION_PROVIDER="fake")`.
- `engine` (session scope) — creates schema once with `alembic upgrade head` against the test DB.
- `connection` (function scope) — one connection with an outer transaction, rolled back after
  each test (fast isolation).
- `db` — `AsyncSession(bind=connection, join_transaction_mode="create_savepoint")`.
- `session_factory` — `LockedSessionFactory` (`tests/support/db.py`): each
  `async with session_factory() as db` yields an `AsyncSession(bind=connection,
  join_transaction_mode="create_savepoint")` while holding a shared `asyncio.Lock`. Code that opens
  its own sessions (SSE streams, voice relay, worker tasks) receives this factory, so everything in
  a test shares the same rolled-back transaction, and concurrent tasks can't use the single
  connection at the same time (asyncpg would fail). Acquiring the lock times out after 5 s with
  "DB session held too long or nested — keep sessions short", which catches nested sessions and
  sessions kept open while other work waits. Tests must not query through `db` while a stream or
  voice relay is still running — await it first.
- `app` — `create_app(settings)` with dependency overrides: `get_db` → `db` fixture;
  `app.state.session_factory` → `session_factory`; provider factories → fakes that tests can
  configure. Lifespan is **not** run in tests (fixtures set `app.state` directly).
- `client` — `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`.
- `local_user` — seeded local user (+ profile + settings).
- `other_user` — a second user, for ownership tests.
- `fake_llm`, `fake_stt`, `fake_tts`, `fake_assessor` — instances injected into the app, so a test
  can script responses: `fake_llm.set_structured("FeedbackAnalysis", {...})`.
- `broker` — Taskiq `InMemoryBroker` swapped in so `.kiq()` executes inline in tests
  (`await broker.wait_all()` where needed).

### Factories (`tests/factories.py`)
Plain async functions: `make_scenario(db, **overrides)`, `make_session(db, user, scenario, mode,
status, turns=[("user","…"), …])`, `make_report(db, session, **overrides)`,
`make_speech(words=[("hello",0.0,0.4,0.99), …])`, `make_wav(seconds=1.0, rate=16000)` (sine wave
via stdlib `wave`), `make_pronunciation_set(db, sentences=[…])`.

### Event-loop rule
asyncpg connections belong to one event loop. Starlette's sync `TestClient` runs the app in another
thread/loop, so it can't share the `connection` fixture — use `httpx-ws` for WebSocket tests (check
its current API with Context7 before use). If that proves impossible, use `TestClient` with a
`clean_db` fixture that truncates all tables after the test, and mark those tests
`@pytest.mark.usefixtures("clean_db")`.

### Rules
- Every endpoint: happy path, validation error, not-found/ownership (other user's id → 404), and
  each documented error code it can return.
- Every service with branching logic: unit tests per branch using fakes.
- Pure functions (metrics, sentence splitter, quote matcher, cursor encoding, streak): table-driven
  tests with `pytest.mark.parametrize` including edge cases (empty, boundary values).
- Provider adapters (Deepgram, Azure, Pydantic AI): unit tests with mocked transports
  (`respx` for HTTP; SDK connection objects replaced by fakes via small wrapper seams) + one `live`
  test each.
- Migrations: `tests/integration/test_zz_migrations.py` upgrades/downgrades the full chain.
- Coverage: `uv run pytest --cov=app --cov-report=term-missing`; services ≥ 80 %.

## 3. Frontend details

- Vitest config: `environment: "jsdom"`, `setupFiles: ["tests/setup.ts"]` (Testing Library
  jest-dom matchers, MSW server).
- **MSW** (`msw`) mocks API calls in component tests using fixtures typed from `schema.ts`.
- Audio: `mic-capture` and `pcm-player` are wrapped behind small interfaces so components are tested
  with fakes. The AudioWorklet only forwards raw Float32 frames; downsampling, chunking and PCM
  encoding live in the pure module `src/lib/audio/pcm.ts`, which is unit-tested.
- SSE parser (`src/lib/api/sse.ts`): unit tests with a fake `ReadableStream` (chunks split in odd
  places, multiple events per chunk, error event).
- Each page: renders loading, empty, error and success states.

## 4. End-to-end (Playwright)

- `playwright.config.ts` runs the app **in isolation from your dev servers and data**:
  - Three `webServer` entries (shared settings live in `apps/web/e2e/env.ts`):
    - API: first resets + seeds `articulate_e2e` (`app.cli reset-db --force`) and flushes Redis
      db 2 (`app.cli flush-redis`), then `pnpm run dev:api` with `API_PORT=8100`. Playwright
      starts web servers **before** `globalSetup`, so the reset lives here: nothing can connect
      to the old schema. There is no `globalSetup`/`globalTeardown`.
    - **Worker** (reports and memory updates need it): `pnpm run dev:worker` with
      `wait: { stderr: /Listening started/ }`.
    - Web: `pnpm --filter web dev --port 3100` with `NEXT_DIST_DIR=.next-e2e` (`next.config.ts`
      reads it for `distDir`).
    - `reuseExistingServer: false`. Playwright stops each server by killing its process group;
      keep that default (see the worker shutdown pitfall in `local-development.md` §7).
  - Environment for API and worker: `APP_ENV=development`, `DATABASE_URL=…/articulate_e2e`,
    `REDIS_URL=redis://localhost:6379/2`, `CORS_ORIGINS=http://localhost:3100`, fake providers,
    `FAKE_PRONUNCIATION_LOW_WORDS=cache` (Phase 4).
    Web: `NEXT_PUBLIC_API_URL=http://localhost:8100/api/v1`,
    `NEXT_PUBLIC_WS_URL=ws://localhost:8100/api/v1`. `use.baseURL = "http://localhost:3100"`.
  - Chromium with `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream
    --use-file-for-fake-audio-capture=e2e/fixtures/hello.wav`.
  - If Next.js refuses to start a second dev server in the same project, stop `make dev` first.
  - Q1 has a single local user, so specs share data: run with `workers: 1` and
    `fullyParallel: false`, and write each spec so it doesn't depend on another spec's leftovers
    (create what it needs). From Phase 7 each spec registers its own user and parallel workers may
    be enabled.
- `smoke.spec.ts` (Phase 0): home renders with "API: ok" and no console errors; the worker answers
  `app.cli ping-worker`.
- Journeys (each is one spec file, added in the phase that builds it):
  1. `text-practice.spec.ts` — pick scenario → send 2 messages → end → report ready.
  2. `voice-practice.spec.ts` — start voice session → PTT turn → assistant turn appears → end.
  3. `pronunciation.spec.ts` — record a sentence → coloured words appear.
  4. `progress.spec.ts` — dashboard shows data after journeys 1–3.
  5. `drills.spec.ts`, `writing.spec.ts`, `custom-scenario.spec.ts`.
  6. (Q2) `auth.spec.ts` — register → verify via Mailpit API → onboarding → logout/login.
  7. (Q2) `byok.spec.ts` — add a key (fake validator) → practice uses it.

## 5. Evals

See `docs/architecture/ai-layer.md` §8. When prompts, rubric or model change, run `make eval`
(Ollama) and — after asking the owner, because it costs money — `make eval-cloud` (reference
model). Paste both summaries into the phase completion log.

## 6. Definition of "tests pass"

`make check` exits 0 **and** (at phase end) `make test-e2e` exits 0. Paste the final lines of the
output as evidence in the task completion log. A skipped or xfail test must have a comment with a
reason and a task id.
