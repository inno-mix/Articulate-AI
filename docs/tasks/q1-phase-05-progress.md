# Phase 5 — Progress, Baseline Assessment, Coach Memory

> **Milestone:** Q1 · **Depends on:** Phases 2, 3, 4
> **For agentic workers:** follow `docs/guides/agent-workflow.md`. Tick subtasks as you go.

**Goal:** Users see their progress over time (per skill, speaking stats, pronunciation, streak),
can take a baseline assessment that anchors the charts, and the coach remembers recurring weaknesses
and uses them in future practice.

**Architecture:** Read-side `progress` service over `skill_scores`, `feedback_reports.voice_metrics`
and activity tables (timezone-aware). `assessments` table links sessions and pronunciation attempts.
`coach_notes` updated by a worker task after each report (LLM `MemoryUpdate`) and by a code rule
after pronunciation attempts; top notes injected into role-play prompts.

**Read before starting:** `product-spec.md` F6–F8, `api-contract.md` §2 (Progress, assessment,
coach notes; Sessions `assessment_id`; Pronunciation `assessment_id`), `data-model.md`
(`assessments`, `coach_notes`, `skill_scores`), `ai-layer.md` §4.1 item 4, §5 (`MemoryUpdate`),
`voice-and-pronunciation.md` §4.4 (weak word rule). Load the `dataviz` skill before building charts.

**Out of scope:** drills (Phase 6 adds drill activity to the streak), emails (Phase 8).

---

## File map

```
apps/api/app/models/{assessment,coach_note}.py
apps/api/migrations/versions/0006_assessments.py   (+ assessment_id FKs)
apps/api/migrations/versions/0007_coach_notes.py
apps/api/app/domain/streak.py
apps/api/app/schemas/{progress,assessment,coach_note}.py
apps/api/app/services/{progress,activity,assessment,memory}.py
apps/api/app/services/{sessions,pronunciation,chat,feedback}.py   (modify)
apps/api/app/llm/prompts/memory_update.md.j2
apps/api/app/llm/{outputs,fake_outputs}.py                        (+ MemoryUpdate)
apps/api/app/worker/tasks/memory.py
apps/api/app/api/v1/{progress,assessment,coach_notes}.py
apps/api/tests/unit/domain/test_streak.py
apps/api/tests/unit/services/test_memory_rules.py
apps/api/tests/integration/api/{test_progress,test_assessment,test_coach_notes}.py
apps/api/tests/integration/services/{test_memory_update,test_weak_words}.py
apps/web/src/features/progress/{api.ts,query-keys.ts,hooks/*,components/*}
apps/web/src/features/assessment/{api.ts,hooks/*,components/*}
apps/web/src/features/coach-notes/{api.ts,components/*}
apps/web/src/app/page.tsx                                          (dashboard)
apps/web/src/app/progress/page.tsx  apps/web/src/app/assessment/page.tsx
apps/web/tests/features/{progress,assessment,coach-notes}/*.test.tsx
apps/web/e2e/progress.spec.ts
```

---

### Task 5.1 — Activity, streak and progress read APIs

**Goal:** `GET /progress/summary`, `/progress/trends`, `/progress/speaking`.
**Depends on:** Phases 2–4
**Files:** `app/domain/streak.py`, `app/services/{activity,progress}.py`,
`app/schemas/progress.py`, `app/api/v1/progress.py`. Tests
`tests/unit/domain/test_streak.py`, `tests/integration/api/test_progress.py`.

**Interfaces (produces):**
```python
# app/domain/streak.py (pure)
def current_streak(active_days: set[date], today: date) -> int
    # consecutive days ending today; if today inactive but yesterday active, the streak still counts
    # up to yesterday (the user can still practise today)

# app/services/activity.py
async def active_local_dates(db, user_id, tz: ZoneInfo, *, since: datetime) -> set[date]
    # union of: practice_sessions.ended_at (status ended), pronunciation_attempts.created_at,
    # (Phase 6) drills.completed_at — each converted to the user's local date in SQL
    # (`(ts AT TIME ZONE :tz)::date`)
async def practiced_on(db, user_id, tz, local_date: date) -> bool

# app/services/progress.py
async def get_summary(db, user: User) -> ProgressSummaryOut
async def get_trends(db, user: User, dimension: Dimension, range_days: Literal[30, 90]) -> TrendsOut
async def get_speaking_trends(db, user: User, range_days: Literal[30, 90]) -> SpeakingTrendsOut
```
Rules:
- **Scorer rule:** scores are only compared within one `scorer`. For each dimension, the
  *current scorer* is the scorer of its most recent practice score.
- `current` = average of the latest 5 practice scores from the current scorer; `previous` =
  average of the 5 before those, same scorer; `change = current - previous` (null if either
  missing); `data_points` = count of practice scores from the current scorer; round to integers.
- `baseline` = average of the dimension's `purpose=assessment` scores from the latest completed
  assessment (null until Task 5.2 is done — keep the query in a function that returns `{}` for now
  and is filled in 5.2); `baseline_comparable` = all of those scores have the current scorer.
- Trends: daily average per (local date, scorer) within the range (practice only);
  `scorer_changes` lists each date where the scorer differs from the previous point; `baseline` and
  `baseline_scorer` as above.
- Speaking trends: per local date, average `wpm` and `filler_rate_per_100` from ready reports of
  voice sessions.
- `sessions_completed` counts `ended` sessions; `pronunciation_attempts` counts attempts;
  `drills_completed` is `0` until Phase 6.

**Subtasks:**
- [ ] 5.1.1 Failing streak tests (parametrised): empty → 0; today only → 1; today+yesterday → 2;
  yesterday+day before (not today) → 2; gap → counts from the latest run only; future dates ignored.
- [ ] 5.1.2 Failing integration tests: summary with no data (all nulls/zeros); current/previous/
  change maths with 12 scores; practice-only (assessment scores excluded from current);
  timezone boundary (a session ended 23:30 UTC counts as the next day for `Asia/Manila`);
  trends daily averages and range filtering; unknown dimension → 422; speaking trends only from
  voice reports; `practiced_today` true after a pronunciation attempt today; `current` ignores
  scores from an older scorer; `baseline_comparable` is false when the baseline scorer differs;
  trends return `scorer_changes` with the right dates.
- [ ] 5.1.3 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 5.1.4 Commit: `feat(api): add progress summary and trends endpoints`

---

### Task 5.2 — Baseline assessment

**Goal:** Assessment lifecycle; assessment-linked sessions and pronunciation attempts; baseline in
progress.
**Depends on:** 5.1
**Files:** `app/models/assessment.py`, migration `0006_assessments` (assessments + `assessment_id` on
`practice_sessions` and `pronunciation_attempts`), `app/schemas/assessment.py`,
`app/services/assessment.py`, `app/api/v1/assessment.py`; modify `app/services/sessions.py`
(`assessment_id` handling), `app/services/pronunciation.py` + router (form field),
`app/services/progress.py` (baseline). Test `tests/integration/api/test_assessment.py`.

**Interfaces (produces):**
```python
ASSESSMENT_TEXT_SCENARIO = "assessment-explain-your-project"
ASSESSMENT_VOICE_SCENARIO = "assessment-standup"
ASSESSMENT_SENTENCES: tuple[tuple[str, int], ...] = (("tech-terms-1", 1), ("tech-terms-2", 1), ("tricky-sounds", 1))
    # (set slug, sentence position — positions are 1-based, assigned by the loader in YAML order)

async def start_or_get_assessment(db, user_id) -> AssessmentOut          # POST /assessment
async def get_current_assessment(db, user_id) -> AssessmentOut           # in-progress, else 404
async def complete_assessment(db, user_id, assessment_id) -> AssessmentOut   # 409 assessment_incomplete
async def assessment_steps(db, assessment: Assessment) -> list[AssessmentStep]
    # text_session done  = an assessment session (mode text) with a READY report
    # voice_session done = an assessment session (mode voice) with a READY report
    # pronunciation done = one attempt per ASSESSMENT_SENTENCES linked to the assessment
async def latest_baseline(db, user_id) -> dict[Dimension, int]
```
Session rule: `POST /sessions` with `assessment_id` → must be the user's `in_progress` assessment
(else 404), scenario must be the matching assessment scenario for the mode (else 422
`validation_error`), `purpose=assessment`. Without `assessment_id`, assessment scenarios → 404.

**Subtasks:**
- [ ] 5.2.1 Failing tests: POST creates in-progress assessment (second POST returns the same one);
  steps start as `todo` and carry scenario slugs / sentence ids; assessment session creation rules
  (wrong scenario → 422; other user's assessment → 404; missing `assessment_id` for an assessment
  scenario → 404); steps become `done` as reports become ready and attempts are posted with
  `purpose=assessment`; complete before done → 409 `assessment_incomplete`; complete after done →
  `completed`; baseline appears in `/progress/summary` and `/progress/trends`; a newer completed
  assessment replaces the baseline; `purpose=assessment` attempt without `assessment_id` → 422; assessment attempts write
  `skill_scores` with `purpose=assessment`.
- [ ] 5.2.2 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 5.2.3 Commit: `feat(api): add baseline assessment`

---

### Task 5.3 — Coach memory

**Goal:** Notes updated after each report and from weak pronunciation words; used in prompts;
viewable and dismissable.
**Depends on:** 5.1
**Read before starting:** `ai-layer.md` §4.1, §5 (`MemoryUpdate`), `voice-and-pronunciation.md`
§4.4.
**Files:** `app/models/coach_note.py` (migration `0007_coach_notes`), `app/llm/prompts/memory_update.md.j2`,
`app/llm/{outputs,fake_outputs}.py`, `app/services/memory.py`, `app/worker/tasks/memory.py`,
`app/schemas/coach_note.py`, `app/api/v1/coach_notes.py`; modify `app/services/feedback.py`
(enqueue after ready), `app/services/pronunciation.py` (weak word rule), `app/services/chat.py` +
voice relay (inject notes). Tests `tests/unit/services/test_memory_rules.py`,
`tests/integration/services/{test_memory_update,test_weak_words}.py`,
`tests/integration/api/test_coach_notes.py`, extend `tests/unit/llm/test_prompts.py`.

**Interfaces (produces):**
```python
# app/services/memory.py
def apply_memory_actions(active: list[CoachNote], dismissed_texts: set[str],
                         actions: list[MemoryAction], *, max_active: int = 8) -> MemoryPlan
    # pure: returns MemoryPlan(add: list[NewNote], reinforce: list[(note_id, evidence)], resolve: list[note_id], evict: list[note_id])
    # rules: ignore reinforce/resolve for unknown note ids; skip "add" whose normalised text equals an
    # active or dismissed note (treat as reinforce if active); when adding beyond max_active, evict the
    # active note with the lowest times_seen (oldest first on ties)
async def update_memory_from_report(session_factory, settings, report_id: UUID, *, llm_override=None) -> None
async def record_weak_word(db, user_id: UUID, word: str) -> None
    # add or reinforce a note: dimension=pronunciation, note=f'Practise saying "{word}"'
async def top_notes_for_prompt(db, user_id, *, mode: PracticeMode, limit: int = 3) -> list[CoachNote]
    # by times_seen desc, updated_at desc; mode=text excludes pronunciation and fluency notes
async def list_active_notes(db, user_id) -> list[CoachNoteOut]
async def dismiss_note(db, user_id, note_id) -> None     # 404 if not owned
# app/worker/tasks/memory.py
@broker.task(task_name="update_coach_memory") async def update_coach_memory(report_id: str) -> None
```
Memory prompt inputs: learner level, current active notes (id, dimension, note, times_seen),
the new report (summary, dimension scores + reasons, improvements, highlights). Instructions:
at most 5 actions; only add notes that are specific and likely to recur; prefer reinforcing an
existing note over adding a near-duplicate; resolve a note when the report shows clear improvement
on it.
Weak word rule: after saving an attempt, for each word with accuracy < 60, count attempts in the
last 30 days where the same word (case-insensitive) scored < 60; if ≥ 2 → `record_weak_word`.
Memory failures never affect the report (log and exit). The memory call uses
`TEMPERATURE["memory"]` (0.0) and holds no DB session while waiting for the LLM.

**Subtasks:**
- [ ] 5.3.1 Failing pure tests for `apply_memory_actions`: add; add duplicate of active → reinforce;
  add duplicate of dismissed → skipped; reinforce unknown id → ignored; resolve; eviction at 8
  (lowest times_seen, oldest first); more than 5 actions → only first 5 applied.
- [ ] 5.3.2 Failing integration tests: report ready enqueues memory update; fake `MemoryUpdate`
  applied to DB; LLM failure leaves notes unchanged and logs; weak word needs two low attempts;
  notes injected into the role-play system prompt (capture via fake LLM) for text and voice, with
  pronunciation/fluency notes left out of text sessions;
  `GET /coach-notes` lists active only; `DELETE` dismisses; other user's note → 404.
- [ ] 5.3.3 Run → FAIL. Implement. Run → PASS. Manual check with Ollama: seed two notes, start a
  session, and confirm the persona naturally creates chances to practise them. (The feedback
  prompt is unchanged in this task, so `make eval` isn't needed.)
- [ ] 5.3.4 Commit: `feat(api): add coach memory from reports and pronunciation`

---

### Task 5.4 — Web: dashboard and progress page

**Goal:** Home becomes a dashboard; `/progress` shows charts and coach notes.
**Depends on:** 5.1, 5.3
**Read before starting:** `dataviz` skill (load it before writing chart code).
**Files:** `src/features/progress/*`, `src/features/coach-notes/*`, `src/app/page.tsx`,
`src/app/progress/page.tsx`; enable "Progress" in the shell. Add `pnpm --filter web add recharts`.
Tests listed in the file map.

**Behaviour:**
- Dashboard (`/`): greeting with display name; "Practised today ✓ / Not yet today"; streak
  ("4-day streak"); primary actions (Practise a scenario, Pronunciation, Drills — "Soon" until
  Phase 6); if no completed assessment: a card "Take your 10-minute baseline" → `/assessment`;
  skill tiles (label, current score /100, change arrow + number, "Not enough data" when null);
  recent sessions (last 3) with scores; top coach notes (3) with "See all".
- Progress page: dimension selector (tabs or select), range toggle 30/90 days, line chart of daily
  scores with a dashed baseline line and accessible data table fallback ("Show data"); speaking
  chart (WPM with the 110–170 band shaded; filler rate on a second chart — don't use dual axes);
  pronunciation trend (dimension `pronunciation`); coach notes list with "Dismiss" (confirm).
- Scorer changes: the trend chart draws a labelled vertical marker "AI model changed" at each
  `scorer_changes` date. When `baseline_comparable` is false the baseline line is hidden and the
  dashboard shows "Your baseline was measured with a different AI model — retake it to compare
  fairly" with a link to `/assessment`.
- Empty states explain how to get data ("Complete a practice session to see this chart").
- Charts follow the `dataviz` skill (colours from theme tokens, legible in light/dark,
  keyboard-accessible tooltips or the data table).

**Subtasks:**
- [ ] 5.4.1 Failing tests: dashboard tiles render values/changes/empty text; assessment card shown
  only without a baseline; streak text pluralisation; progress chart receives the right points for
  the selected dimension/range (assert on the data passed to a thin chart wrapper, not SVG
  internals); "Show data" table; dismissing a note removes it after the mutation; the
  "AI model changed" marker is passed for each scorer change; baseline hidden and the retake card
  shown when `baseline_comparable` is false.
- [ ] 5.4.2 Run → FAIL. Implement. Run → PASS. `make lint`.
- [ ] 5.4.3 Browser check with real data (after several sessions): charts readable in light and dark
  mode; no console errors.
- [ ] 5.4.4 Commit: `feat(web): add dashboard, progress charts and coach notes`

---

### Task 5.5 — Web: assessment flow

**Goal:** `/assessment` guides the user through the three steps and shows the baseline.
**Depends on:** 5.2, 5.4
**Files:** `src/features/assessment/*`, `src/app/assessment/page.tsx`; session and pronunciation
components accept an optional `assessmentId` prop. Tests `tests/features/assessment/*.test.tsx`.

**Behaviour:**
- Intro: what's measured and how long it takes (~10 minutes); "Start" → `POST /assessment`.
- Checklist of 3 steps with status. Step 1 "Explain your project (text)" → creates the assessment
  text session and opens it; Step 2 "Stand-up update (voice)" → same for voice; Step 3
  "Read 3 sentences" → inline recorder using the Phase 4 components with `purpose=assessment`.
- After finishing a session the report page shows "Back to assessment" when the session's
  `assessment_id` is set (`SessionDetail.assessment_id`, see `api-contract.md`), and hides
  "Practise again" (assessment scenarios can't be started as normal practice).
- When all steps are done: "Finish" → `POST /assessment/{id}/complete` → results: baseline per
  skill with short explanations and a CTA to start practising.
- Steps whose report is still generating show "Scoring…" and poll.

**Subtasks:**
- [ ] 5.5.1 Failing tests: start → checklist; step states from API; step 3 posts attempts with
  `purpose=assessment` and `assessment_id`; finish disabled until all done; results screen.
- [ ] 5.5.2 Run → FAIL. Implement. Run → PASS.
- [ ] 5.5.3 Commit: `feat(web): add baseline assessment flow`

---

### Task 5.6 — E2E: progress and assessment

**Files:** `apps/web/e2e/progress.spec.ts`.
- [ ] 5.6.1 Spec (fake providers): complete the assessment (text session 2 turns → end → wait for
  report; voice session with two PTT turns → end; 3 pronunciation recordings) → Finish →
  dashboard shows skill tiles and no assessment card → complete one normal text practice session
  (2 turns, wait for its report) → Progress page shows a chart point for clarity and the baseline
  line (same fake scorer, so it's comparable).
- [ ] 5.6.2 `make test-e2e` → PASS. Update phase status. Commit: `test(web): add progress e2e journey`

## Phase verification

1. With real providers, take the assessment, then do 3 practice sessions; dashboard numbers match a
   manual SQL check (`select dimension, avg(score) … limit 5`).
2. Change the profile timezone with the API (there is no profile screen until Phase 7):
   `curl -s -X PATCH localhost:8000/api/v1/me/profile -H 'Content-Type: application/json' -d '{"timezone":"Pacific/Auckland"}'`
   → "practised today" and the streak update correctly; set it back afterwards.
3. After several sessions with the same weakness, a matching coach note appears and the persona
   creates chances to practise it.
4. Dismiss a note → it doesn't come back as a duplicate.
5. `make check` and `make test-e2e` → PASS.

## Completion log

<!-- Append: - YYYY-MM-DD · Task N.M · commits · evidence · Notes · Follow-ups -->
