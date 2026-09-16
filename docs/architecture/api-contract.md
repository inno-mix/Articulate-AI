# API Contract

> Base URL: `http://localhost:8000/api/v1` · JSON uses `snake_case` · timestamps ISO-8601 UTC.
> FastAPI generates OpenAPI from `app/schemas/*`; the frontend types are generated from it.
> **This doc is binding:** changing a path, field or status code requires updating this doc,
> regenerating the client (`make gen-client`) and updating tests in the same commit.

## 1. Conventions

### Errors
Every non-2xx response (except 422 from FastAPI validation, which is also wrapped) uses:
```json
{ "error": { "code": "session_not_active", "message": "This session has already ended.", "details": {} } }
```
- `code` is a stable snake_case string the UI can switch on. `message` is safe to show users.
- Implemented by `app/core/errors.py`: `class AppError(Exception)` with `status_code`, `code`,
  `message`, `details`; exception handlers for `AppError`, `RequestValidationError`
  (→ 422 `validation_error`, `details.fields = [{loc, msg}]`) and unhandled `Exception`
  (→ 500 `internal_error`, message never leaks internals).

| Code | HTTP | When |
|---|---|---|
| `validation_error` | 422 | request body/query invalid |
| `not_found` | 404 | resource missing **or owned by another user** (never 403 for others' data) |
| `session_not_active` | 409 | message/hint on an ended session |
| `reply_in_progress` | 409 | a reply is already streaming for this session |
| `session_in_use` | 409 | (Phase 3) deleting a session that has an open voice connection |
| `turn_limit_reached` | 409 | > 20 user turns |
| `llm_unavailable` | 503 | provider unreachable/timeouts after retries |
| `llm_invalid_output` | 502 | structured output failed validation after retries |
| `llm_not_configured` | 409 | (Phase 9, production) user has no active key |
| `llm_auth_failed` | 400 | (Phase 9) stored key rejected by provider |
| `llm_rate_limited` | 429 | provider or our own per-user limit |
| `speech_unavailable` | 503 | Deepgram unreachable |
| `pronunciation_unavailable` | 503 | Azure unreachable |
| `invalid_audio` | 400 | WAV not 16 kHz / mono / PCM16, too long, empty |
| `payload_too_large` | 413 | upload over limit |
| `report_not_ready` | 409 | retry on a report that is pending/running |
| `assessment_incomplete` | 409 | (Phase 5) completing an assessment whose steps aren't done |
| `limit_reached` | 409 | (Phase 6) a per-user count limit, e.g. 50 custom scenarios |
| `drill_already_finished` | 409 | (Phase 6) answering or skipping a completed/skipped drill |
| `local_user_missing` | 500 | (Q1) the local user hasn't been seeded — run `make seed` |
| `invalid_host` | 400 | `Host` header not in `ALLOWED_HOSTS` (request guard, Phase 0) |
| `origin_not_allowed` | 403 | unsafe request whose `Origin` isn't in `CORS_ORIGINS` (request guard, Phase 0) |
| `unauthorized` | 401 | (Phase 7) missing/invalid session |
| `invalid_credentials` | 401 | (Phase 7) wrong email or password (same message for both) |
| `email_taken` | 409 | (Phase 7) registration with an existing email |
| `invalid_token` | 400 | (Phase 7) bad/expired verification or reset token |
| `email_not_verified` | 403 | (Phase 7) for actions that require it |
| `csrf_failed` | 403 | (Phase 7) |
| `rate_limited` | 429 | (Phase 7/10) our rate limiter; `Retry-After` header set |
| `internal_error` | 500 | anything unexpected |

### Pagination
Cursor-based: `?limit=20&cursor=<opaque>` → `{ "items": [...], "next_cursor": "..." | null }`.
Cursor = base64url of `"<iso-timestamp>|<uuid>"`. Max `limit` = 50.

### Auth (by phase)
- Q1 (`AUTH_MODE=local_single_user`): no credentials; `get_current_user` returns the local user.
- Q2 (`AUTH_MODE=accounts`): httpOnly cookies `access_token` / `refresh_token`; unsafe methods
  require header `X-CSRF-Token` matching cookie `csrf_token` (see `security-privacy.md`).

---

## 2. Endpoints — Q1

### Health
`GET /health` → 200
```json
{ "status": "ok", "checks": { "database": "ok", "redis": "ok", "llm": "ok" } }
```
Each check is `"ok"` or `"unavailable"`; `status` is `"degraded"` if any is unavailable (still 200).
`llm` check calls the provider's cheapest liveness call with a 2 s timeout (Ollama: `GET /api/tags`).

### Me / profile / settings
- `GET /me` → `MeOut { user: {id, email, is_local, email_verified}, profile: ProfileOut, settings: SettingsOut }`
  (Phase 7 adds `onboarding_completed: bool`)
- `PATCH /me/profile` body `ProfileUpdate` (all fields optional) → `ProfileOut`
  - `display_name` 1–60, `seniority`, `native_language` ≤ 40, `english_level`, `goals` (enum list,
    ≤ 6), `focus_areas` (dimension keys, ≤ 3), `timezone` (valid IANA)
- `GET /settings` → `SettingsOut`; `PATCH /settings` body `SettingsUpdate` → `SettingsOut`
  - `default_mode`, `voice_input_mode`, `tts_voice` (must be in `GET /voices`)
  - Q2 adds `reminders_enabled`, `reminder_time` (`HH:MM`), `weekly_summary_enabled`
- `GET /voices` → `[{ "id": "aura-2-thalia-en", "label": "Thalia (US, female)" }, ...]` (curated list
  in `app/voice/voices.py`)

### Scenarios (Phase 1; custom in Phase 6)
- `GET /scenarios?category=&difficulty=&mode=&owner=builtin|mine|all` → `list[ScenarioSummary]`
  - `ScenarioSummary { id, slug, title, category, difficulty, summary, recommended_mode, is_custom }`
  - Assessment scenarios are excluded.
- `GET /scenarios/{slug}` → `ScenarioDetail` (= summary + `persona`, `user_objective`,
  `opening_line`, `success_criteria`)
- `POST /scenarios/custom/draft` (Phase 6) body `{ description: str(20..1000) }` → `ScenarioDraft`
  (same fields as detail minus id/slug) — nothing saved
- `POST /scenarios/custom` (Phase 6) body `ScenarioDraft` → 201 `ScenarioDetail`
- `DELETE /scenarios/custom/{id}` (Phase 6) → 204 (sessions using it are deleted by cascade —
  UI must confirm)

### Sessions (Phase 1)
- `POST /sessions` body `{ scenario_id: UUID, mode: "text"|"voice", assessment_id?: UUID }` →
  201 `SessionDetail`
  - Creates the session and the first assistant message (`opening_line`, `seq=0`).
  - `assessment_id` (Phase 5) must be the user's in-progress assessment; it sets
    `purpose=assessment` and is the only way to start an assessment scenario (otherwise those
    scenarios return 404).
- `GET /sessions?limit&cursor&status=` → `Page[SessionSummary]`
  - `SessionSummary { id, scenario: {slug,title}, mode, status, started_at, ended_at, user_turns,
    overall_score | null }`
- `GET /sessions/{id}` → `SessionDetail { ...summary, assessment_id: UUID | null (Phase 5),
  messages: list[MessageOut], limits: {max_user_turns: 20, max_message_chars: 1000} }`
  - `MessageOut { id, seq, role, content, source, created_at }`
- `POST /sessions/{id}/messages` body `{ content: str(1..1000) }` → **200 `text/event-stream`**
  (see §4). Errors that happen *before* streaming starts return normal JSON errors.
- `POST /sessions/{id}/hint` → `{ "hint": "..." }`
- `POST /sessions/{id}/end` → `{ "status": "ended"|"abandoned", "report_status": "pending"|null }`
  - Idempotent: ending an ended session returns the current state.
- `DELETE /sessions/{id}` → 204. Deletes the session with its messages, report and skill scores
  (database cascades). 404 if not owned; 409 `session_in_use` if a voice connection is open for it
  (Phase 3). A queued report job for a deleted session finishes quietly.

### Reports (Phase 2)
- `GET /sessions/{id}/report` → `ReportOut`
  ```json
  {
    "status": "pending|running|ready|failed",
    "error_code": null,
    "overall_score": 72, "objective_met": true, "summary": "...",
    "dimension_scores": [{"dimension": "clarity", "score": 4, "reason": "..."}],
    "strengths": ["..."], "improvements": ["..."],
    "highlights": [{"message_id": "...", "quote": "...", "issue": "...", "better_version": "..."}],
    "grammar_fixes": [{"original": "...", "corrected": "...", "explanation": "..."}],
    "voice_metrics": null,
    "rubric_version": "v1", "llm_model": "llama3.2:latest",
    "created_at": "...", "updated_at": "...", "completed_at": "..."
  }
  ```
  Fields other than `status`/`error_code` are `null` until `ready`. 404 if the session was
  abandoned (no report).
- `POST /sessions/{id}/report/retry` → 202 `{ "status": "pending" }`. Allowed when the report is
  `failed`, `ready` (regenerate), or **stale** — `pending`/`running` with `updated_at` older than
  5 minutes (e.g. the worker stopped). Otherwise 409 `report_not_ready`. `ReportOut` includes
  `updated_at` so the UI can tell.

### Voice (Phase 3)
- `WS /sessions/{id}/voice` — protocol in `voice-and-pronunciation.md` §2.
- `GET /tts/preview?voice=<id>&text=<1..200 chars>` → `audio/mpeg` (Deepgram REST TTS). Used by the
  settings voice preview and the pronunciation "hear it" buttons. Per-user rate limit (30/min) is
  added in Phase 10.

### Pronunciation (Phase 4)
- `GET /pronunciation/sets` → `list[{ slug, title, description, difficulty, sentence_count,
  best_score | null }]`
- `GET /pronunciation/sets/{slug}` → `{ slug, title, description, sentences: [{ id, position,
  text, focus_words, last_score | null }] }`
- `POST /pronunciation/attempts` `multipart/form-data`: `sentence_id` (UUID), `purpose`
  (`practice`|`assessment`|`drill`, default `practice`), `assessment_id` (UUID, Phase 5, required
  when `purpose=assessment`), `audio` (file, `audio/wav`, ≤ 1.2 MB, ≤ 30 s) → 201
  `PronunciationAttemptOut`
  ```json
  { "id": "...", "sentence_id": "...", "pron_score": 81.5, "accuracy": 84.0, "fluency": 90.0,
    "completeness": 100.0, "duration_ms": 4200,
    "words": [{ "word": "cache", "accuracy": 42.0, "error_type": "Mispronunciation",
                "phonemes": [{ "phoneme": "k", "accuracy": 95.0, "heard_as": null }] }],
    "created_at": "..." }
  ```
- `GET /pronunciation/attempts?sentence_id=&limit&cursor` → `Page[PronunciationAttemptOut]`

### Progress, assessment, coach notes (Phase 5)
- `GET /progress/summary` →
  ```json
  { "dimensions": [{ "dimension": "clarity", "current": 70, "previous": 60, "change": 10,
                     "baseline": 50, "baseline_comparable": true,
                     "scorer": "ollama:qwen3:4b", "data_points": 7 }],
    "sessions_completed": 12, "pronunciation_attempts": 40, "drills_completed": 9,
    "streak_days": 4, "practiced_today": true }
  ```
  `current` = average of the last 5 scores from the current scorer (the scorer of the most
  recent score); `previous` = average of the 5 before, same scorer; `null` when missing.
  `baseline_comparable` is false when the baseline was produced by a different scorer.
- `GET /progress/trends?dimension=<key>&range=30d|90d` → `{ "dimension": "...", "points":
  [{ "date": "2026-09-01", "score": 65, "scorer": "ollama:qwen3:4b" }],
  "scorer_changes": [{ "date": "2026-09-10", "from": "ollama:llama3.2:latest", "to": "ollama:qwen3:4b" }],
  "baseline": 50 | null, "baseline_scorer": "..." | null }` (daily average per scorer, user
  timezone)
- `GET /progress/speaking?range=30d|90d` → `{ "points": [{ "date": "...", "wpm": 128.0,
  "filler_rate_per_100": 3.1 }] }`
- `POST /assessment` → 201 `{ id, status, steps: [...] }` (creates or returns the in-progress one)
- `GET /assessment/current` → `{ id, status, steps: [{ kind: "text_session"|"voice_session"|
  "pronunciation", status: "todo"|"done", scenario_slug?, session_id?, sentence_ids? }] }` or 404
- `POST /assessment/{id}/complete` → `{ id, status: "completed" }` (409 if steps not done)
- `GET /coach-notes` → `list[{ id, dimension, note, evidence, times_seen, created_at }]`
  (active only)
- `DELETE /coach-notes/{id}` → 204 (sets `is_active=false`, `dismissed_by_user=true`)

### Drills (Phase 6)
- `GET /drills/today` → `{ date, drills: [DrillOut ×3] }` (generates if missing)
  - `DrillOut { id, position, kind, answer_mode, title, prompt, target_dimension, status,
    payload, result | null }`
- `POST /drills/{id}/text` body `{ answer: str(1..2000) }` → `DrillOut` (with `result`)
- `POST /drills/{id}/voice` multipart `audio` (WAV 16 kHz mono, ≤ 90 s, ≤ 3.5 MB) → `DrillOut`
- `POST /drills/{id}/complete-pronunciation` body `{ attempt_ids: [UUID] }` → `DrillOut`
- `POST /drills/{id}/skip` → `DrillOut`

### Writing coach (Phase 6)
- `POST /writing/rewrite` body `{ text: str(1..4000), channel, goal, context?: str(..500) }` →
  201 `{ id, output_text, changes: [{what, why}], tone_note, created_at }`
- `GET /writing/rewrites?limit&cursor` → `Page[...]` (includes `input_text`, `channel`, `goal`)
- `DELETE /writing/rewrites/{id}` → 204

---

## 3. Endpoints — Q2

### Auth (Phase 7)
| Method & path | Body | Success | Notes |
|---|---|---|---|
| `POST /auth/register` | `{email, password(12..128), display_name?}` | 201 `{user}` + cookies | sends verification email; generic 409 `email_taken` |
| `POST /auth/login` | `{email, password}` | 200 `{user}` + cookies | 401 `invalid_credentials` (same message for unknown email); rate limited |
| `POST /auth/logout` | – | 204 | revokes refresh family, clears cookies |
| `POST /auth/refresh` | – (cookie) | 204 + new cookies | rotation; reuse of a used token revokes the family |
| `POST /auth/verify-email` | `{token}` | 200 `{user}` | 400 `invalid_token` |
| `POST /auth/resend-verification` | – | 202 | max 3/hour |
| `POST /auth/forgot-password` | `{email}` | 202 always | never reveals whether the email exists |
| `POST /auth/reset-password` | `{token, password}` | 204 | revokes all refresh tokens |
| `GET /auth/csrf` | – | 200 `{csrf_token}` + cookie | called by the web app on load |

- `POST /onboarding` body `{ seniority, english_level, native_language?, goals, focus_areas,
  timezone }` → `ProfileOut` (sets `onboarding_completed_at`)
- `DELETE /me` body `{ password }` → 204 (deletes user + cascades, clears cookies)

### Emails (Phase 8)
- `GET /emails/unsubscribe?token=...` → HTML page confirming; `POST` same path does the
  unsubscribe (one-click `List-Unsubscribe-Post` support).

### AI keys & usage (Phase 9)
- `GET /settings/llm-credentials` → `list[{ provider, key_last4, model, is_active, validated_at,
  last_error_code }]`
- `PUT /settings/llm-credentials/{provider}` body `{ api_key, model }` → validates, encrypts,
  saves → `{...}`; 400 `llm_auth_failed` if the provider rejects it
- `POST /settings/llm-credentials/{provider}/activate` → sets it as the only active one
- `DELETE /settings/llm-credentials/{provider}` → 204
- `GET /settings/llm-models` → `{ "anthropic": [{"id": "...", "label": "..."}], "openai": [...],
  "google": [...] }` (from `app/llm/model_allowlist.yaml`)
- `GET /usage?range=7d|30d` → `{ "days": [{ "date": "...", "llm_input_tokens": 0,
  "llm_output_tokens": 0, "stt_seconds": 0, "tts_characters": 0, "pronunciation_seconds": 0 }] }`

---

## 4. Server-Sent Events: `POST /sessions/{id}/messages`

Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`,
`X-Accel-Buffering: no`. Each event is `event: <name>\ndata: <json>\n\n`.

| Event | Data | Notes |
|---|---|---|
| `user_message` | `MessageOut` | first event, the saved user message |
| `delta` | `{ "text": "partial" }` | 0..n times |
| `assistant_message` | `MessageOut` | final saved assistant message |
| `done` | `{ "user_turns": 3, "turns_left": 17 }` | last event on success |
| `error` | `{ "code": "llm_unavailable", "message": "..." }` | last event on failure; no assistant message saved |

Safety path: if the crisis check triggers, the stream sends `user_message`, one `delta` with the
fixed safety text, `assistant_message` (`source: "system"`), then `done`.

Client: `fetch` with `ReadableStream` + `eventsource-parser` (EventSource can't POST). Abort
with `AbortController` when the user leaves the page; the server stops generation when the client
disconnects (`await request.is_disconnected()` checked between deltas).
