# 0010. Typed API client generated from OpenAPI

- Status: Accepted
- Date: 2026-09-17

## Context
Two languages; request/response drift is a common bug source, especially for AI agents editing
one side.

## Decision
`make gen-client`: export FastAPI OpenAPI to `apps/api/openapi.json` (script, no server needed),
generate `apps/web/src/lib/api/schema.ts` with `openapi-typescript`; call the API with
`openapi-fetch`. Both generated files are committed; `make check-client` fails when stale.

## Consequences
- Backend schema changes are immediately type errors in the frontend.
- SSE and WebSocket payloads are not covered by OpenAPI → their TS types live in
  `src/lib/api/events.ts` and must mirror the docs by hand (tests cover them).

## Alternatives considered
- Hand-written types — drift.
- Orval / hey-api — heavier codegen than needed.
