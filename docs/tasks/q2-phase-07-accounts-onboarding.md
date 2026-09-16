# Phase 7 — Accounts, Onboarding & Profile

> **Milestone:** Q2 · **Depends on:** Q1 exit review done
> **For agentic workers:** follow `docs/guides/agent-workflow.md`. Tick subtasks as you go.

**Goal:** Real multi-user accounts — register, verify email, log in/out, refresh, reset password,
delete account — plus the onboarding wizard and the profile screen with timezone detection (moved
here from Q1 by owner decision D22), while keeping the auth code swappable for AWS (e.g. Cognito)
later.

**Architecture:** `app/auth/` package: Argon2 password hashing, short-lived JWT access cookie,
rotating opaque refresh token (hashed in `auth_tokens`), double-submit CSRF, Redis rate limiting,
`TokenVerifier` Protocol behind `get_current_user`. Transactional emails via an `EmailSender`
Protocol (SMTP → Mailpit locally) sent by a worker task. Next.js pages for auth + onboarding, and
`proxy.ts` for route protection.

**Read before starting:** `product-spec.md` F12–F13 and D22, `security-privacy.md` §2.1 (every line),
`api-contract.md` §1 (Auth), §3 (Auth), `data-model.md` (`auth_tokens`, `email_deliveries`,
`users`, `profiles.onboarding_completed_at`), ADR-0007. Context7: `pwdlib`, `PyJWT`,
`aiosmtplib`, FastAPI security/cookies, Next.js 16 `proxy.ts`, Mailpit API (for E2E).

**Out of scope:** reminder/summary emails (Phase 8), social login, MFA, Cognito.

---

## File map

```
apps/api/app/auth/{__init__,passwords,tokens,cookies,csrf,verifier,rate_limit,service}.py
apps/api/app/models/auth.py                          (AuthToken, EmailDelivery)
apps/api/migrations/versions/0010_auth_tokens_email_deliveries.py
apps/api/app/email/{__init__,base,smtp,fake,render}.py
apps/api/app/email/templates/{verify_email,password_reset}.{html,txt}.j2
apps/api/app/worker/tasks/email.py
apps/api/app/schemas/auth.py  apps/api/app/schemas/onboarding.py
apps/api/app/services/{account,onboarding}.py
apps/api/app/api/v1/{auth,onboarding}.py  apps/api/app/api/v1/me.py (DELETE /me)
apps/api/app/deps.py                                  (accounts mode)
apps/api/app/core/config.py                           (+ JWT/cookie/SMTP settings)
apps/api/app/cli.py                                   (+ claim-local-data)
apps/api/app/voice/relay.py / api/v1/voice.py         (cookie + Origin auth)
apps/api/tests/unit/auth/{test_passwords,test_tokens,test_csrf,test_rate_limit}.py
apps/api/tests/unit/email/test_render.py
apps/api/tests/integration/api/{test_auth,test_auth_required,test_onboarding,test_delete_account}.py
apps/api/tests/integration/test_claim_local_data.py
apps/web/src/proxy.ts
apps/web/src/lib/api/{client,csrf}.ts                 (modify/create)
apps/web/src/features/auth/*  apps/web/src/features/onboarding/*
apps/web/src/app/(auth)/{login,register,verify-email,forgot-password,reset-password}/page.tsx
apps/web/src/app/onboarding/page.tsx
apps/web/src/features/settings/components/profile-section.tsx  apps/web/src/features/settings/hooks/use-timezone-check.ts
apps/web/src/components/timezone-banner.tsx  apps/web/src/lib/timezones.ts
apps/web/tests/features/settings/{profile-section,timezone-banner}.test.tsx
apps/web/tests/features/{auth,onboarding}/*.test.tsx
apps/web/e2e/auth.spec.ts  apps/web/e2e/fixtures/auth.ts   (login helper for all other specs)
```

---

### Task 7.1 — Auth primitives

**Goal:** Pure/unit-tested building blocks.
**Files:** `app/auth/{passwords,tokens,cookies,csrf,rate_limit,verifier}.py`, `app/core/config.py`,
`app/models/auth.py` + migration `0010_auth_tokens_email_deliveries`. Add deps: `uv add "pwdlib[argon2]" pyjwt`.
Tests `tests/unit/auth/*`.

**Interfaces (produces):**
```python
# passwords.py
def hash_password(plain: str) -> str
def verify_password(plain: str, hashed: str) -> tuple[bool, str | None]   # (ok, updated_hash_if_rehash_needed)
def validate_password_policy(password: str, email: str) -> None           # 12..128 chars, != email → ValidationAppError

# tokens.py
def create_access_token(user_id: UUID, *, secret: str, now: datetime, ttl: timedelta = timedelta(minutes=15)) -> str
def decode_access_token(token: str, *, secret: str, now: datetime) -> UUID                     # raises UnauthorizedError
def new_opaque_token() -> tuple[str, str]                                                     # (plain, sha256 hex)
def hash_opaque_token(plain: str) -> str

# verifier.py
class TokenVerifier(Protocol):
    async def verify(self, request: Request) -> UUID     # user id or raises UnauthorizedError
class LocalJwtVerifier: ...                               # reads the access_token cookie

# cookies.py
def set_auth_cookies(response: Response, *, access: str, refresh: str, settings: Settings) -> None
def clear_auth_cookies(response: Response, settings: Settings) -> None
def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None

# csrf.py
class CSRFMiddleware:     # pure ASGI middleware; enforces rules in security-privacy.md §2.1 when AUTH_MODE=accounts

# rate_limit.py
async def hit(redis: Redis, key: str, *, limit: int, window_s: int) -> RateLimitResult   # fixed window (INCR + EXPIRE NX)
# RateLimitResult(allowed: bool, retry_after_s: int)
```
New settings: `jwt_secret: SecretStr | None`, `cookie_secure: bool = False`, `smtp_host`,
`smtp_port`, `smtp_username`, `smtp_password: SecretStr | None`, `email_from`. Validator:
`AUTH_MODE=accounts` requires `jwt_secret` (≥ 32 chars); production requires
`cookie_secure=True`.
New errors: `UnauthorizedError` (401 `unauthorized`), `InvalidCredentialsError` (401),
`EmailTakenError` (409), `InvalidTokenError` (400), `EmailNotVerifiedError` (403),
`CsrfFailedError` (403), `RateLimitedError` (429, sets `Retry-After`).

**Subtasks:**
- [ ] 7.1.1 Failing tests: hash/verify round trip, wrong password, policy rules; access token
  round trip, expired → 401, tampered → 401, wrong `typ` → 401; opaque token hash stable;
  CSRF: safe methods pass, unsafe without header → 403, mismatched → 403, matching → pass,
  exempt paths only check Origin, bad Origin → 403, `local_single_user` mode bypasses;
  rate limiter allows `limit` hits then blocks with `retry_after_s > 0` (Redis db 1);
  settings validators.
- [ ] 7.1.2 Run → FAIL. Implement (+ migration, reviewed). Run → PASS.
- [ ] 7.1.3 Commit: `feat(api): add auth primitives`

---

### Task 7.2 — Email infrastructure

**Goal:** Send templated emails through a worker task; Mailpit locally.
**Files:** `app/email/*`, `app/worker/tasks/email.py`, Makefile `infra-up-mail`,
`app/deps.py`. Add `uv add aiosmtplib`. Tests `tests/unit/email/test_render.py`,
`tests/integration/worker/test_email_task.py`.

**Interfaces (produces):**
```python
@dataclass(frozen=True)
class EmailMessage: to: str; subject: str; html: str; text: str; headers: dict[str, str] = field(default_factory=dict)
class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None      # raises EmailSendError
class SmtpEmailSender: ...      # aiosmtplib; STARTTLS only when not localhost:1025
class FakeEmailSender: sent: list[EmailMessage]
def render_email(template: str, **context: Any) -> tuple[str, str]      # (html, text); StrictUndefined; autoescape html
@broker.task(task_name="send_email")
async def send_email(user_id: str, kind: str, dedupe_key: str, template: str, subject: str, context: dict[str, Any]) -> None
    # skip if email_deliveries has dedupe_key; send; insert delivery (sent|failed + error)
```
`EMAIL_PROVIDER` setting: `smtp` | `fake` (fake forbidden in production); add to
`local-development.md` §5.
Templates: plain, accessible HTML (single column, readable without images) + text version;
product name, short message, one primary button link, footer "You're receiving this because you
created an Articulate AI account."

**Subtasks:**
- [ ] 7.2.1 Failing tests: templates render both parts with the link; missing variable raises;
  HTML escapes user-provided names; task dedupes by key; send failure records `failed` and doesn't
  raise.
- [ ] 7.2.2 Run → FAIL. Implement. Run → PASS. Manual: `make infra-up-mail`, enqueue a test
  email from a shell, see it at http://localhost:8025.
- [ ] 7.2.3 Commit: `feat(api): add email sending via worker`

---

### Task 7.3 — Auth endpoints and accounts mode

**Goal:** All `/auth/*` endpoints; `get_current_user` in accounts mode; every protected endpoint
requires login.
**Depends on:** 7.1, 7.2
**Files:** `app/auth/service.py`, `app/schemas/auth.py`, `app/api/v1/auth.py`, `app/deps.py`,
`app/main.py` (CSRF middleware), `app/api/v1/voice.py` (cookie + Origin on handshake).
Tests `tests/integration/api/{test_auth,test_auth_required}.py`, extend `test_voice_ws.py`.

**Interfaces (produces):**
```python
async def register(db, redis, data: RegisterIn, settings) -> tuple[User, IssuedTokens]
    # lower-case email; policy; create user+profile+settings; issue tokens; enqueue verify email
async def login(db, redis, data: LoginIn, ip: str, settings) -> tuple[User, IssuedTokens]   # rate limited
async def refresh(db, refresh_plain: str, settings) -> IssuedTokens    # rotation + reuse detection
async def logout(db, refresh_plain: str | None) -> None
async def verify_email(db, token_plain: str) -> User
async def resend_verification(db, redis, user: User, settings) -> None  # 3/hour
async def forgot_password(db, redis, email: str, settings) -> None       # always silent
async def reset_password(db, token_plain: str, new_password: str) -> None   # revokes all refresh tokens
```
`get_current_user` (accounts mode): `TokenVerifier.verify` → load user with profile/settings →
401 if missing. Auth routes, `/health`, `/emails/unsubscribe` (Phase 8) and `/auth/csrf` are
public; everything else requires a user. Add a test that walks `app.routes` and asserts every
non-public route returns 401 without cookies (so new routes can't forget auth).

**Subtasks:**
- [ ] 7.3.1 Failing tests (`AUTH_MODE=accounts` fixture variant `accounts_app`/`accounts_client`
  with a `login(client, user)` helper):
  register → 201 + cookies + verification email in `FakeEmailSender`; duplicate email → 409;
  weak password → 422; login ok; wrong password and unknown email return identical 401 bodies;
  6th login attempt in 15 min → 429 with `Retry-After`; refresh rotates (old token then fails and
  revokes the family); logout clears cookies and revokes; verify-email ok / reused / expired →
  400; resend limited to 3/hour; forgot-password always 202 and only sends for existing emails;
  reset-password ok → old refresh tokens revoked, login with new password works; CSRF enforced on
  a protected POST; route-walk test (401 everywhere non-public); WebSocket without cookie → close
  4401; bad Origin → 4403.
- [ ] 7.3.2 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 7.3.3 Commit: `feat(api): add account endpoints and require login`

**Pitfalls:** all existing integration tests used `local_single_user`; keep that fixture as the
default for feature tests and add the accounts variant — don't rewrite every test. Cookie
`Secure` must be off for `http://localhost`.

---

### Task 7.4 — Onboarding, account deletion, local data migration

**Goal:** `POST /onboarding`, `DELETE /me`, `app.cli claim-local-data`.
**Depends on:** 7.3
**Files:** `app/services/{onboarding,account}.py`, `app/schemas/onboarding.py`,
`app/api/v1/{onboarding,me}.py`, `app/cli.py`. Tests
`tests/integration/api/{test_onboarding,test_delete_account}.py`,
`tests/integration/test_claim_local_data.py`.

**Interfaces (produces):**
```python
async def complete_onboarding(db, user_id, data: OnboardingIn) -> ProfileOut
async def delete_account(db, user: User, password: str) -> None      # verify password; delete user (cascade)
async def claim_local_data(db, *, email: str) -> ClaimReport
    # moves every user-owned row from LOCAL_USER_ID to the account with `email` (must exist, must have no
    # sessions yet); copies profile/settings; deletes the local user; refuses in production
```
`MeOut` gains `onboarding_completed: bool`.

**Subtasks:**
- [ ] 7.4.1 Failing tests: onboarding validation + sets `onboarding_completed_at`; delete with wrong
  password → 401 `invalid_credentials`; delete removes every user-owned row (query each table with
  a `user_id` column via SQLAlchemy metadata — the test must fail if a new table is forgotten);
  claim moves sessions/reports/scores/notes/drills/attempts/rewrites/usage and refuses when the
  target already has data.
- [ ] 7.4.2 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 7.4.3 Commit: `feat(api): add onboarding, account deletion and local data claim`

---

### Task 7.5 — Web: auth pages, CSRF, route protection

**Goal:** Users can register, verify, log in, reset passwords and log out in the browser.
**Depends on:** 7.3
**Files:** `src/proxy.ts`, `src/lib/api/{client,csrf}.ts`, `src/features/auth/*`,
`src/app/(auth)/*`, app shell user menu. Tests `tests/features/auth/*.test.tsx`,
`tests/lib/api/client-auth.test.ts`.

**Behaviour:**
- On app load the client calls `GET /auth/csrf` once and adds `X-CSRF-Token` to unsafe requests
  (openapi-fetch middleware).
- A 401 on any request triggers one `POST /auth/refresh` (single-flight) and retries once; if that
  fails → redirect to `/login?next=<path>`.
- `proxy.ts`: for app routes, if neither `access_token` nor `refresh_token` cookie exists →
  redirect to `/login?next=…`; auth pages redirect to `/` when an access cookie exists. (The API is
  still the real authority.)
- Pages: login (email, password, "Forgot password?"); register (display name, email, password
  with strength hint and rules); "Check your email" screen with resend; verify-email (reads
  `?token=`, shows success/failure); forgot-password (always shows the same confirmation);
  reset-password (new password twice). Clear, generic error texts.
- Shell: user menu with display name, "Settings", "Log out". Banner "Verify your email to turn on
  reminders" when unverified (Phase 8 uses it).
- Settings → "Delete account" (password confirmation dialog; explains that everything is deleted).

**Subtasks:**
- [ ] 7.5.1 Failing tests: CSRF header added only to unsafe methods; refresh single-flight with two
  concurrent 401s; redirect after failed refresh keeps `next`; each form's validation and error
  mapping; logout clears query cache and navigates to `/login`; delete account flow.
- [ ] 7.5.2 Run → FAIL. Implement. Run → PASS. `make lint`.
- [ ] 7.5.3 Commit: `feat(web): add authentication pages and route protection`

---

### Task 7.6 — Web: onboarding wizard

**Goal:** New users complete a 4-step onboarding before using the app.
**Depends on:** 7.4, 7.5
**Files:** `src/features/onboarding/*`, `src/app/onboarding/page.tsx`; app layout redirects to
`/onboarding` when `me.onboarding_completed` is false (client-side guard).

**Behaviour:** step 1 role & seniority; step 2 English level (CEFR descriptions) + native language;
step 3 goals + up to 3 focus areas + timezone (detected); step 4 "Take your baseline now (10 min)"
→ `/assessment` or "Skip for now" → dashboard. Back/Next buttons, progress indicator, state kept
if the user goes back.

**Subtasks:**
- [ ] 7.6.1 Failing tests: step validation; back keeps values; submit payload; guard redirects
  unfinished users; finished users can't reach `/onboarding` (redirect to `/`).
- [ ] 7.6.2 Run → FAIL. Implement. Run → PASS. Commit: `feat(web): add onboarding wizard`

---

### Task 7.7 — Web: profile settings and timezone detection

**Goal:** Users edit their profile in Settings, and the app keeps their timezone correct (owner
decision D22 — this was deliberately left out of Q1).
**Depends on:** 7.6
**Read before starting:** `product-spec.md` F12–F13, `api-contract.md` §2 (Me / profile),
`data-model.md` (`profiles`).
**Files:** `src/features/settings/components/profile-section.tsx`,
`src/features/settings/hooks/use-timezone-check.ts`, `src/components/timezone-banner.tsx`,
`src/lib/timezones.ts`; settings page (add the Profile section first); app layout (banner).
Tests `tests/features/settings/profile-section.test.tsx`,
`tests/features/settings/timezone-banner.test.tsx`.

**Interfaces (produces):**
```ts
// src/lib/timezones.ts
export function detectTimezone(): string | null          // Intl.DateTimeFormat().resolvedOptions().timeZone, null if unavailable
export function listTimezones(): string[]                 // Intl.supportedValuesOf("timeZone") with a static fallback list
// src/features/settings/hooks/use-timezone-check.ts
export function useTimezoneCheck(): { mismatch: { saved: string; detected: string } | null;
  update(): Promise<void>; dismiss(): void }              // dismissal stored per detected zone (localStorage, try/catch)
```

**Behaviour:**
- Settings → **Profile** section: display name, seniority, native language, English level (with
  one-line CEFR explanations), goals (checkboxes), focus areas (max 3), timezone (searchable
  select + "Use my current timezone" button). Save with a toast; field errors from
  `validation_error.details.fields`.
- Timezone banner (logged-in pages): when the detected browser timezone differs from the saved one:
  "Your timezone looks like Asia/Manila. Update it so streaks and reminders use your local day?"
  [Update] [Not now]. "Not now" hides it for that detected zone.
- A changed English level applies from the next practice session's prompts.

**Subtasks:**
- [ ] 7.7.1 Failing tests: profile section loads values; partial PATCH on save; field errors shown;
  max 3 focus areas enforced; "Use my current timezone" fills the detected zone; banner shown only
  on mismatch; "Update" sends `PATCH /me/profile` with the detected zone and hides the banner;
  "Not now" hides it for that zone only; storage errors don't break the page.
- [ ] 7.7.2 Run → FAIL. Implement. Run → PASS. `make lint`.
- [ ] 7.7.3 Browser check: change timezone → dashboard "practised today" and streak reflect the new
  local day. Commit: `feat(web): add profile settings and timezone detection`

**Acceptance criteria:**
- [ ] Profile edits persist and are validated.
- [ ] The timezone banner appears only on a mismatch and respects "Not now".

---

### Task 7.8 — Switch defaults, E2E, docs

**Goal:** Accounts mode becomes the default for development; all E2E specs log in.
**Depends on:** 7.7
**Files:** `.env.example` (`AUTH_MODE=accounts`, `JWT_SECRET` placeholder with generation hint,
SMTP vars), `Makefile` (`dev` starts Mailpit; `dev-fake` sets `EMAIL_PROVIDER=fake`),
`playwright.config.ts`, `e2e/fixtures/auth.ts`, `e2e/auth.spec.ts`, all existing specs (use the
login fixture), `docs/guides/local-development.md`, `AGENTS.md`, `README.md`.

**Subtasks:**
- [ ] 7.8.1 E2E login fixture: registers a unique user through the API, verifies it directly via a
  test-only CLI (`uv run python -m app.cli verify-email --email …`, refuses outside
  development/test), stores cookies in `storageState`.
- [ ] 7.8.2 `auth.spec.ts` (runs with real SMTP to Mailpit): register → read the verification email
  via Mailpit's HTTP API → open the link → onboarding → dashboard → Settings → change English level
  → reload → value persists → log out → log in → forgot password → reset via emailed link → log in
  with the new password.
- [ ] 7.8.3 Update all other specs to use the fixture (each spec gets its own user, so
  `workers` may now be raised above 1 if memory allows); `make test-e2e` → PASS.
- [ ] 7.8.4 Run `uv run python -m app.cli claim-local-data --email <owner's email>` **only if the
  owner asks** (it moves their Q1 practice history into their new account).
- [ ] 7.8.5 Update docs and phase status. Commit: `chore: make accounts mode the default`

## Phase verification

1. Register a new account in the browser; the email arrives in Mailpit; verification works.
2. Two browsers with two accounts can't see each other's sessions, reports, notes or attempts
   (spot-check URLs with the other user's ids → 404).
3. Access token expiry (temporarily set TTL to 1 minute) → the app refreshes silently.
4. Refresh-token reuse (replay an old cookie with curl) → family revoked; next request redirects
   to login.
5. Delete account → all rows gone (SQL check).
6. `make check` and `make test-e2e` → PASS.

## Completion log

<!-- Append: - YYYY-MM-DD · Task N.M · commits · evidence · Notes · Follow-ups -->
