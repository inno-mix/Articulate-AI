# 0001. Next.js frontend + FastAPI backend

- Status: Accepted
- Date: 2026-09-17

## Context
The owner wants a Next.js UI and a Python backend. Speech/AI tooling is strong in Python, and the
backend must hold WebSockets, background jobs and provider SDKs.

## Decision
- `apps/web`: Next.js 16 (App Router) — UI only, no business logic, no secrets.
- `apps/api`: FastAPI — all business logic, persistence, provider calls, WebSockets.
- The browser calls the API directly (CORS allowlist, `credentials: "include"`).

## Consequences
- Two toolchains (pnpm + uv) — unified by the root `Makefile`.
- Types cross the boundary via generated OpenAPI types (ADR-0010).
- Next.js route handlers/server actions are not used for business logic.

## Alternatives considered
- Next.js full-stack only (AI SDK in route handlers) — rejected by owner preference for Python backend.
- Next.js rewrites proxying `/api` to FastAPI — unnecessary: localhost ports are same-site for
  cookies, and WebSocket proxying through the dev server is unreliable.
