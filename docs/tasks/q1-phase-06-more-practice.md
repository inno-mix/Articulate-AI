# Phase 6 — Writing Coach, Custom Scenarios, Daily Drills, Settings

> **Milestone:** Q1 (last Q1 phase) · **Depends on:** Phase 5
> **For agentic workers:** follow `docs/guides/agent-workflow.md`. Tick subtasks as you go.

**Goal:** Complete the Q1 feature set: rewrite messages, create custom scenarios from real
situations, do three personalised daily drills, and manage practice/voice settings (the profile
screen is Q2 — Phase 7).
Finish with the Q1 exit review.

**Architecture:** Three LLM-backed services with structured outputs (`RewriteResult`,
`ScenarioDraftOut`, `DrillBatch`/`DrillFeedback`), a Deepgram pre-recorded adapter for voice drill
answers, lazy per-day drill generation with static fallback templates, and a settings page over
existing endpoints. LLM calls use the temperatures in `ai-layer.md` §4.3 (rewrite 0.3, custom
scenario 0.7, drill generation 0.8, drill feedback 0.0).

**Read before starting:** `product-spec.md` F9–F12, `api-contract.md` §2 (Scenarios custom,
Drills, Writing coach, Me/settings), `data-model.md` (`drills`, `writing_rewrites`,
`skill_scores.drill_id`), `ai-layer.md` §4–5, `voice-and-pronunciation.md` §5–7, ADR-0013, ADR-0016
(pre-recorded SDK method).

**Out of scope:** reminders (Phase 8), accounts (Phase 7), AI keys (Phase 9).

---

## File map

```
apps/api/app/models/{writing,drill}.py
apps/api/migrations/versions/0008_writing_rewrites.py
apps/api/migrations/versions/0009_drills.py                  (+ skill_scores.drill_id)
apps/api/app/llm/prompts/{rewrite,custom_scenario,drill_generate,drill_feedback}.md.j2
apps/api/app/llm/{outputs,fake_outputs}.py                    (+ RewriteResult, ScenarioDraftOut, DrillBatch, DrillFeedback)
apps/api/content/drills/templates.yaml
apps/api/app/content/drill_templates.py
apps/api/app/voice/deepgram_prerecorded.py  apps/api/app/voice/fake.py (+ FakePrerecordedTranscriber)
apps/api/app/schemas/{writing,drill}.py  apps/api/app/schemas/scenario.py (+ draft)
apps/api/app/services/{writing,custom_scenarios,drills,drill_scoring}.py
apps/api/app/services/activity.py                             (+ drills)
apps/api/app/services/progress.py                             (drills_completed)
apps/api/app/api/v1/{writing,drills}.py  apps/api/app/api/v1/scenarios.py (custom)
apps/api/tests/unit/services/{test_drill_composition,test_drill_scoring}.py
apps/api/tests/unit/voice/test_deepgram_prerecorded.py
apps/api/tests/integration/api/{test_writing,test_custom_scenarios,test_drills}.py
apps/web/src/features/writing/*  apps/web/src/features/custom-scenarios/*
apps/web/src/features/drills/*   apps/web/src/features/settings/*
apps/web/src/app/writing/page.tsx  apps/web/src/app/practice/new/page.tsx
apps/web/src/app/drills/page.tsx   apps/web/src/app/settings/page.tsx
apps/web/tests/features/{writing,custom-scenarios,drills,settings}/*.test.tsx
apps/web/e2e/{writing,custom-scenario,drills,settings}.spec.ts
docs/tasks/q1-exit-review.md
```

---

### Task 6.1 — Writing coach API

**Goal:** `POST /writing/rewrite`, `GET /writing/rewrites`, `DELETE /writing/rewrites/{id}`.
**Depends on:** Phase 5
**Files:** `app/models/writing.py` (migration `0008_writing_rewrites`), `app/llm/prompts/rewrite.md.j2`,
`app/llm/{outputs,fake_outputs}.py`, `app/schemas/writing.py`, `app/services/writing.py`,
`app/api/v1/writing.py`. Test `tests/integration/api/test_writing.py`, extend
`tests/unit/llm/test_prompts.py`.

**Interfaces (produces):**
```python
async def rewrite(db, user: User, data: RewriteIn, llm: LLMService) -> RewriteOut
async def list_rewrites(db, user_id, *, limit, cursor) -> Page[RewriteHistoryItem]
async def delete_rewrite(db, user_id, rewrite_id) -> None
```
Prompt requirements (`rewrite.md.j2`): role = editor for engineers' workplace messages; keep the
author's meaning, facts, names, code snippets and links unchanged; channel rules — `slack`:
short paragraphs, no formal greeting/sign-off unless present; `email`: greeting + sign-off,
clear subject-like first line if missing; `pr_description`: sections "Summary", "Changes",
"Testing" in Markdown; `other`: neutral; goal rules — `clearer`: main point first; `shorter`:
cut ≥ 30 % without losing facts; `more_polite`: soften without hedging excessively;
`more_assertive`: direct requests and commitments, remove apologies; adapt vocabulary to the
learner's English level; output always in English (input in another language is rewritten into
English — spec D23); input wrapped in `<user_text>`; context in `<context>`.

**Subtasks:**
- [ ] 6.1.1 Failing tests: happy path saves and returns output + changes; each validation limit
  (empty text, > 4,000 chars, unknown channel/goal, context > 500) → 422; LLM unavailable → 503
  and nothing saved; invalid output → 502; history paginates; delete own → 204; delete other's →
  404; usage recorded with `feature="rewrite"`; prompt contains the channel and goal rules
  (template test).
- [ ] 6.1.2 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 6.1.3 Manual check with Ollama on 3 real-looking inputs (a rambling Slack message, a blunt
  email, a PR description without structure); note quality in the completion log.
- [ ] 6.1.4 Commit: `feat(api): add writing coach`

---

### Task 6.2 — Web: writing coach page

**Goal:** `/writing` form, result and history.
**Depends on:** 6.1
**Files:** `src/features/writing/*`, `src/app/writing/page.tsx`; enable "Writing" in the shell.

**Behaviour:** channel select (Slack / Email / PR description / Other); goal segmented control;
optional context input (collapsed by default); textarea with counter (4,000); "Improve" button
(disabled when empty; spinner while pending). Result: before/after side by side on wide screens
(stacked on narrow), "Copy" button (with "Copied" feedback), list of changes (what → why), tone
note. History below: date, channel, goal, first line of the input; click to reopen; delete with
confirm. PR descriptions render the output as a Markdown preview with a "Raw" toggle — add
`pnpm --filter web add react-markdown` (no raw HTML rendering; default safe settings).

**Subtasks:**
- [ ] 6.2.1 Failing tests: submit sends the right payload; result renders changes and tone note;
  copy writes to the clipboard (mock); history reopen; delete; validation counter; error states.
- [ ] 6.2.2 Run → FAIL. Implement. Run → PASS. Commit: `feat(web): add writing coach page`

---

### Task 6.3 — Custom scenarios API

**Goal:** Draft, save and delete user-owned scenarios.
**Depends on:** Phase 5
**Files:** `app/llm/prompts/custom_scenario.md.j2`, outputs/fake outputs,
`app/schemas/scenario.py` (draft in/out), `app/services/custom_scenarios.py`,
`app/api/v1/scenarios.py`. Test `tests/integration/api/test_custom_scenarios.py`.

**Interfaces (produces):**
```python
async def draft_custom_scenario(user: User, description: str, llm: LLMService) -> ScenarioDraft
async def save_custom_scenario(db, user_id, draft: ScenarioDraft) -> ScenarioDetail
    # slug = f"custom-{secrets.token_hex(4)}" (retry on collision); is_custom=True; owner_user_id=user_id;
    # rubric_version="v1"; keyterms=[]; content_hash=None
async def delete_custom_scenario(db, user_id, scenario_id) -> None    # 404 for built-ins and others' scenarios
```
`ScenarioDraft` (API model) has the same fields and limits as `ScenarioDraftOut` so the user can
edit before saving. Prompt: turn the user's description into a realistic counterpart persona who
behaves like the real person would (push back where plausible), an objective phrased as what the
user wants to achieve, an in-character opening line, 3–4 success criteria; never include real
personal data beyond first names given by the user; description wrapped in `<user_text>`.
Limit: max 50 custom scenarios per user (beyond that → 409 `limit_reached`, message "You can keep up to 50 custom scenarios. Delete one to add another.").

**Subtasks:**
- [ ] 6.3.1 Failing tests: draft returns a validated draft and saves nothing; description length
  limits; save creates a scenario visible in `GET /scenarios?owner=mine` and startable via
  `POST /sessions`; other users can't see or start it (404); delete removes it and its sessions
  (cascade); deleting a built-in → 404; 51st scenario → 409 `limit_reached`; usage recorded
  (`feature="custom_scenario"`).
- [ ] 6.3.2 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 6.3.3 Commit: `feat(api): add custom scenarios`

---

### Task 6.4 — Web: create your own scenario

**Goal:** `/practice/new` flow and "My scenarios" in the library.
**Depends on:** 6.3
**Files:** `src/features/custom-scenarios/*`, `src/app/practice/new/page.tsx`; library gets a
"Create your own" button and an owner filter (All / Built-in / Mine); detail page shows "Delete"
for custom scenarios.

**Behaviour:** step 1 describe (textarea 20–1,000 chars, example placeholder: "Tomorrow I need to
tell my PM that the search feature will be two weeks late because the vendor API changed…") →
"Draft scenario" → step 2 editable preview form (all fields, with limits) → "Save and practise"
(saves, then opens the detail page) or "Start over". Delete asks for confirmation and warns that
its practice history will be deleted too.

**Subtasks:**
- [ ] 6.4.1 Failing tests: draft → preview populated; editing fields; save navigates; validation
  messages; delete confirmation; owner filter query.
- [ ] 6.4.2 Run → FAIL. Implement. Run → PASS. Commit: `feat(web): add custom scenario creation`

---

### Task 6.5 — Drills: pre-recorded transcription, model, generation

**Goal:** Three drills per local day, generated lazily, personalised, with a reliable fallback.
**Depends on:** Phase 5
**Read before starting:** ADR-0013 (pre-recorded method), `voice-and-pronunciation.md` §5.
**Files:** `app/voice/deepgram_prerecorded.py`, `app/voice/fake.py`, `app/deps.py`
(`get_prerecorded`, lazy like `get_stt`), `app/models/drill.py` (migration `0009_drills`, also adds
`skill_scores.drill_id`), `content/drills/templates.yaml`,
`app/content/drill_templates.py`, `app/llm/prompts/drill_generate.md.j2`, outputs/fake outputs,
`app/schemas/drill.py`, `app/services/drills.py`. Tests
`tests/unit/voice/test_deepgram_prerecorded.py`, `tests/unit/services/test_drill_composition.py`,
`tests/integration/api/test_drills.py` (generation part).

**Interfaces (produces):**
```python
# app/services/drills.py
@dataclass(frozen=True)
class DrillSlot: position: int; kind: DrillKind; answer_mode: AnswerMode; target_dimension: str; coach_note_id: UUID | None
def compose_slots(*, top_note: CoachNote | None, weak_words: list[str],
                  rephrase_source: Highlight | None) -> list[DrillSlot]      # pure, always 3 slots
async def get_or_create_today(db, user: User, llm: LLMService) -> TodayDrillsOut
```
Composition rules (`compose_slots`):
- Slot 0: if `top_note` exists → `explain_concept` (voice) targeting the note's dimension (if the
  note's dimension is `pronunciation`, use slot rules of slot 1 instead and pick the next note);
  else `explain_concept` (voice) targeting `clarity`.
- Slot 1: if `weak_words` (≥ 1, from pronunciation notes / recent attempts) → `pronunciation`
  (answer_mode `pronunciation`, payload = up to 3 sentence ids containing those words, falling back
  to `tech-terms-1` sentences); else `filler_free_minute` (voice) targeting `fluency`.
- Slot 2: if `rephrase_source` (a highlight from the last 14 days) → `rephrase` (text) targeting
  `clarity`, payload `{ "original": quote, "issue": issue }`; else `explain_concept` (text)
  targeting `conciseness`.
Generation: LLM `DrillBatch` fills titles/prompts for the non-pronunciation slots (topic ideas from
the user's goals, seniority and notes); on any LLM error or invalid output, use
`templates.yaml` (≥ 10 templates per kind, chosen deterministically by
`hash(user_id, date, position)`) — **the drills page must always work**. Generation is
idempotent per (user, local date) — concurrent requests use the unique constraint and re-read on
conflict.

**Subtasks:**
- [ ] 6.5.1 Failing unit tests: `compose_slots` for every rule combination (table-driven);
  pre-recorded adapter (mocked SDK/HTTP): maps words incl. fillers; error → `SpeechUnavailableError`;
  > 90 s rejected before calling; the request carries `mip_opt_out=true` (options from
  `deepgram_request_options()`).
- [ ] 6.5.2 Failing integration tests: first `GET /drills/today` creates 3 drills; second call
  returns the same ids; local date uses the profile timezone; LLM failure → template drills (still
  3); pronunciation slot payload has valid sentence ids; concurrency (two parallel calls → 3 rows
  total).
- [ ] 6.5.3 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 6.5.4 Commit: `feat(api): generate personalised daily drills`

---

### Task 6.6 — Drill answers and scoring

**Goal:** Complete drills by text, voice or pronunciation attempts; skip; scores feed progress and
streaks.
**Depends on:** 6.5
**Files:** `app/services/drill_scoring.py`, `app/services/drills.py`, `app/api/v1/drills.py`,
`app/llm/prompts/drill_feedback.md.j2`, `app/services/activity.py`, `app/services/progress.py`.
Tests `tests/unit/services/test_drill_scoring.py`, `tests/integration/api/test_drills.py`.

**Interfaces (produces):**
```python
def score_filler_free_minute(metrics: VoiceMetrics) -> DrillResult      # score = fluency_score; feedback from fluency_reason; speaking < 30 s → score 1 + "Try to speak for the full minute."
def score_pronunciation_drill(attempts: list[PronunciationAttempt]) -> DrillResult   # mean pron_score → 1–5 via bands 0–39:1, 40–59:2, 60–74:3, 75–89:4, 90+:5
async def complete_text(db, user, drill_id, answer: str, llm) -> DrillOut
async def complete_voice(db, user, drill_id, wav: bytes, transcriber, llm) -> DrillOut
    # validate + load, commit, then transcribe / call the LLM, then save (no connection held during provider calls)
    # explain_concept (voice): transcribe → metrics → LLM DrillFeedback on the transcript (+ metrics in result)
    # filler_free_minute: transcribe → metrics → score_filler_free_minute (no LLM)
async def complete_pronunciation(db, user, drill_id, attempt_ids: list[UUID]) -> DrillOut
    # attempts must be the user's, purpose=drill, for the drill's payload sentences, created today
async def skip(db, user_id, drill_id) -> DrillOut
```
On completion: `status=completed`, `result`, `completed_at`, one `skill_scores` row
(`source=drill`, `dimension=target_dimension`, `score=to_score_100(result.score)`, `scorer` =
the LLM's `<provider>:<model>` for text and `explain_concept` drills, `metrics:v1` for
`filler_free_minute`, `<assessor>:pronunciation` for pronunciation drills), usage
recorded. Completing an already completed/skipped drill → 409 `drill_already_finished`
("This drill is already finished."). Wrong answer mode for the endpoint → 422 `validation_error`.
`activity.active_local_dates` now includes `drills.completed_at`; `progress.drills_completed`
counts completed drills.

**Subtasks:**
- [ ] 6.6.1 Failing unit tests for both scoring functions (bands, short speech rule).
- [ ] 6.6.2 Failing integration tests: text completion (fake `DrillFeedback`); voice completion for
  both voice kinds (fake transcriber); invalid WAV → 400; pronunciation completion validations
  (other user's attempt, wrong sentence, wrong purpose → 422); skip; double completion → 409;
  skill score written with the right `scorer`; the pronunciation attempts made for a drill wrote
  no skill scores of their own; streak counts a drill-only day; `drills_completed` in summary.
- [ ] 6.6.3 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 6.6.4 Commit: `feat(api): score drill answers`

---

### Task 6.7 — Web: drills page

**Goal:** `/drills` with three interactive drill cards.
**Depends on:** 6.6
**Files:** `src/features/drills/*`, `src/app/drills/page.tsx`; enable "Drills" in the shell and
the dashboard action. Reuse `useSentenceRecorder` (max 90 s for voice drills, 30 s for sentences)
and the pronunciation result components.

**Behaviour:** header "Today's drills" with date and "2 of 3 finished" (completed or skipped);
each card shows kind label,
title, prompt, target skill, and:
- text → textarea + "Submit";
- voice → record (with timer; `filler_free_minute` shows a 60 s countdown target) + "Submit";
- pronunciation → the 1–3 sentences with inline record/result (each posts an attempt with
  `purpose=drill`), then "Finish drill";
- "Skip" (secondary). Completed cards show score (1–5 dots), feedback, better version (if any),
  and speaking stats for voice drills. When all three are done: a short celebration message and a
  link to Progress.

**Subtasks:**
- [ ] 6.7.1 Failing tests: renders three kinds; submit flows per kind; skip; completed state;
  "N of 3 finished" counts completed and skipped drills; all-done message; error mapping
  (`invalid_audio`, `speech_unavailable`).
- [ ] 6.7.2 Run → FAIL. Implement. Run → PASS. Commit: `feat(web): add daily drills page`

---

### Task 6.8 — Web: settings page

**Goal:** `/settings` for practice preferences, voice and microphone. (Profile editing and
timezone detection are **not** part of Q1 — owner decision D22; they arrive in Phase 7, Task 7.7.
Structure the page with sections so Q2 can add Profile, Reminders and AI keys.)
**Depends on:** Phase 3 (voices), Phase 5
**Files:** `src/features/settings/*`, `src/app/settings/page.tsx`; enable "Settings".

**Behaviour:**
- Practice: default mode, voice input style (with a short explanation of each). Save with toast;
  field errors from `validation_error.details.fields`.
- Voice: list from `GET /voices` with "Play sample" (`/tts/preview`, fixed sample sentence) and a
  selected state; speed control only if ADR-0013 confirmed support.
- Microphone test: "Test microphone" → live level meter for 10 s + "We can hear you" when RMS
  crosses a threshold; permission error help.
- "About your data (local mode)": explains that everything is stored locally, audio isn't stored,
  which services receive audio/text (Deepgram — opted out of model training, Azure, Ollama
  locally), and that the profile uses defaults (English level B2, timezone UTC) until accounts
  arrive.

**Subtasks:**
- [ ] 6.8.1 Failing tests: loads current values; partial PATCH on save; validation errors shown
  on fields; voice preview requests the right URL; mic test shows the success message with a fake
  source; no profile fields are rendered.
- [ ] 6.8.2 Run → FAIL. Implement. Run → PASS. Commit: `feat(web): add settings page`

---

### Task 6.9 — E2E journeys and Q1 exit review

**Goal:** Remaining journeys covered; Q1 verified end to end with real providers.
**Depends on:** 6.2, 6.4, 6.7, 6.8
**Files:** `apps/web/e2e/{writing,custom-scenario,drills,settings}.spec.ts`,
`docs/tasks/q1-exit-review.md`.

**Subtasks:**
- [ ] 6.9.1 Specs (fake providers):
  - writing: paste text → Improve → result + changes → appears in history.
  - custom scenario: describe → draft → edit title → save → start text practice → opening line shown.
  - drills: open Drills → record the first drill (always voice) → skip the second (its kind
    depends on existing data) → answer the third (always text) → "3 of 3 finished".
  - settings: change default mode and voice input style → reload → values persist; voice sample
    plays (request observed).
- [ ] 6.9.2 `make test-e2e` (all specs) → PASS.
- [ ] 6.9.3 Q1 exit review with real providers (Ollama + Deepgram + Azure) — create
  `docs/tasks/q1-exit-review.md` with a checklist and results for product-spec journeys 1–7, the
  quality bar in `product-spec.md` §6 (measured latencies, eval summary, coverage from
  `uv run pytest --cov=app`), open follow-ups from all completion logs, and known limitations
  (at least: no profile screen — defaults B2/UTC until Phase 7; all AI output in English and
  native language unused (D23); Ollama quality gap from ADR-0012).
- [ ] 6.9.4 Request a code review of the whole Q1 diff (`code-review` skill) and fix blocking
  findings.
- [ ] 6.9.5 Update `docs/tasks/README.md` (Phase 6 done, Q1 exit recorded), `AGENTS.md` status,
  and `README.md` (features now available). Summarise Q1 to the owner. Commit:
  `docs: record q1 exit review`

## Phase verification

1. Each new feature works with real Ollama (quality notes recorded) and fails gracefully with
   Ollama stopped (templates keep drills working).
2. Streak increases from a drill-only day.
3. `make check`, `make test-e2e` → PASS; Q1 exit review complete and shared with the owner.

## Completion log

<!-- Append: - YYYY-MM-DD · Task N.M · commits · evidence · Notes · Follow-ups -->
