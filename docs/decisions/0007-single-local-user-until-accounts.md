# 0007. Single built-in local user until accounts exist

- Status: Accepted
- Date: 2026-09-17

## Context
The owner moved accounts and onboarding to Q2 to prioritise core features, but every feature
stores per-user data.

## Decision
- `AUTH_MODE=local_single_user`: `get_current_user` returns the seeded user
  `00000000-0000-0000-0000-000000000001` (`is_local=true`).
- All tables and service functions are still user-scoped from day one.
- The API binds to `127.0.0.1` in this mode; the mode is rejected in production.
- Phase 7 switches to `AUTH_MODE=accounts` and adds `app.cli claim-local-data --email <email>`
  to move the local user's rows to a real account.

## Consequences
- No auth code in Q1; ownership tests still use a second user created in fixtures.
- Profile editing lives in Settings during Q1 (the onboarding wizard arrives in Phase 7).

## Alternatives considered
- Build auth first — delays core value; rejected by owner.
- No user concept in Q1 — would force a painful schema migration later.
