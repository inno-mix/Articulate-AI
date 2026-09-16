# Security & Privacy

> Practice transcripts are personal data (they often describe real workplace conflicts).
> Treat them like private messages. Run the `security-auditor` skill in Phase 10.

## 1. Rules that apply from Phase 0

| # | Rule | How it's enforced |
|---|---|---|
| S1 | Secrets live only in `apps/api/.env` (git-ignored). `.env.example` has names + safe defaults, never real values | `.gitignore`; review checklist |
| S2 | Provider keys (Deepgram, Azure, eval keys, user LLM keys) never reach the browser, never appear in logs, errors or API responses | Keys only read inside adapters; the structlog redaction processor masks these field names (case-insensitive, exact name or listed suffix — not any substring): `api_key` and `*_api_key`, `authorization`, `ocp-apim-subscription-key`, `password` and `*_password`, `secret` and `*_secret`, `token`, `access_token`, `refresh_token`, `csrf_token`, `cookie`, `set-cookie`, `encrypted_key`. Fields such as `input_tokens` or `keyterms` stay visible |
| S3 | Every query for user-owned rows filters by `user_id`; "not yours" returns 404 `not_found` | Service functions take `user_id` as a required argument; integration test per resource with a second user (from Phase 7; in Q1 a test creates a second user directly) |
| S4 | API binds to `127.0.0.1` while `AUTH_MODE=local_single_user` | `Makefile` / uvicorn args; `Settings` validator rejects `local_single_user` in production |
| S15 | Other websites open in the same browser can't drive the local API (DNS rebinding, cross-site form posts, cross-site WebSockets) | `RequestGuardMiddleware` (Phase 0): `Host` must be in `ALLOWED_HOSTS` (400 `invalid_host`); unsafe methods and WebSocket handshakes with an `Origin` not in `CORS_ORIGINS` are rejected (403 `origin_not_allowed` / close 4403). Requests without `Origin` (curl, tests) are allowed in Q1 |
| S5 | Fake providers and Ollama are development-only | `Settings` validator |
| S6 | User text sent to an LLM is wrapped in delimiters and treated as data | Prompt templates (see `ai-layer.md` §4) |
| S7 | Scoring runs in a separate LLM call with its own system prompt; role-play output never influences scoring instructions | Feedback worker design |
| S8 | Input limits on every field (length, list sizes, file sizes, audio durations) | Pydantic schemas + WAV validation |
| S9 | No raw audio stored (memory only, discarded after the turn/attempt) | Code review; no audio columns exist |
| S10 | Crisis content → fixed supportive message, session flagged | `app/services/safety.py` |
| S11 | Dependencies pinned via lock files (`uv.lock`, `pnpm-lock.yaml`) | Committed lock files |
| S12 | Logs never contain full transcripts; log ids and lengths instead | Logging convention |
| S13 | Every Deepgram request (streaming STT, pre-recorded STT, TTS WebSocket, TTS REST) sets `mip_opt_out=true` so audio/text isn't used for Deepgram model training (ADR-0016) | Shared options helper in `app/voice/deepgram_common.py`; adapter unit tests assert the flag on every request type |
| S14 | Eval keys (`EVAL_ANTHROPIC_API_KEY`, `EVAL_OPENAI_API_KEY`, `EVAL_GOOGLE_API_KEY`) are development-only secrets used by `evals/` and live tests, never by the app runtime (ADR-0015) | `Settings` rejects them when `APP_ENV=production`; unit test proves `get_llm_service` ignores them; same redaction rules as S2 |

### Safety message (S10)
`app/services/safety.py`:
- `detect_crisis(text: str) -> bool` — case-insensitive phrase list (e.g. "kill myself",
  "end my life", "suicide", "self harm", "hurt myself", "don't want to live"). Keep the list in
  `app/domain/safety_phrases.py`. Unit-test positives and near-miss negatives
  ("kill the process", "this bug is killing me").
- Fixed reply (source `system`): "I'm stepping out of the practice for a moment. It sounds like you
  might be going through something hard. If you're in danger or thinking about harming yourself,
  please contact local emergency services or a crisis line in your country right away. You can end
  this practice session any time."

## 2. Q2 additions

### 2.1 Passwords & sessions (Phase 7)
- Hashing: `pwdlib` with Argon2id (library defaults). Password 12–128 chars; reject if it equals
  the email.
- Access token: JWT (HS256, `JWT_SECRET` ≥ 32 random bytes), 15 min, claims `sub`, `iat`, `exp`,
  `typ="access"`. Cookie `access_token`: `HttpOnly; SameSite=Lax; Path=/; Secure` when
  `COOKIE_SECURE=true` (false only for http localhost).
- Refresh token: 32 random bytes (base64url), stored as sha256 in `auth_tokens`, 30 days,
  rotated on every use; reuse of an already-used token revokes the whole family. Cookie
  `refresh_token`: `HttpOnly; SameSite=Strict; Path=/api/v1/auth`.
- CSRF (double submit): cookie `csrf_token` (not HttpOnly, random) + header `X-CSRF-Token` on
  POST/PUT/PATCH/DELETE; plus `Origin` header must be in `CORS_ORIGINS`. Exempt: `/auth/login`,
  `/auth/register`, `/auth/forgot-password`, `/auth/reset-password`, `/emails/unsubscribe`
  (these check `Origin` only, and unsubscribe relies on its signed token).
- WebSocket: cookie auth on handshake + `Origin` check.
- Verification / reset tokens: 32 random bytes, sha256 stored, single use, 24 h / 1 h.
- Login rate limit: 5 attempts / 15 min per (IP, email) and 20 / 15 min per IP (Redis fixed window).
- Generic responses: login failure and forgot-password never reveal whether an email exists.
- Future Cognito swap: all of this sits behind `app/auth/` with a `TokenVerifier` Protocol used by
  `get_current_user`; routers never parse tokens themselves.

### 2.2 Email (Phase 8)
- Unsubscribe token: `itsdangerous.URLSafeTimedSerializer(EMAIL_TOKEN_SECRET)` over
  `{user_id, kind}`; valid 90 days.
- Headers: `List-Unsubscribe` + `List-Unsubscribe-Post: List-Unsubscribe=One-Click`.
- Emails never include transcript content — only counts, scores and links.

### 2.3 User LLM keys (Phase 9)
- AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`), random 12-byte nonce per
  encryption, associated data = `f"{user_id}:{provider}"`.
- Master keys: `ENCRYPTION_KEYS` = comma-separated `version:base64key` (32 bytes each);
  `ENCRYPTION_ACTIVE_KEY_VERSION` selects the one for new writes. Rotation = add a new version,
  re-encrypt with `app.cli rotate-llm-keys`. Later: AWS KMS envelope encryption.
- Decrypt only inside `app/llm/factory.py`, immediately before building the provider object; never
  cache plaintext beyond the request.
- API returns only `key_last4`.
- Provider errors are mapped to our codes; raw provider error bodies are logged with the key
  redacted, never returned.

### 2.4 Launch-readiness (Phase 10)
- Per-user limits: 60 LLM calls/hour, 60 voice minutes/day, 200 pronunciation attempts/day
  (configurable).
- Security headers on the web app (CSP, `X-Content-Type-Options`, `Referrer-Policy`,
  `Permissions-Policy: microphone=(self)`).
- `pip-audit` and `pnpm audit` clean (or documented exceptions).
- Account deletion verified to remove every row (integration test enumerates all tables).
- Privacy notice page listing processors: Deepgram (audio; requests opted out of Deepgram's model
  improvement program), Azure (audio), the user's chosen LLM provider (text).

## 3. Data retention

| Data | Retention |
|---|---|
| Raw audio | Never stored |
| Transcripts, reports, scores, notes | Until the user deletes the session/account |
| `usage_events` | 400 days (cleanup job in Phase 10) |
| `auth_tokens` | Deleted 7 days after expiry (cleanup job in Phase 8) |
| `email_deliveries` | 90 days (cleanup job in Phase 8) |
