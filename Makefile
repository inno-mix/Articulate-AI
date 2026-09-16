SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Relative paths only: the absolute repo path contains a space.
API := apps/api
WEB := apps/web
COMPOSE := docker compose -f infra/docker-compose.yml
OLLAMA_MODEL ?= $(shell grep -E '^OLLAMA_MODEL=' $(API)/.env 2>/dev/null | cut -d= -f2)
FAKE_ENV := LLM_PROVIDER=fake STT_PROVIDER=fake TTS_PROVIDER=fake PRONUNCIATION_PROVIDER=fake

.PHONY: help setup infra-up infra-down infra-up-mail db-migrate db-revision db-reset db-backup \
	db-restore seed dev dev-fake test test-api test-web test-e2e test-live lint format gen-client \
	check-client eval eval-cloud check

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies and create .env files from the examples
	cd $(API) && uv sync
	pnpm install
	@if [ -f $(API)/.env.example ] && [ ! -f $(API)/.env ]; then cp $(API)/.env.example $(API)/.env; echo "created $(API)/.env"; fi
	@if [ -f $(WEB)/.env.example ] && [ ! -f $(WEB)/.env.local ]; then cp $(WEB)/.env.example $(WEB)/.env.local; echo "created $(WEB)/.env.local"; fi
	@if [ -d $(WEB) ] && [ "$${SKIP_PLAYWRIGHT:-0}" != "1" ]; then pnpm --filter web exec playwright install chromium; fi

infra-up: ## Start Postgres and Redis (Docker)
	$(COMPOSE) up -d --wait postgres redis

infra-down: ## Stop Docker services (data is kept)
	$(COMPOSE) --profile mail down

infra-up-mail: ## Start Postgres, Redis and Mailpit (Q2)
	$(COMPOSE) --profile mail up -d --wait postgres redis mailpit

db-migrate: ## Apply database migrations
	cd $(API) && uv run alembic upgrade head

db-revision: ## Create a migration: make db-revision m="message"
	@test -n "$(m)" || (echo 'usage: make db-revision m="message"' && exit 1)
	cd $(API) && uv run alembic revision --autogenerate -m "$(m)"

db-reset: ## Back up, then drop/recreate/migrate/seed the dev DB (local only; FORCE=1 skips the prompt)
	@if [ "$${APP_ENV:-}" = "production" ] || grep -qE '^APP_ENV=production' $(API)/.env 2>/dev/null; then echo "refusing: APP_ENV is production"; exit 1; fi
	@if [ "$(FORCE)" != "1" ]; then read -r -p "This deletes the local database. Type RESET to continue: " ans; [ "$$ans" = "RESET" ] || (echo "aborted" && exit 1); fi
	@if [ "$(NO_BACKUP)" != "1" ]; then $(MAKE) --no-print-directory db-backup; fi
	cd $(API) && uv run python -m app.cli reset-db --force

db-backup: ## Save a pg_dump of the dev DB into backups/
	@mkdir -p backups
	@file="backups/articulate-$$(date +%Y%m%d-%H%M%S).dump"; \
	  $(COMPOSE) exec -T postgres pg_dump -U articulate -Fc articulate > "$$file.partial" && mv "$$file.partial" "$$file" && echo "backup written: $$file"

db-restore: ## Restore a backup: make db-restore FILE=backups/x.dump (FORCE=1 skips the prompt)
	@test -n "$(FILE)" || (echo "usage: make db-restore FILE=backups/<file>.dump" && exit 1)
	@test -f "$(FILE)" || (echo "file not found: $(FILE)" && exit 1)
	@if [ "$(FORCE)" != "1" ]; then read -r -p "This overwrites the local database. Type RESTORE to continue: " ans; [ "$$ans" = "RESTORE" ] || (echo "aborted" && exit 1); fi
	$(COMPOSE) exec -T postgres pg_restore -U articulate -d articulate --clean --if-exists < "$(FILE)"

seed: ## Create the local user and load content
	cd $(API) && uv run python -m app.cli seed

dev: ## Run api (:8000), worker and web (:3000)
	pnpm dev:all

dev-fake: ## Same as dev with fake AI/speech/pronunciation providers
	$(FAKE_ENV) pnpm dev:all

test: test-api test-web ## Run backend and frontend tests

test-api: ## Backend tests (needs make infra-up)
	cd $(API) && uv run pytest

test-web: ## Frontend unit/component tests
	pnpm --filter web test

test-e2e: ## Playwright journeys on isolated ports and data
	pnpm --filter web e2e

test-live: ## Tests against real Ollama/Deepgram/Azure (costs money for Deepgram/Azure)
	cd $(API) && uv run pytest -m live

lint: ## Lint and type-check both apps
	cd $(API) && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	pnpm --filter web lint
	pnpm --filter web format:check
	pnpm --filter web typecheck

format: ## Format both apps
	cd $(API) && uv run ruff format . && uv run ruff check --fix .
	pnpm --filter web format

gen-client: ## Export OpenAPI and regenerate the TypeScript client types
	cd $(API) && uv run python -m app.scripts.export_openapi openapi.json
	pnpm --filter web exec openapi-typescript ../api/openapi.json -o src/lib/api/schema.ts

check-client: gen-client ## Fail if the generated client is out of date
	git diff --exit-code -- $(API)/openapi.json $(WEB)/src/lib/api/schema.ts

eval: ## Feedback-quality evals on Ollama
	cd $(API) && uv run python -m evals.run --provider ollama --model "$(OLLAMA_MODEL)"

eval-cloud: ## Reference evals: make eval-cloud PROVIDER=anthropic MODEL=<id> CONFIRM=1 (costs money)
	@test -n "$(PROVIDER)" -a -n "$(MODEL)" || (echo "usage: make eval-cloud PROVIDER=<anthropic|openai|google> MODEL=<id> CONFIRM=1" && exit 1)
	@test "$(CONFIRM)" = "1" || (echo "This calls a paid API. Re-run with CONFIRM=1." && exit 1)
	cd $(API) && uv run python -m evals.run --provider "$(PROVIDER)" --model "$(MODEL)"

check: lint check-client test ## Everything that must pass before a commit
