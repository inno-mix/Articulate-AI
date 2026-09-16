# Phase 8 — Reminder & Weekly Summary Emails

> **Milestone:** Q2 · **Depends on:** Phase 7
> **For agentic workers:** follow `docs/guides/agent-workflow.md`. Tick subtasks as you go.

**Goal:** Verified users can opt in to a daily practice reminder at their local time (sent only if
they haven't practised that day) and a weekly progress summary; every email has one-click
unsubscribe. Housekeeping jobs clean up expired tokens and old delivery logs.

**Architecture:** `TaskiqScheduler` with `LabelScheduleSource` runs cron tasks every 15 minutes.
Selection queries are timezone-aware and idempotent through `email_deliveries.dedupe_key`.
Emails are rendered from templates with stats computed by existing services — no LLM.

**Read before starting:** `product-spec.md` F14, `security-privacy.md` §2.2, §3,
`data-model.md` (`user_settings` reminder columns, `email_deliveries`), `api-contract.md` §3
(Emails), ADR-0006. Context7: Taskiq scheduling (`TaskiqScheduler`, `LabelScheduleSource`, cron
labels), `itsdangerous`.

**Out of scope:** push notifications, Slack, SMS, a production email provider.

---

## File map

```
apps/api/app/worker/scheduler.py
apps/api/app/worker/tasks/{reminders,housekeeping}.py
apps/api/app/services/{reminders,weekly_summary,unsubscribe}.py
apps/api/app/email/templates/{practice_reminder,weekly_summary}.{html,txt}.j2
apps/api/app/email/templates/unsubscribe_page.html.j2
apps/api/app/api/v1/emails.py
apps/api/app/schemas/me.py                        (+ reminder settings)
apps/api/app/services/me.py                       (validation: verified email required)
apps/api/app/domain/clock.py                      (injectable now())
apps/api/tests/unit/services/{test_reminder_window,test_unsubscribe_tokens}.py
apps/api/tests/integration/services/{test_reminders,test_weekly_summary,test_housekeeping}.py
apps/api/tests/integration/api/{test_unsubscribe,test_reminder_settings}.py
package.json                                      (dev:all adds scheduler)
apps/web/src/features/settings/components/reminders-section.tsx
apps/web/tests/features/settings/reminders.test.tsx
```

---

### Task 8.1 — Scheduler and housekeeping

**Goal:** A scheduler process runs cron tasks; cleanup jobs exist.
**Files:** `app/worker/scheduler.py`, `app/worker/tasks/housekeeping.py`,
`app/domain/clock.py`, root `package.json` (`dev:scheduler` script, added to `dev:all`),
`docs/architecture/overview.md` §6 (already lists the scheduler — confirm the command).
Tests `tests/integration/services/test_housekeeping.py`.

**Interfaces (produces):**
```python
# app/domain/clock.py
class Clock(Protocol):
    def now(self) -> datetime          # timezone-aware UTC
class SystemClock: ...
class FixedClock: def __init__(self, at: datetime) -> None; def advance(self, delta: timedelta) -> None

# app/worker/scheduler.py
scheduler = TaskiqScheduler(broker, sources=[LabelScheduleSource(broker)])

# app/worker/tasks/housekeeping.py
@broker.task(task_name="cleanup_auth_tokens", schedule=[{"cron": "17 3 * * *"}])      # daily 03:17 UTC
async def cleanup_auth_tokens() -> int        # deletes tokens expired > 7 days ago; returns count
@broker.task(task_name="cleanup_email_deliveries", schedule=[{"cron": "27 3 * * *"}])
async def cleanup_email_deliveries() -> int   # deletes rows older than 90 days
```
Script: `"dev:scheduler": "cd apps/api && uv run taskiq scheduler app.worker.scheduler:scheduler app.worker.tasks"`.

**Subtasks:**
- [ ] 8.1.1 Failing tests with `FixedClock`: only rows past the thresholds are deleted; counts
  returned.
- [ ] 8.1.2 Run → FAIL. Implement. Run → PASS. Manual: `make dev` shows `[scheduler]` output and
  the schedule list at startup.
- [ ] 8.1.3 Commit: `feat(api): add scheduler and housekeeping jobs`

**Pitfalls:** run exactly one scheduler process (duplicate schedulers = duplicate jobs; dedupe keys
protect emails but not other jobs).

---

### Task 8.2 — Reminder settings API and UI

**Goal:** Users set reminders on/off, time, and weekly summary on/off.
**Files:** `app/schemas/me.py`, `app/services/me.py`, settings UI section. Tests
`tests/integration/api/test_reminder_settings.py`, `tests/features/settings/reminders.test.tsx`.

Rules: `reminder_time` format `HH:MM` in 15-minute steps (`00`, `15`, `30`, `45`); turning on
reminders or the weekly summary requires a verified email (403 `email_not_verified`); turning
reminders on without a time defaults to `18:00`. `SettingsOut` includes the three fields.

**Subtasks:**
- [ ] 8.2.1 Failing API tests: set/unset; invalid minute (e.g. `18:10`) → 422; unverified → 403;
  default time applied.
- [ ] 8.2.2 Failing UI tests: toggles + time select (15-minute options); unverified users see the
  verify-email prompt instead of toggles; saving shows a toast.
- [ ] 8.2.3 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 8.2.4 Commit: `feat: add reminder settings`

---

### Task 8.3 — Daily practice reminder

**Goal:** Every 15 minutes, send reminders to users whose local reminder time falls in the current
window and who haven't practised today.
**Depends on:** 8.1, 8.2
**Files:** `app/services/reminders.py`, `app/worker/tasks/reminders.py`, templates.
Tests `tests/unit/services/test_reminder_window.py`, `tests/integration/services/test_reminders.py`.

**Interfaces (produces):**
```python
def in_window(local_now: datetime, reminder_time: time, window: timedelta = timedelta(minutes=15)) -> bool   # pure
async def due_practice_reminders(db, clock: Clock) -> list[ReminderCandidate]
    # users: email verified, reminders_enabled, reminder_time set; local time in window;
    # not practiced on local date (activity service); no delivery with key
    # f"practice_reminder:{user_id}:{local_date.isoformat()}"
@broker.task(task_name="send_practice_reminders", schedule=[{"cron": "*/15 * * * *"}])
async def send_practice_reminders() -> int     # enqueues send_email per candidate; returns count
```
Email content: subject "A few minutes of practice today?"; body greets by display name, shows the
current streak (or "Start a new streak today"), one suggested action (top coach note's dimension
→ a matching scenario title, else "Today's drills"), button → `FRONTEND_URL/drills`, unsubscribe
link + headers (Task 8.5). Filtering by timezone happens in Python after a coarse SQL filter (users
with reminders on) — acceptable at this scale; note it.

**Subtasks:**
- [ ] 8.3.1 Failing pure tests for `in_window` (start inclusive, end exclusive, midnight wrap,
  DST change day in `America/New_York`).
- [ ] 8.3.2 Failing integration tests with `FixedClock` + `FakeEmailSender`: due user gets one
  email; second run in the same window sends nothing (dedupe); user who practised today gets
  nothing; unverified or disabled users get nothing; two users in different timezones at the same
  UTC instant — only the one whose local time matches; content includes streak and unsubscribe
  link; no transcript text appears in the email.
- [ ] 8.3.3 Run → FAIL. Implement. Run → PASS.
- [ ] 8.3.4 Commit: `feat(api): send daily practice reminders`

---

### Task 8.4 — Weekly summary

**Goal:** Monday 09:00 local summary of the previous 7 days.
**Depends on:** 8.3
**Files:** `app/services/weekly_summary.py`, reminders task module (second scheduled task),
templates. Tests `tests/integration/services/test_weekly_summary.py`.

**Interfaces (produces):**
```python
@dataclass(frozen=True)
class WeeklyStats: sessions: int; drills: int; pronunciation_attempts: int; streak: int
                  most_improved: tuple[str, int] | None     # (dimension label, change)
                  focus_next: str | None                    # top coach note text
async def weekly_stats(db, user: User, local_week_start: date) -> WeeklyStats
@broker.task(task_name="send_weekly_summaries", schedule=[{"cron": "*/15 * * * *"}])
async def send_weekly_summaries() -> int
    # due when local weekday is Monday and local time in [09:00, 09:15); dedupe key
    # f"weekly_summary:{user_id}:{iso_year}-W{iso_week}"
```
Zero-activity weeks still get an encouraging summary ("No practice last week — here's a 5-minute
way to restart."). Subject: "Your week in practice".

**Subtasks:**
- [ ] 8.4.1 Failing tests: stats maths over a seeded week (timezone-correct boundaries); due only in
  the Monday window; dedupe per ISO week; zero-activity variant; content has no transcript text.
- [ ] 8.4.2 Run → FAIL. Implement. Run → PASS.
- [ ] 8.4.3 Commit: `feat(api): send weekly progress summaries`

---

### Task 8.5 — Unsubscribe

**Goal:** One-click unsubscribe for both email kinds.
**Files:** `app/services/unsubscribe.py`, `app/api/v1/emails.py`,
`app/email/templates/unsubscribe_page.html.j2`, email task (headers). Add `uv add itsdangerous`.
Settings `EMAIL_TOKEN_SECRET` (required when `AUTH_MODE=accounts`) and `API_PUBLIC_URL`
(default `http://localhost:8000`).
Tests `tests/unit/services/test_unsubscribe_tokens.py`, `tests/integration/api/test_unsubscribe.py`.

**Interfaces (produces):**
```python
def make_unsubscribe_token(user_id: UUID, kind: Literal["practice_reminder", "weekly_summary"], secret: str) -> str
def read_unsubscribe_token(token: str, secret: str, *, max_age_days: int = 90) -> tuple[UUID, str]   # InvalidTokenError
def unsubscribe_url(settings, user_id, kind) -> str      # f"{settings.api_public_url}/api/v1/emails/unsubscribe?token=…"
```
`GET /emails/unsubscribe?token=` → small HTML page with a "Confirm unsubscribe" form (POST);
`POST` (form or one-click `List-Unsubscribe=One-Click` body) → turns the setting off → HTML
"You're unsubscribed" page. Invalid/expired token → HTML page explaining how to change settings
after logging in (status 400). Headers on emails: `List-Unsubscribe: <url>`,
`List-Unsubscribe-Post: List-Unsubscribe=One-Click`.

**Subtasks:**
- [ ] 8.5.1 Failing tests: token round trip; tampered/expired → error; GET shows confirm page;
  POST disables only the matching setting; invalid token page; emails carry both headers; endpoint
  is public and exempt from CSRF (Origin not required for POST from email clients — document why
  it's safe: the signed token is the authority).
- [ ] 8.5.2 Run → FAIL. Implement. Run → PASS. Update `security-privacy.md` if any rule differs.
- [ ] 8.5.3 Commit: `feat(api): add one-click email unsubscribe`

---

### Task 8.6 — End-to-end check

- [ ] 8.6.1 Integration test marked `mail` (runs only when Mailpit is up; add the marker to
  pytest config, excluded by default like `live`): send one reminder through `SmtpEmailSender` and
  read it back from Mailpit's API; assert subject and unsubscribe header.
- [ ] 8.6.2 Manual: set your reminder time to the next quarter hour, wait, see the email in
  Mailpit, click unsubscribe, confirm the setting turned off in the UI.
- [ ] 8.6.3 `make check` → PASS; update phase status; commit: `test(api): verify reminder emails through mailpit`

## Phase verification

1. Reminders arrive only in the right local window and only when you haven't practised.
2. Weekly summary arrives on Monday 09:00 local (use `FixedClock` in a manual script, not by
   waiting).
3. Unsubscribe links work without logging in; settings reflect it.
4. Housekeeping deletes only expired data.
5. `make check`, `make test-e2e` → PASS.

## Completion log

<!-- Append: - YYYY-MM-DD · Task N.M · commits · evidence · Notes · Follow-ups -->
