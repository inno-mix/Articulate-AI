# Phase 10 — Launch-Readiness

> **Milestone:** Q2 (final) · **Depends on:** Phases 8 and 9
> **For agentic workers:** follow `docs/guides/agent-workflow.md`. Tick subtasks as you go.

**Goal:** The app is safe, limited, observable and runnable as a production-like stack on the
owner's machine, with a documented checklist for choosing a host and going live. (Actual
deployment is **not** part of this phase.)

**Architecture:** Per-user rate limits via the Redis limiter; security headers and CSP in Next.js;
security audit; retention jobs; request ids and JSON logs; Dockerfiles + a `full` compose profile
behind Caddy with local HTTPS so production settings (secure cookies, no dev providers) can be
exercised locally.

**Read before starting:** `security-privacy.md` (all), `product-spec.md` §6, `overview.md`,
`local-development.md`, ADR-0002, ADR-0007. Load the `security-auditor` skill for Task 10.2 and
`cicd-builder` only if the owner asks for deployment pipelines (out of scope here).

**Out of scope:** choosing/provisioning a host, DNS, production email provider, billing.

---

## File map

```
apps/api/app/services/limits.py  apps/api/app/core/request_id.py
apps/api/app/worker/tasks/housekeeping.py        (+ usage retention)
apps/api/Dockerfile  apps/web/Dockerfile  .dockerignore
infra/docker-compose.yml                          (profile "full")  infra/Caddyfile
infra/.env.full.example
apps/web/next.config.ts                           (headers, output: "standalone")
apps/web/src/app/privacy/page.tsx
docs/guides/launch-checklist.md
docs/security/<audit-date>-audit.md               (named with the date the audit is written)
apps/api/tests/integration/{test_limits,test_request_id,test_retention}.py
apps/web/tests/security-headers.test.ts
apps/web/e2e/regression.spec.ts                   (smoke of every journey)
```

---

### Task 10.1 — Per-user usage limits

**Goal:** Protect users' keys and the app's Deepgram/Azure budget.
**Files:** `app/services/limits.py`, call sites (chat stream, hint, rewrite, custom draft, drills
LLM calls, feedback/memory tasks count too, voice relay, pronunciation, TTS preview), settings.

Limits (settings with these defaults): `LIMIT_LLM_CALLS_PER_HOUR=60`,
`LIMIT_VOICE_SECONDS_PER_DAY=3600`, `LIMIT_PRONUNCIATION_ATTEMPTS_PER_DAY=200`,
`LIMIT_TTS_PREVIEWS_PER_MINUTE=30`. Exceeding → 429 `rate_limited` with `Retry-After`; voice
relay sends `limit` with reason `daily_voice_limit` (already listed in `voice-and-pronunciation.md`
§2.3) and ends the session gracefully. Background tasks that hit the LLM limit wait and retry later
(Taskiq retry with delay) instead of failing the report.

**Subtasks:**
- [ ] 10.1.1 Failing tests: each limit blocks at N+1 with a correct `Retry-After`; limits are per
  user (another user unaffected); report task retries instead of failing; UI shows the friendly
  message ("You've reached today's voice practice limit. It resets at midnight.") — web test.
- [ ] 10.1.2 Run → FAIL. Implement. Run → PASS. Update docs (`api-contract.md`, `security-privacy.md`
  §2.4, `local-development.md` §5).
- [ ] 10.1.3 Commit: `feat: add per-user usage limits`

---

### Task 10.2 — Security audit and hardening

**Goal:** No known high/critical issues.
**Files:** `docs/security/<audit-date>-audit.md`, fixes across the codebase, `apps/web/next.config.ts`,
`apps/web/tests/security-headers.test.ts`.

**Subtasks:**
- [ ] 10.2.1 Run the `security-auditor` skill over the whole repo (API auth/ownership, CSRF,
  cookies, WebSocket auth, uploads, prompt injection, secrets handling incl. eval keys (S14),
  Deepgram `mip_opt_out` on every request (S13), logging, dependency versions). Write findings
  with severity to the audit doc.
- [ ] 10.2.2 Dependency audits: `cd apps/api && uvx pip-audit` and `pnpm audit --prod`; fix or
  document each finding with a reason.
- [ ] 10.2.3 Security headers in `next.config.ts` `headers()`: `Content-Security-Policy`
  (default-src 'self'; connect-src 'self' + API origin + WS origin; media-src 'self' blob:;
  img-src 'self' data:; frame-ancestors 'none'; script/style per Next.js requirements — check the
  Next.js 16 CSP guide), `X-Content-Type-Options: nosniff`, `Referrer-Policy:
  strict-origin-when-cross-origin`, `Permissions-Policy: microphone=(self), camera=()`. Test that the
  config returns them (unit test on the exported headers function).
- [ ] 10.2.4 API: request body size limit middleware (1.2 MB default; 3.5 MB for drill voice
  upload route), and production values for the request guard's `ALLOWED_HOSTS` and
  `CORS_ORIGINS` (the guard itself exists since Phase 0).
- [ ] 10.2.5 Fix all high/critical findings with tests (TDD per fix); re-run the audit summary.
- [ ] 10.2.6 Commit(s): `fix(security): …` per finding; `docs: add security audit`

---

### Task 10.3 — Retention and deletion guarantees

**Files:** `app/worker/tasks/housekeeping.py`, `tests/integration/test_retention.py`.
- [ ] 10.3.1 Failing tests: `cleanup_usage_events` deletes rows older than 400 days only; the
  account-deletion test from Task 7.4 still enumerates every `user_id` table (add any tables created
  since).
- [ ] 10.3.2 Implement (cron `37 3 * * *`). Run → PASS. Commit: `feat(api): add usage retention job`

---

### Task 10.4 — Observability

**Files:** `app/core/request_id.py`, `app/core/logging.py`, worker logging, web error boundary.
- [ ] 10.4.1 Failing tests: every response has `X-Request-ID` (incoming valid id is reused,
  otherwise generated); log records inside a request include `request_id`; worker task logs include
  `task_name` and `report_id`/`user_id` where relevant; JSON logs when `APP_ENV != development`.
- [ ] 10.4.2 Implement (contextvars + structlog). Web: a root `error.tsx` that shows a friendly
  message with the request id when available. Run → PASS.
- [ ] 10.4.3 Commit: `feat: add request ids and structured logging context`

---

### Task 10.5 — Production-like local stack

**Goal:** `make up-full` runs web, api, worker, scheduler, Postgres, Redis, Mailpit and Caddy
(HTTPS on `https://localhost:8443`) with production settings, using real providers and user keys.
**Files:** `apps/api/Dockerfile`, `apps/web/Dockerfile`, `.dockerignore`,
`infra/docker-compose.yml` (profile `full`), `infra/Caddyfile`, `infra/.env.full.example`,
`Makefile` (`up-full`, `down-full`), `apps/web/next.config.ts` (`output: "standalone"`).

Design:
- API image: multi-stage with `uv` (`uv sync --frozen --no-dev`), non-root user, `uvicorn` with
  `--proxy-headers`; same image runs worker and scheduler with different commands; runs
  `alembic upgrade head` via a one-shot `migrate` service before the API starts.
- Web image: Next.js standalone output, non-root.
- Caddy (`tls internal`): `https://localhost:8443` → `/api/*` and WebSocket upgrades to the API,
  everything else to web — single origin, so `NEXT_PUBLIC_API_URL=https://localhost:8443/api/v1`,
  `CORS_ORIGINS=https://localhost:8443`, `COOKIE_SECURE=true`, `APP_ENV=production`,
  `AUTH_MODE=accounts`, `LLM_PROVIDER=user_credentials`, `LLM_FALLBACK_TO_OLLAMA=false`, real
  Deepgram/Azure, `EMAIL_PROVIDER=smtp` to Mailpit.
- Memory: this stack is heavy for 8 GB — stop `make dev` and Ollama first; set container
  `mem_limit`s; document it.
- The API in this profile listens on the Docker network only (no host port).

**Subtasks:**
- [ ] 10.5.1 Write the Dockerfiles and compose profile; `docker compose --profile full config` valid.
- [ ] 10.5.2 `make up-full` → all services healthy; open `https://localhost:8443` (trust Caddy's
  local CA when prompted — the owner does this, not the agent), register, verify via Mailpit, add a
  real AI key, complete one text session, one voice session, one pronunciation attempt.
- [ ] 10.5.3 Record image sizes, memory use and the smoke results in the completion log.
- [ ] 10.5.4 Commit: `build: add production-like docker stack`

---

### Task 10.6 — Privacy page and launch checklist

**Files:** `apps/web/src/app/privacy/page.tsx`, footer link, `docs/guides/launch-checklist.md`.
- [ ] 10.6.1 Privacy page (plain language; the owner must review the wording): what's stored
  (transcripts, scores, notes; no audio), processors (Deepgram — voice audio, with requests opted
  out of Deepgram's model improvement program; Azure — pronunciation audio; the user's chosen AI
  provider — text), keys encrypted, how to delete the account, contact
  placeholder the owner fills in. Mark clearly "Draft — not legal advice".
- [ ] 10.6.2 `launch-checklist.md`: hosting decision (options to evaluate: AWS as the owner prefers
  — e.g. ECS/Fargate or App Runner + RDS + ElastiCache + SES + Cognito — vs alternatives), secrets
  management, backups (`pg_dump` schedule + restore test), domain + TLS, production email sender
  with SPF/DKIM/DMARC, Deepgram and Azure paid tiers (Azure F0 is dev-only; re-check that the
  Deepgram plan still allows `mip_opt_out` without a price change — ADR-0016), monitoring/alerting,
  cost alerts, incident contacts, data-processing agreements, legal review of privacy/terms,
  Cognito migration plan (swap `TokenVerifier`, migrate users), rollback plan.
- [ ] 10.6.3 Commit: `docs: add privacy page and launch checklist`

---

### Task 10.7 — Final regression and Q2 exit

**Files:** `apps/web/e2e/regression.spec.ts`, `docs/tasks/q2-exit-review.md`.
- [ ] 10.7.1 Regression spec touching every journey quickly (fake providers): auth → onboarding →
  text session + report → voice turn → pronunciation attempt → drill → rewrite → custom scenario →
  progress → add key → usage → delete account.
- [ ] 10.7.2 `make check` and `make test-e2e` → PASS; `make test-live` with the owner's
  permission → PASS; `make eval` for the default provider → recorded.
- [ ] 10.7.3 Write `q2-exit-review.md` (quality bar results, audit status, open follow-ups, known
  limitations, go-live blockers from the checklist). Code review of the Q2 diff; fix blockers.
- [ ] 10.7.4 Update `docs/tasks/README.md`, `AGENTS.md`, `README.md`. Summarise to the owner.
  Commit: `docs: record q2 exit review`

## Phase verification

1. Limits trigger with friendly messages and reset as documented.
2. Audit doc has no open high/critical findings.
3. The production-like stack works end to end over HTTPS with secure cookies and real providers.
4. All tests, E2E, live tests and evals pass or have documented, owner-accepted exceptions.

## Completion log

<!-- Append: - YYYY-MM-DD · Task N.M · commits · evidence · Notes · Follow-ups -->
