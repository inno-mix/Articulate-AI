# AGENTS.md — Articulate AI

AI communication coach for software engineers improving their English. Text + voice role-play
practice, feedback reports, pronunciation practice, progress tracking.
**Status:** Phase 0 (foundations) done. Next: Phase 1 — `docs/tasks/q1-phase-01-text-practice.md`.

## Read first
1. `docs/guides/agent-workflow.md` — how to work here (task loop, hard rules, definition of done).
2. `docs/tasks/README.md` — phase order and status; pick the first unfinished task.
3. The task's "Read before starting" list.
Full map: `docs/README.md`.

## Stack (details in docs/architecture/overview.md)
- `apps/web` — Next.js 16 (App Router), React 19, TypeScript strict, Tailwind v4, shadcn/ui,
  TanStack Query, openapi-fetch (types generated from the API). UI only.
- `apps/api` — Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async + Alembic, PostgreSQL 17,
  Redis 7, Taskiq worker, Pydantic AI v2 (behind `LLMService`), Deepgram SDK v5, Azure Speech.
- Dev LLM: Ollama on the host (never in production). Evals also use one cloud reference model with
  the owner's key (dev only). Users bring their own keys in Phase 9.
- Every Deepgram request sets `mip_opt_out=true` (no model-training use of users' audio).
- Package managers: `uv` (Python), `pnpm` (JS). Root `Makefile` wraps everything.

## Commands
```bash
make setup        # install deps, create .env files
make infra-up     # Postgres + Redis (Docker)
make db-migrate   # apply migrations
make seed         # local user + content
make dev          # web :3000, api :8000, worker   (make dev-fake = no Ollama/Deepgram/Azure)
make check        # lint + generated-client check + tests — run before every commit
make test-e2e     # Playwright journeys (phase end)
make eval         # LLM feedback quality on Ollama (when prompts/rubric/model change)
make eval-cloud   # same on the owner's cloud reference model (costs money — ask first)
make gen-client   # regenerate TS types after any API schema change
```

## Golden rules
1. Work on one task at a time; tick its checkboxes in the phase file; log evidence.
2. TDD: failing test → minimal code → `make check` → commit (Conventional Commits).
3. Never guess third-party APIs — query Context7 / official docs first.
4. Contracts in `docs/architecture/*` are binding; change docs + generated client in the same commit.
5. No new dependencies unless the task names them. Ask otherwise.
6. Never print, log or commit secrets. You can't create accounts/keys — ask the owner.
7. The repo path contains a space: quote paths in every shell command.
8. 8 GB RAM machine: one Ollama model at a time; use `make dev-fake` for UI-only work.
9. Evidence before claims: don't say "done/passing" without running the command.
10. Out-of-scope issues go to the completion log "Follow-ups", not into the current change.

## Layout
```
apps/web/src/{app,features,components,lib}     apps/api/app/{api/v1,services,models,schemas,llm,voice,pronunciation,worker,core,domain}
apps/api/{content,evals,migrations,tests,spikes} infra/docker-compose.yml   docs/
```
