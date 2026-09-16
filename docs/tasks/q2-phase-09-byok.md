# Phase 9 — Bring Your Own AI Key

> **Milestone:** Q2 · **Depends on:** Phase 7
> **For agentic workers:** follow `docs/guides/agent-workflow.md`. Tick subtasks as you go.
> **Cost note:** live tests and evals in this phase use the owner's own Anthropic/OpenAI/Gemini keys
> and cost money — ask before running them.

**Goal:** Each user can add an Anthropic, OpenAI or Gemini API key, pick a model, and all AI
features use it. Keys are encrypted at rest, validated on save, never shown again (last 4 chars
only). Users see their usage. In production a user without a key is asked to add one; in
development Ollama is the fallback.

**Architecture:** AES-256-GCM with versioned master keys (`app/crypto.py`). `llm_credentials`
table. Provider validators call cheap "list models" endpoints. `get_llm_service` builds a
per-request Pydantic AI model from the decrypted key (`LLM_PROVIDER=user_credentials`). Model
allowlist in YAML. Web settings section for keys + usage page.

**Read before starting:** `product-spec.md` F15, `ai-layer.md` §1–2, §8–9,
`security-privacy.md` §2.3, `data-model.md` (`llm_credentials`, `usage_events`),
`api-contract.md` §3 (AI keys & usage), ADR-0002, ADR-0008. Context7: Pydantic AI v2
(`AnthropicModel`/`AnthropicProvider`, `OpenAIChatModel`/`OpenAIProvider`,
`GoogleModel`/`GoogleProvider`, error classes), `cryptography` AESGCM; provider docs for the
list-models endpoints and current model ids.

**Out of scope:** app-owned cloud keys, per-user Deepgram/Azure keys (revisit after this phase —
see spec D14), billing.

---

## File map

```
apps/api/app/crypto.py
apps/api/app/models/credentials.py
apps/api/migrations/versions/0011_llm_credentials.py
apps/api/app/llm/model_allowlist.yaml  apps/api/app/llm/allowlist.py
apps/api/app/llm/validators.py
apps/api/app/llm/providers.py                     (exists since Phase 2 — reused, not rewritten)
apps/api/app/llm/factory.py                       (user_credentials mode)
apps/api/app/services/{credentials,usage_report}.py
apps/api/app/schemas/{credentials,usage}.py
apps/api/app/api/v1/{credentials,usage}.py
apps/api/app/cli.py                               (+ rotate-llm-keys)
apps/api/app/core/config.py                       (+ ENCRYPTION_*, LLM_KEY_VALIDATION, LLM_FALLBACK_TO_OLLAMA, FAKE_PROVIDER_MODELS)
apps/api/evals/run.py                             (already supports cloud providers since Phase 2)
apps/api/tests/unit/{test_crypto,llm/test_allowlist,llm/test_validators}.py
apps/api/tests/integration/api/{test_credentials,test_usage}.py
apps/api/tests/integration/llm/test_factory_user_credentials.py
apps/api/tests/live/test_user_providers_live.py
apps/web/src/features/ai-keys/*  apps/web/src/features/usage/*
apps/web/src/app/settings/page.tsx                (AI keys section)  apps/web/src/app/usage/page.tsx
apps/web/src/components/llm-not-configured-banner.tsx
apps/web/tests/features/{ai-keys,usage}/*.test.tsx
apps/web/e2e/byok.spec.ts
```

---

### Task 9.1 — Encryption module and key rotation

**Files:** `app/crypto.py`, `app/core/config.py`, `app/cli.py` (`rotate-llm-keys`).
Tests `tests/unit/test_crypto.py`.

**Interfaces (produces):**
```python
@dataclass(frozen=True)
class EncryptedValue: ciphertext: bytes; nonce: bytes; key_version: int
class KeyRing:
    def __init__(self, keys: dict[int, bytes], active_version: int) -> None   # each key 32 bytes
    @classmethod
    def from_settings(cls, settings: Settings) -> "KeyRing"                    # parses "1:<b64>,2:<b64>"
    def encrypt(self, plaintext: str, *, associated_data: bytes) -> EncryptedValue
    def decrypt(self, value: EncryptedValue, *, associated_data: bytes) -> str  # raises DecryptionError
```
Settings validation: `LLM_PROVIDER=user_credentials` requires valid `ENCRYPTION_KEYS` and
`ENCRYPTION_ACTIVE_KEY_VERSION` present in them. Also add `LLM_KEY_VALIDATION`,
`LLM_FALLBACK_TO_OLLAMA` and `FAKE_PROVIDER_MODELS` to `Settings` with the rules in
`local-development.md` §5 (fake/test-only values rejected in production).

**Subtasks:**
- [ ] 9.1.1 Failing tests: round trip; different nonce each time; wrong associated data → error;
  tampered ciphertext → error; unknown key version → error; parsing errors (bad base64, wrong
  length, active version missing); decrypt with an old version after rotation works.
- [ ] 9.1.2 Run → FAIL. `uv add cryptography` (declare it directly even if it's already a
  transitive dependency). Implement. Run → PASS.
- [ ] 9.1.3 Commit: `feat(api): add versioned aes-gcm key ring`

---

### Task 9.2 — Allowlist and key validators

**Files:** `app/llm/{model_allowlist.yaml,allowlist,validators}.py`. `app/llm/providers.py`
(`build_model`) and the provider extras already exist from Task 2.5 — reuse them. Tests
`tests/unit/llm/{test_allowlist,test_validators}.py`.

**Allowlist format** (verify **every** model id against the provider's current documentation at
implementation time; remove ids that don't exist; prefer each provider's current general-purpose
and fast/cheap models):
```yaml
anthropic:
  default: claude-sonnet-5
  models:
    - { id: claude-sonnet-5, label: "Claude Sonnet 5 (recommended)" }
    - { id: claude-haiku-4-5-20251001, label: "Claude Haiku 4.5 (faster, cheaper)" }
    - { id: claude-opus-5, label: "Claude Opus 5 (most capable)" }
openai:
  default: <verify>
  models: [ ... ]        # look up current ids
google:
  default: <verify>
  models: [ ... ]        # look up current ids
```
(The `<verify>` markers must be replaced with real ids before this task is committed — a unit test
fails if any id is `<verify>` or empty.)

**Interfaces (produces):**
```python
# allowlist.py
def get_allowlist() -> dict[Provider, ProviderModels]
def is_allowed(provider: Provider, model: str) -> bool
# validators.py
class KeyValidator(Protocol):
    async def validate(self, provider: Provider, api_key: str) -> None    # raises LLMAuthError / LLMRateLimitedError / LLMUnavailableError
class HttpKeyValidator:  # uses each provider's list-models endpoint (no token cost); timeout 10 s; httpx
class FakeKeyValidator:  # accepts keys starting with "test-", rejects others with LLMAuthError
# providers.py — consumed, not produced (Task 2.5)
def build_model(provider: Provider, model: str, api_key: str) -> tuple[Model, OutputMode]
```
Look up the exact list-models endpoints and auth headers for each provider (Anthropic
`x-api-key` + `anthropic-version`; OpenAI `Authorization: Bearer`; Gemini API key header) and
record them in a docstring with the doc URL.

**Subtasks:**
- [ ] 9.2.1 Failing tests: allowlist loads, defaults are members, no placeholder ids; validators
  (respx): 200 → ok; 401/403 → `LLMAuthError`; 429 → rate limited; 5xx/timeout → unavailable;
  the key never appears in raised messages or logs (capture logs); the allowlist includes the
  reference model recorded in ADR-0012 if that provider is offered.
- [ ] 9.2.2 Run → FAIL. Implement. Run → PASS.
- [ ] 9.2.3 Commit: `feat(api): add llm provider allowlist and key validation`

---

### Task 9.3 — Credentials and usage APIs

**Files:** `app/models/credentials.py` + migration `0011_llm_credentials`, `app/services/{credentials,usage_report}.py`,
`app/schemas/{credentials,usage}.py`, `app/api/v1/{credentials,usage}.py`, `app/deps.py`
(`get_key_validator`, `get_key_ring`). Tests `tests/integration/api/{test_credentials,test_usage}.py`.

**Interfaces (produces):**
```python
async def list_credentials(db, user_id) -> list[CredentialOut]
async def upsert_credential(db, user_id, provider, api_key: str, model: str,
                            validator: KeyValidator, ring: KeyRing) -> CredentialOut
    # model must be allowed (422); validate key (400 llm_auth_failed); encrypt with AD f"{user_id}:{provider}";
    # key_last4 = api_key[-4:]; validated_at = now; first credential becomes active automatically
async def activate_credential(db, user_id, provider) -> CredentialOut   # sets others inactive (single tx)
async def delete_credential(db, user_id, provider) -> None              # if it was active, no active remains
async def get_usage(db, user_id, range_days: Literal[7, 30]) -> UsageOut   # daily sums per kind, user's timezone
```
`api_key` input: 20–300 chars, stripped; never logged (add the field name to the redaction list if
not covered).

**Subtasks:**
- [ ] 9.3.1 Failing tests: PUT with fake validator ok → `key_last4` only in the response and the DB
  row has no plaintext (assert the plaintext bytes aren't in `encrypted_key`); invalid key → 400
  and nothing saved; disallowed model → 422; replace key keeps one row per provider; first key
  auto-active; activate switches; delete active leaves none active; other users can't see/modify
  (404); partial unique index prevents two active rows (direct DB insert test); usage sums per day
  and kind in the user's timezone; `GET /settings/llm-models` returns the allowlist.
- [ ] 9.3.2 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 9.3.3 Commit: `feat(api): add ai key management and usage endpoints`

---

### Task 9.4 — Factory: user credentials mode

**Files:** `app/llm/factory.py`, `app/llm/pydantic_ai_service.py` (accept provider name + output
mode), `app/core/errors.py` (`LLMNotConfiguredError` → 409 `llm_not_configured`), worker tasks
(use the same factory with the session's user). Tests
`tests/integration/llm/test_factory_user_credentials.py`, extend feature tests.

Rules:
- `LLM_PROVIDER=user_credentials`: active credential → decrypt → `build_model` → service with
  `provider`/`model` set (sessions record them). Decryption failure → log error (no key material)
  and raise `LLMNotConfiguredError` with message "Your AI key needs to be re-entered."
- No active credential: if `LLM_FALLBACK_TO_OLLAMA=true` (default `true` in development; the
  settings validator forces `false` in production) → Ollama service (log once per process that
  the fallback is in use); otherwise → `LLMNotConfiguredError`.
- Provider auth errors at call time → set `last_error_code="llm_auth_failed"` on the credential
  (separate short transaction) and surface `llm_auth_failed`.
- Reports and memory updates in the worker use the session owner's credential at execution time.

**Subtasks:**
- [ ] 9.4.1 Failing tests: builds the right provider from a stored credential (patch `build_model`
  to return a `FunctionModel`); fallback to Ollama when `llm_fallback_to_ollama=True`; with
  `llm_fallback_to_ollama=False` → 409 on
  `POST /sessions/{id}/messages` before streaming, on hint, rewrite, custom draft; drills fall back
  to templates instead of failing; report generation marks `failed`/`llm_not_configured`; auth
  error at call time updates `last_error_code`.
- [ ] 9.4.2 Run → FAIL. Implement. Run → PASS.
- [ ] 9.4.3 Commit: `feat(api): use each user's own ai key`

**Pitfall:** don't cache decrypted keys or provider objects across requests/users.

---

### Task 9.5 — Provider quality check (live, costs money)

The eval runner already supports cloud providers with `EVAL_*_API_KEY` (Task 2.5, ADR-0015).
**Files:** `tests/live/test_user_providers_live.py`.
- [ ] 9.5.1 Live test per provider (skipped unless its `EVAL_*_API_KEY` is set): build the service
  through the **user-credentials path** (a stored, encrypted test credential), then one streamed
  reply and one `FeedbackAnalysis`.
- [ ] 9.5.2 With the owner's permission and keys, run `make eval-cloud` for each provider's
  allowlist default; paste summaries into the completion log. If a provider's in-range rate is
  < 80 %, adjust prompts only if the Phase 2 reference model doesn't get worse (re-run it, and
  re-run Ollama to report its numbers — ADR-0015).
- [ ] 9.5.3 Commit: `test(api): evaluate feedback quality per provider`

---

### Task 9.6 — Web: AI keys, usage, "no key" handling

**Files:** `src/features/ai-keys/*`, `src/features/usage/*`, settings page section,
`src/app/usage/page.tsx`, `src/components/llm-not-configured-banner.tsx`; error mapping for
`llm_not_configured` and `llm_auth_failed` across practice, writing, custom scenario pages.

**Behaviour:**
- Settings → "AI provider": three provider cards (Anthropic, OpenAI, Google Gemini) with status
  (Not set / Active / Saved / Needs attention), `••••1234`, model select (from
  `/settings/llm-models`), "Add key"/"Replace key" dialog (password input, "Where do I get this?"
  link to the provider's key page, note "Your key is encrypted and never shown again. Usage is
  billed by the provider to your account."), "Make active", "Remove" (confirm).
- Validation errors shown inline; saving shows "Key verified".
- Banner on practice/writing pages when the API returns `llm_not_configured`: "Add your AI key to
  start practising" → settings.
- Usage page: range toggle 7/30 days; table by day (AI tokens in/out, speech seconds, voice
  characters, pronunciation seconds) and one simple bar chart of total AI tokens per day (follow the
  `dataviz` skill).

**Subtasks:**
- [ ] 9.6.1 Failing tests: card states; add key flow (success + invalid key error); key input is
  cleared after submit and never re-rendered; activate/remove; banner appears on 409; usage table
  and chart data.
- [ ] 9.6.2 Run → FAIL. Implement. Run → PASS. Commit: `feat(web): add ai key settings and usage page`

---

### Task 9.7 — E2E and switch default

**Files:** `apps/web/e2e/byok.spec.ts`, `apps/web/e2e/fixtures/auth.ts`, `.env.example`
(`LLM_PROVIDER=user_credentials`, `ENCRYPTION_KEYS` placeholder + generation hint), `Makefile`
`dev-fake`, docs.

From this task on, `make dev-fake` runs with `LLM_PROVIDER=user_credentials`,
`FAKE_PROVIDER_MODELS=true` (dev/test only: the factory returns `FakeLLMService` for a user's
active credential, whatever the provider, instead of calling `build_model`), `LLM_KEY_VALIDATION=fake` and `LLM_FALLBACK_TO_OLLAMA=false`. The E2E login
fixture adds a `test-e2e-key-0000000000` Anthropic key for each new user by default
(`withKey: false` opts out).
- [ ] 9.7.1 E2E `byok.spec.ts` (user created with `withKey: false`): banner on a practice page →
  add key `test-1234567890abcdefghij` → "Key verified" → start a session → get a reply → Usage
  page shows today's tokens. All other specs keep passing with the fixture's default key.
- [ ] 9.7.2 `make test-e2e` → PASS.
- [ ] 9.7.3 Update `local-development.md` (new vars, how to add your own key locally),
  `ai-layer.md` §2 (final behaviour), `AGENTS.md`, phase status. Commit:
  `chore: default to user credentials for the llm`

## Phase verification

1. Add a real key for one provider in the browser; practise a text and a voice session; reports and
   memory use that provider (check `practice_sessions.llm_provider` and `feedback_reports.llm_model`).
2. Revoke the key at the provider → next request shows "needs attention" and a clear message.
3. DB inspection shows only ciphertext; logs contain no key material (`grep` the dev log for the
   last 4 characters' surrounding pattern and the full key).
4. Rotate master keys with `app.cli rotate-llm-keys` → keys still work.
5. `make check`, `make test-e2e` → PASS.

## Completion log

<!-- Append: - YYYY-MM-DD · Task N.M · commits · evidence · Notes · Follow-ups -->
