# Local Development

> Target machine: Apple M1, **8 GB RAM**, macOS. The repo path contains a space
> (`…/Projects/Articulate AI`) — always quote paths in shell commands and scripts.

## 1. Prerequisites

| Tool | Version | Status on owner's machine | Install |
|---|---|---|---|
| Node.js | ≥ 22 (24 LTS recommended) | 22.12.0 ✅ | `brew install node@24` (optional) |
| pnpm | 10.x | 10.29.3 ✅ | `npm i -g pnpm` |
| Python | 3.12.x | 3.12.4 ✅ | – |
| uv | ≥ 0.11 | 0.11.32 ✅ | `brew install uv` |
| Docker Desktop | ≥ 29 | 29.7.2 ✅ | – (set memory limit to **2 GB**: Settings → Resources) |
| Git | any recent | 2.39.5 ✅ | – |
| Ollama | ≥ 0.5 (structured outputs) | 0.21.2 ✅ | macOS app |
| Deepgram account + API key | – | ⬜ needed from Phase 3 | https://console.deepgram.com |
| One cloud LLM API key (Anthropic, OpenAI or Google) for the eval reference model | – | ⬜ needed from Phase 2 (Task 2.5) | Owner's own account; development only (ADR-0015) |
| Azure account + Speech resource (F0 free tier) + key + region | – | ⬜ needed from Phase 4 | Azure portal → create "Speech" resource, pricing tier F0 |

Agents: you cannot create accounts or obtain keys. When a phase needs one, stop and ask the owner
to add it to `apps/api/.env`.

## 2. One-time setup

```bash
# Ollama (dev LLM)
launchctl setenv OLLAMA_CONTEXT_LENGTH 8192
launchctl setenv OLLAMA_MAX_LOADED_MODELS 1
# restart the Ollama app, then:
ollama pull llama3.2:latest     # already installed
ollama pull qwen3:4b            # candidate, compared in Phase 2 evals

# project
make setup          # uv sync, pnpm install, copies .env.example → .env if missing
make infra-up       # Postgres + Redis in Docker
make db-migrate     # alembic upgrade head
make seed           # local user + YAML content
make dev            # web :3000, api :8000, worker
```

Open http://localhost:3000.

**Q1 has no profile screen** (it arrives in Phase 7). The local user starts with English level `B2`
and timezone `UTC`. To change them before then (optional):

```bash
curl -s -X PATCH http://localhost:8000/api/v1/me/profile \
  -H 'Content-Type: application/json' \
  -d '{"timezone": "Asia/Manila", "english_level": "B1"}'
```

## 3. Make targets (defined in Phase 0; extended later)

| Target | Does |
|---|---|
| `make help` | default target: lists all targets with descriptions |
| `make setup` | `uv sync` in `apps/api`, `pnpm install`, create `.env` files from examples if missing, install Playwright browsers (chromium only) |
| `make infra-up` / `make infra-down` | `docker compose -f infra/docker-compose.yml up -d` / `down` |
| `make infra-up-mail` | also starts Mailpit (Q2) |
| `make db-migrate` | `uv run alembic upgrade head` |
| `make db-revision m="message"` | `uv run alembic revision --autogenerate -m "$(m)"` |
| `make db-reset` | back up first (unless `NO_BACKUP=1`), then drop + recreate `articulate` DB, migrate, seed (**local only**, asks for confirmation unless `FORCE=1`) |
| `make db-backup` | `pg_dump -Fc` of `articulate` into `backups/articulate-<timestamp>.dump` (git-ignored) |
| `make db-restore FILE=backups/….dump` | restore a backup over the dev DB (`pg_restore --clean --if-exists`; asks for confirmation unless `FORCE=1`) |
| `make seed` | `uv run python -m app.cli seed` |
| `make dev` | runs api, worker, web together (`pnpm dev:all` → `concurrently`) |
| `make dev-fake` | same with fake providers: `LLM_PROVIDER=fake STT_PROVIDER=fake TTS_PROVIDER=fake PRONUNCIATION_PROVIDER=fake` (Phase 7 adds `EMAIL_PROVIDER=fake`; Phase 9 switches the LLM part to `user_credentials` + `FAKE_PROVIDER_MODELS=true`) |
| `make test` | `make test-api test-web` |
| `make test-api` | `uv run pytest -m "not live"` (needs `make infra-up`; uses DB `articulate_test`) |
| `make test-web` | `pnpm --filter web test` (Vitest) |
| `make test-e2e` | Playwright with its own servers and data: web 3100, api 8100, worker, Redis db 2, DB `articulate_e2e`, fake providers (see `testing-strategy.md` §4). If Next.js refuses a second dev server, stop `make dev` first |
| `make test-live` | `uv run pytest -m live` (real Ollama/Deepgram/Azure; costs money for Deepgram/Azure) |
| `make lint` | ruff check, ruff format --check, mypy, `pnpm --filter web lint`, `pnpm --filter web format:check` (Prettier), `pnpm --filter web typecheck` |
| `make format` | ruff format, ruff check --fix, prettier --write |
| `make gen-client` | export OpenAPI → `apps/api/openapi.json` → `apps/web/src/lib/api/schema.ts` |
| `make check-client` | `make gen-client` then `git diff --exit-code` on both files |
| `make eval` | Ollama eval run: `uv run python -m evals.run --provider ollama --model $(OLLAMA_MODEL)` |
| `make eval-cloud PROVIDER=anthropic MODEL=<id> CONFIRM=1` | Reference eval run on the owner's cloud key (costs money; refuses without `CONFIRM=1` or without the matching `EVAL_*_API_KEY`) |
| `make check` | `make lint check-client test` — run before every commit |
| `make up-full` / `make down-full` | (Phase 10) production-like stack in Docker behind Caddy on `https://localhost:8443` |

## 4. Services and ports

| Service | How | Port | Credentials (local only) |
|---|---|---|---|
| Web (Next.js) | native | 3000 | – |
| API (FastAPI) | native, `127.0.0.1` | 8000 (docs at `/docs`) | – |
| Worker (Taskiq) | native | – | – |
| PostgreSQL 17 | Docker `postgres:17-alpine` | 5432 | db `articulate`, user `articulate`, password `articulate`; test db `articulate_test` |
| Redis 7 | Docker `redis:7-alpine` | 6379 | – (db 0 app, db 1 tests) |
| Mailpit (Q2) | Docker `axllent/mailpit`, profile `mail` | 8025 UI / 1025 SMTP | – |
| Ollama | macOS app | 11434 | – |
| E2E web / API (during `make test-e2e`) | native | 3100 / 8100 | uses `articulate_e2e` and Redis db 2 |

`infra/initdb/01-create-databases.sql` creates `articulate_test` and `articulate_e2e` on first start.

## 5. Environment variables

### `apps/api/.env` (template: `apps/api/.env.example`)
| Name | Example / default | Phase | Notes |
|---|---|---|---|
| `APP_ENV` | `development` | 0 | `development` \| `test` \| `production` |
| `LOG_LEVEL` | `INFO` | 0 | |
| `DATABASE_URL` | `postgresql+asyncpg://articulate:articulate@localhost:5432/articulate` | 0 | |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://articulate:articulate@localhost:5432/articulate_test` | 0 | |
| `REDIS_URL` | `redis://localhost:6379/0` | 0 | |
| `CORS_ORIGINS` | `http://localhost:3000` | 0 | comma-separated |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | 0 | comma-separated; the request guard rejects other `Host` headers |
| `API_PORT` | `8000` | 0 | shell variable read by `pnpm run dev:api` (not by `Settings`); E2E sets 8100 |
| `FRONTEND_URL` | `http://localhost:3000` | 0 | used in email links |
| `AUTH_MODE` | `local_single_user` | 0 | default becomes `accounts` in Phase 7 (Task 7.8) |
| `LLM_PROVIDER` | `ollama` | 0 | `ollama` \| `fake` \| `user_credentials` (Phase 9) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | 0 | no `/v1` suffix; the adapter adds it |
| `OLLAMA_MODEL` | `llama3.2:latest` | 0 | final value chosen in Phase 2 |
| `LLM_TIMEOUT_SECONDS` | `60` | 1 | |
| `EVAL_ANTHROPIC_API_KEY` / `EVAL_OPENAI_API_KEY` / `EVAL_GOOGLE_API_KEY` | *(secret, optional)* | 2 | owner's own key for the eval reference model only; never used by the app; rejected in production |
| `STT_PROVIDER` / `TTS_PROVIDER` | `deepgram` | 3 | or `fake` |
| `DEEPGRAM_API_KEY` | *(secret)* | 3 | |
| `DEEPGRAM_STT_MODEL` | `nova-3` | 3 | or `flux-general-en` after the spike |
| `DEEPGRAM_TTS_VOICE` | `aura-2-thalia-en` | 3 | default voice |
| `PRONUNCIATION_PROVIDER` | `azure` | 4 | or `fake` |
| `AZURE_SPEECH_KEY` | *(secret)* | 4 | |
| `AZURE_SPEECH_REGION` | e.g. `eastus` | 4 | |
| `AZURE_SPEECH_MAX_CONCURRENCY` | `1` | 4 | F0 allows 1 |
| `FAKE_PRONUNCIATION_LOW_WORDS` | empty | 4 | dev/test only: comma-separated words the fake assessor scores low (E2E sets `cache`) |
| `JWT_SECRET` | *(secret, ≥ 32 bytes)* | 7 | `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `COOKIE_SECURE` | `false` | 7 | `true` outside localhost |
| `EMAIL_PROVIDER` | `smtp` | 7 | `smtp` \| `fake` (fake is dev/test only) |
| `SMTP_HOST` / `SMTP_PORT` | `localhost` / `1025` | 7 | Mailpit |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | empty | 7 | |
| `EMAIL_FROM` | `Articulate AI <no-reply@articulate.localhost>` | 7 | |
| `EMAIL_TOKEN_SECRET` | *(secret)* | 8 | unsubscribe links |
| `API_PUBLIC_URL` | `http://localhost:8000` | 8 | base URL used in unsubscribe links |
| `ENCRYPTION_KEYS` | `1:<base64 32 bytes>` | 9 | `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"` |
| `ENCRYPTION_ACTIVE_KEY_VERSION` | `1` | 9 | |
| `LLM_KEY_VALIDATION` | `live` | 9 | `live` \| `fake` (fake is dev/test only) |
| `LLM_FALLBACK_TO_OLLAMA` | `true` | 9 | use Ollama when a user has no key; forced `false` in production |
| `FAKE_PROVIDER_MODELS` | `false` | 9 | dev/test only: every provider returns the fake model (E2E) |

### `apps/web/.env.local` (template: `apps/web/.env.example`)
| Name | Default |
|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000/api/v1` |

## 6. Memory budget (8 GB)

| Consumer | Approx. |
|---|---|
| macOS + browser | ~3 GB |
| Ollama with a 3–4B model, 8K context | ~2.5–3.5 GB |
| Docker VM (Postgres + Redis) | ≤ 2 GB (cap it) |
| Next.js dev server | 0.5–1 GB |
| API + worker | ~0.3 GB |

Your practice history lives in the Docker volume. Run `make db-backup` before risky changes;
`make db-reset` takes a backup automatically.

Tips: close other apps; use `make dev-fake` when working on UI only (Ollama idle unloads the model
after 5 min); if memory is tight, Postgres/Redis can run via Homebrew instead of Docker (update
`DATABASE_URL`/`REDIS_URL`).

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `/health` shows `llm: unavailable` | Ollama app not running, or model not pulled: `ollama list` |
| Reports fail with `llm_invalid_output` often | context too small (`OLLAMA_CONTEXT_LENGTH`), or model too weak — run `make eval`, try the other model |
| Very slow responses | another model loaded (`ollama ps`), swap pressure (Activity Monitor), long transcript |
| Mic permission denied | browser site settings → allow microphone for `localhost:3000` |
| No audio playback | click anywhere first (browsers block audio until a user gesture); the voice page starts audio on the "Start" click |
| Azure 429 | F0 allows one request at a time; wait and retry |
| `port already in use` | `lsof -i :8000` and stop the old process |
| Worker won't stop after a SIGTERM | taskiq's process manager can deadlock when it gets two SIGTERMs at once (e.g. `kill -TERM -<group>` hits both `uv run` and taskiq, and `uv` forwards another). Ctrl+C and `make dev`'s own shutdown are fine. Fix: `pkill -f "taskiq worker"`. |
| Is the worker consuming jobs? | `cd apps/api && uv run python -m app.cli ping-worker` prints `pong:cli` within 10 s (dev tool; refuses in production) |
| Claude desktop `preview_start` fails with `getcwd: Operation not permitted` | macOS blocks the app from reading `~/Documents`. Allow it in System Settings → Privacy & Security → Files and Folders, or run `make dev` in a terminal and open `http://localhost:3000` in the browser pane |
| Stale jobs in Redis | `cd apps/api && uv run python -m app.cli flush-redis` empties the database in `REDIS_URL` (dev tool; refuses in production) |
