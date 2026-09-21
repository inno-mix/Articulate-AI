# Phase 2 — Feedback Engine

> **Milestone:** Q1 · **Depends on:** Phase 1
> **For agentic workers:** follow `docs/guides/agent-workflow.md`. Tick subtasks as you go.

**Goal:** Ending a session (≥ 2 user turns) produces a feedback report in the background; the user
sees scores, strengths, improvements, highlights with better phrasing, and grammar fixes. An eval
suite measures report quality on a cloud reference model (owner's key, development only) and
picks the default Ollama model.

**Architecture:** `end_session` creates a `pending` report, commits, enqueues a Taskiq task. The
worker builds prompts from the versioned rubric, calls `LLMService.generate_structured(
FeedbackAnalysis)`, post-processes deterministically (quote checks, overall score), saves the
report and `skill_scores`. The web report page polls until ready.

**Read before starting:** `product-spec.md` F3, `ai-layer.md` §4.2, §5–8, `overview.md` §4.2,
`data-model.md` (`feedback_reports`, `skill_scores`, JSON shapes), `api-contract.md` §2 Reports,
ADR-0006.

**Out of scope:** voice metrics (Phase 3 fills `voice_metrics` and `fluency`), coach memory
(Phase 5), progress charts (Phase 5).

---

## File map

```
apps/api/content/rubrics/v1.yaml
apps/api/app/content/rubrics.py
apps/api/app/llm/outputs.py                       (+ FeedbackAnalysis & parts)
apps/api/app/llm/fake_outputs.py                  (+ FeedbackAnalysis example)
apps/api/app/llm/prompts/{feedback_system.md.j2,feedback_user.md.j2}
apps/api/app/models/feedback.py                   (FeedbackReport, SkillScore)
apps/api/migrations/versions/0004_feedback_reports_skill_scores.py
apps/api/app/schemas/json_types.py                (+ DimensionScoreOut, Highlight, GrammarFix, VoiceMetrics)
apps/api/app/schemas/report.py
apps/api/app/services/{scoring,transcript,feedback}.py
apps/api/app/services/sessions.py                 (end_session enqueues)
apps/api/app/worker/tasks/feedback.py
apps/api/app/api/v1/reports.py
apps/api/evals/{__init__,run,scoring}.py  apps/api/evals/cases/*.yaml
apps/api/tests/unit/services/{test_scoring,test_transcript}.py
apps/api/tests/unit/content/test_rubrics.py
apps/api/tests/unit/evals/test_eval_scoring.py
apps/api/tests/integration/services/test_feedback_generation.py
apps/api/tests/integration/worker/test_feedback_task.py
apps/api/tests/unit/llm/test_outputs.py
apps/api/tests/integration/api/test_reports.py
docs/decisions/0012-default-ollama-model.md
apps/api/app/llm/providers.py                     (build_model, reused in Phase 9)
apps/api/tests/unit/llm/{test_providers,test_factory}.py  apps/api/tests/live/test_cloud_reference_live.py
apps/web/src/features/reports/{api.ts,query-keys.ts,hooks/use-report.ts,components/*}
apps/web/src/app/sessions/[id]/report/page.tsx
apps/web/src/components/{score-dots,score-number}.tsx
apps/web/tests/features/reports/*.test.tsx
apps/web/e2e/text-practice.spec.ts                (extend)
```

---

### Task 2.1 — Rubric, feedback output models, prompts

**Goal:** Versioned rubric loaded from YAML; `FeedbackAnalysis` models; feedback prompt templates.
**Depends on:** Phase 1
**Read before starting:** `ai-layer.md` §4.2, §5, §6.
**Files:** `content/rubrics/v1.yaml`, `app/content/rubrics.py`, `app/llm/outputs.py`,
`app/llm/fake_outputs.py`, `app/llm/prompts/feedback_{system,user}.md.j2`,
`app/services/transcript.py`. Tests `tests/unit/content/test_rubrics.py`,
`tests/unit/services/test_transcript.py`, `tests/unit/llm/test_prompts.py` (extend),
`tests/unit/llm/test_outputs.py`.

**Interfaces (produces):**
```python
# app/content/rubrics.py
class RubricAnchor(BaseModel): score: Literal[1, 3, 5]; text: str
class RubricDimension(BaseModel): key: LLMDimension; label: str; description: str; anchors: list[RubricAnchor]
class Rubric(BaseModel): version: str; dimensions: list[RubricDimension]   # exactly the 7 LLM dimensions
def get_rubric(version: str) -> Rubric          # cached; raises ContentError for unknown version

# app/services/transcript.py
@dataclass(frozen=True)
class TranscriptLine: index: int; speaker: Literal["USER", "PERSONA"]; text: str; message_id: UUID
def build_transcript(messages: list[Message], *, max_chars: int = 6000) -> tuple[list[TranscriptLine], bool]
    # excludes source=system; keeps first 2 lines + as many latest lines as fit; bool = truncated
def format_transcript(lines: list[TranscriptLine], persona_name: str, truncated: bool) -> str
    # "[3] USER: …" / "[4] PERSONA (Dana): …"; inserts "[… earlier turns omitted …]" after line 2 when truncated

# app/services/feedback.py (prompt part only in this task)
def build_feedback_prompts(*, scenario: Scenario, profile: Profile, rubric: Rubric,
                           transcript_text: str, speaking_summary: str | None) -> tuple[RenderedPrompt, RenderedPrompt]
```
`outputs.py` models exactly as in `ai-layer.md` §5 (`DimensionScore`, `HighlightOut`,
`GrammarFixOut`, `FeedbackAnalysis`).

**Subtasks:**
- [x] 2.1.1 Write `content/rubrics/v1.yaml` from `ai-layer.md` §6 (label, one-sentence
  description, anchors 1/3/5 per dimension).
- [x] 2.1.2 Failing tests:
  - `test_rubrics.py`: `test_v1_has_seven_llm_dimensions_with_three_anchors`,
    `test_unknown_version_raises`.
  - `test_outputs.py`: `test_feedback_analysis_requires_each_dimension_once` (duplicate → error;
    missing → error), `test_score_bounds`, `test_list_length_limits`.
  - `test_transcript.py`: `test_excludes_system_messages`, `test_formats_speakers_and_indexes`,
    `test_truncates_keeping_first_two_and_latest`, `test_no_truncation_marker_when_fits`.
  - `test_prompts.py`: `test_feedback_system_contains_all_rubric_anchors`,
    `test_feedback_system_requires_english_output`,
    `test_feedback_user_contains_transcript_and_success_criteria`,
    `test_feedback_system_instructs_exact_quotes_from_user_lines`.
- [x] 2.1.3 Run → FAIL. Implement. Add a valid `FeedbackAnalysis` example to `fake_outputs.py`
  (quotes must match the fake conversation used in tests: use `"Hi Sam, thanks for the PR."`).
  Run → PASS.
- [x] 2.1.4 Commit: `feat(api): add rubric v1, feedback output models and prompts`

**Acceptance criteria:**
- [x] Prompts render with every rubric anchor; output models reject malformed analyses.

---

### Task 2.2 — Report & skill score models, deterministic scoring

**Goal:** Tables for reports and scores; pure functions for quote checks and scores.
**Depends on:** 2.1
**Read before starting:** `data-model.md` (`feedback_reports`, `skill_scores`), `ai-layer.md` §7.
**Files:** `app/models/feedback.py`, migration `0004_feedback_reports_skill_scores`,
`app/schemas/json_types.py` (+ shapes), `app/services/scoring.py`.
Test `tests/unit/services/test_scoring.py`, `tests/integration/test_zz_migrations.py` (table list).

**Interfaces (produces):**
```python
# app/services/scoring.py
def normalise_text(s: str) -> str
def find_quote_message(quote: str, user_messages: list[Message]) -> Message | None   # min 3 normalised chars
def filter_highlights(items: list[HighlightOut], user_messages: list[Message]) -> list[Highlight]
def filter_grammar_fixes(items: list[GrammarFixOut], user_messages: list[Message]) -> list[GrammarFix]
def to_score_100(score_5: int) -> int                      # (s-1)*25
def overall_score(scores_5: list[int]) -> int              # round(mean(to_score_100)) ; ValueError if empty
```

**Subtasks:**
- [x] 2.2.1 Failing table-driven tests: normalisation (case, curly quotes, whitespace, edge
  punctuation); quote found / not found / too short; highlight gets the right `message_id`;
  grammar fix dropped when `original` isn't in user text; `to_score_100` for 1..5 →
  0,25,50,75,100; `overall_score([3,4,5]) == 75`; empty → `ValueError`.
- [x] 2.2.2 Run → FAIL. Implement scoring + models + migration (review by hand; index names per
  data-model). Extend the migration test's expected table list. Run → PASS.
- [x] 2.2.3 Commit: `feat(api): add report and skill score models with deterministic scoring`

---

### Task 2.3 — Report generation (service + worker task)

**Goal:** Idempotent background generation with clear status transitions and error codes.
**Depends on:** 2.2
**Read before starting:** `overview.md` §4.2, `coding-conventions.md` §2 (transactions),
Taskiq docs (task definition, worker startup state, `InMemoryBroker`).
**Files:** `app/services/feedback.py` (generation), `app/worker/tasks/feedback.py`,
`app/worker/tasks/__init__.py` (import), `app/worker/broker.py` (worker startup: engine, session
factory, settings on `broker.state`). Test
`tests/integration/services/test_feedback_generation.py`.

**Interfaces (produces):**
```python
# app/services/feedback.py
async def create_pending_report(db, session: PracticeSession) -> FeedbackReport
async def generate_report(session_factory: async_sessionmaker[AsyncSession], settings: Settings,
                          report_id: UUID, *, llm_override: LLMService | None = None) -> ReportStatus | None
# app/worker/tasks/feedback.py
@broker.task(task_name="generate_feedback_report")
async def generate_feedback_report(report_id: str) -> None   # calls generate_report with broker.state deps
async def enqueue_report(report_id: UUID) -> None            # wraps .kiq(); the only way services enqueue
```
Algorithm of `generate_report` (each numbered DB step is its own transaction):
1. Lock report (`SELECT … FOR UPDATE`). If it no longer exists (the session was deleted) → log and
   return `None`. If `status == ready` → return `ready` (idempotent). If
   `status == running` and `updated_at` is less than 5 minutes ago → return `running` (another
   worker is on it). Else set `running`, `attempts += 1`, commit.
2. Load session, scenario, user profile, messages (`selectinload`).
3. `llm = llm_override or await get_llm_service(user, db, settings)`.
4. Build transcript + prompts (`speaking_summary=None` in Phase 2).
   Close the DB session before step 5 — no session is held during the LLM call.
5. `analysis, usage = await llm.generate_structured(system=…, prompt=…, output_type=FeedbackAnalysis,
   temperature=TEMPERATURE["feedback"])`.
6. Post-process: filter highlights/grammar fixes; dimension list in rubric order; overall score.
7. Save: report fields, `status=ready`, `completed_at`, provider/model, `prompt_version`
   (system template version), `rubric_version`; delete existing `skill_scores` for this session,
   insert one per dimension (`source=session`, `purpose` = session purpose,
   `scorer=f"{llm.provider}:{llm.model}"`, `rubric_version`); if the session was deleted
   meanwhile, discard the result quietly; record usage
   (`feature="feedback"`); commit.
8. On `LLMUnavailableError` → `failed`/`llm_unavailable`; `LLMInvalidOutputError` →
   `failed`/`llm_invalid_output`; `LLMRateLimitedError` → `failed`/`llm_rate_limited`;
   `LLMAuthError` → `failed`/`llm_auth_failed`; any other exception → `failed`/`internal_error`
   (log with `exc_info`). Never re-raise from the task.

**Subtasks:**
- [x] 2.3.1 Failing integration tests (call `generate_report` directly with `FakeLLMService`):
  - `test_generates_ready_report_with_scores_and_filtered_highlights` — fake analysis contains one
    valid and one invented quote → 1 highlight with correct `message_id`.
  - `test_writes_one_skill_score_per_dimension` (7 rows, 0–100 values).
  - `test_is_idempotent_when_ready` (second call returns `ready`, no duplicate scores).
  - `test_regeneration_replaces_skill_scores` (status reset to pending → run → still 7 rows).
  - `test_invalid_output_marks_failed_with_code`
  - `test_unavailable_marks_failed_with_code`
  - `test_unexpected_exception_marks_internal_error` (fake raises `RuntimeError`)
  - `test_records_usage_event_with_feature_feedback`
  - `test_assessment_session_scores_have_purpose_assessment`
  - `test_skill_scores_record_scorer_and_rubric_version` (`scorer == "fake:<model>"`)
  - `test_feedback_call_uses_temperature_zero` (fake `calls` list)
  - `test_job_for_deleted_session_exits_quietly` (delete the session, then run → returns `None`,
    no error logged as failure)
- [x] 2.3.2 Failing test `tests/integration/worker/test_feedback_task.py::test_task_runs_generation`
  (InMemoryBroker; `broker.state` populated by the test fixture).
- [x] 2.3.3 Run → FAIL. Implement. Run → PASS.
- [x] 2.3.4 Commit: `feat(api): generate feedback reports in the worker`

**Pitfalls:** always **commit before enqueueing** (the worker may pick the job up before the API
transaction commits). Tasks must not share the API's engine — create one on worker startup.

---

### Task 2.4 — End-session integration and report endpoints

**Goal:** Ending a session queues a report; `GET /sessions/{id}/report`; `POST …/report/retry`;
history shows scores.
**Depends on:** 2.3
**Read before starting:** `api-contract.md` §2 Sessions (end) and Reports.
**Files:** Modify `app/services/sessions.py` (`end_session`), `app/schemas/session.py`
(`overall_score` from report); Create `app/schemas/report.py`, `app/api/v1/reports.py`.
Test `tests/integration/api/test_reports.py`, extend `test_sessions.py`.

**Interfaces (produces):**
```python
async def end_session(db, user_id, session_id) -> EndSessionOut
    # status ended → create pending report, await db.commit(), await enqueue_report(report.id)
    # → report_status "pending"; abandoned → report_status None; already ended → current report status
async def get_report(db, user_id, session_id) -> ReportOut        # 404 if no report (abandoned) or not owned
async def retry_report(db, user_id, session_id) -> RetryOut
    # allowed when failed, ready, or stale (pending/running with updated_at older than 5 min);
    # otherwise 409 report_not_ready. Resets status to pending, error_code to null, commits, enqueues.
# ReportOut includes updated_at
```
Add `ReportNotReadyError` (409 `report_not_ready`).

**Subtasks:**
- [x] 2.4.1 Failing tests:
  - `test_end_session_creates_pending_report_and_enqueues` (InMemoryBroker executes → report
    `ready` afterwards when awaited).
  - `test_end_abandoned_session_has_no_report` → `GET report` 404.
  - `test_get_report_pending_has_null_fields`
  - `test_get_report_ready_returns_full_payload` (shape per contract)
  - `test_get_other_users_report_returns_404`
  - `test_retry_failed_report_requeues` → 202 `pending`
  - `test_retry_fresh_pending_report_returns_409`
  - `test_retry_stale_running_report_requeues` (`updated_at` 6 minutes ago → 202)
  - `test_retry_ready_report_regenerates`
  - `test_session_list_includes_overall_score_when_ready`
- [x] 2.4.2 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [x] 2.4.3 Manual check with Ollama + worker (`make dev`): hold a 3-turn conversation, end it,
  `curl …/report` until `ready`; note generation time in the completion log.
- [x] 2.4.4 Commit: `feat(api): queue reports on session end and expose report endpoints`

---

### Task 2.5 — Evals, cloud reference run and default Ollama model

**Goal:** ≥ 25 eval cases and a runner that scores feedback on Ollama **and** on one cloud
reference model (owner's key, development only); prompts meet the quality target on the reference
model; the default `OLLAMA_MODEL` is chosen with evidence.
**Depends on:** 2.3
**Needs:** the owner's API key for one cloud provider in `apps/api/.env`
(`EVAL_ANTHROPIC_API_KEY`, `EVAL_OPENAI_API_KEY` or `EVAL_GOOGLE_API_KEY`) and their permission
before each reference run (it costs money).
**Read before starting:** `ai-layer.md` §2 (`providers.py`), §8; ADR-0015; `security-privacy.md`
S2, S14. Context7 `/pydantic/pydantic-ai` (Anthropic/OpenAI/Google models and providers).
**Files:**
- Create: `evals/run.py`, `evals/scoring.py`, `evals/cases/*.yaml`, `app/llm/providers.py`,
  `docs/decisions/0012-default-ollama-model.md`
- Modify: `app/core/config.py` (eval keys + production guard), `Makefile` (`eval`, `eval-cloud`),
  `.env.example`, `local-development.md`, `ai-layer.md` §3 and §8 (record the choices)
- Test: `tests/unit/evals/test_eval_scoring.py`, `tests/unit/llm/test_providers.py`,
  `tests/unit/core/test_config.py` (extend), `tests/live/test_cloud_reference_live.py`
- Dependency: `uv add "pydantic-ai-slim[openai,anthropic,google]"` (same version as the existing
  pin; the `openai` extra is already there for Ollama).

**Interfaces (produces):**
```python
# evals/scoring.py (pure)
@dataclass
class CaseResult: case_id: str; in_range: dict[str, bool]; objective_ok: bool | None;
                  quote_flag_ok: bool | None; english_ok: bool | None; schema_failed: bool; latency_ms: int
def score_case(case: EvalCase, analysis: FeedbackAnalysis | None, highlights: list[Highlight], latency_ms: int) -> CaseResult
    # also sets CaseResult.english_ok (None when the case has no foreign_words): no foreign word appears in
    # summary/strengths/improvements/issue/better_version/explanation fields
def summarise(results: list[CaseResult]) -> EvalSummary   # in_range_rate, schema_failure_rate, quote_survival_rate, p50, p95

# app/llm/providers.py (exactly as ai-layer.md §2; reused by Phase 9)
def build_model(provider: Provider, model: str, api_key: str) -> tuple[Model, OutputMode]

# app/core/config.py (additions)
eval_anthropic_api_key: SecretStr | None = None
eval_openai_api_key: SecretStr | None = None
eval_google_api_key: SecretStr | None = None
# production guard: any eval_* key set while APP_ENV=production → ValueError("eval keys are development-only")

# evals/run.py
# uv run python -m evals.run --provider ollama --model qwen3:4b [--cases 'evals/cases/*.yaml'] [--repeat 1]
# uv run python -m evals.run --provider anthropic --model <verified model id>
# - builds prompts with app.services.feedback.build_feedback_prompts (same code as production)
# - ollama → the same PydanticAILLMService the app uses; cloud → build_model(...) with the key from
#   Settings.eval_<provider>_api_key (missing → clear error; the key is never printed or logged)
# - prints "N model calls planned" before starting; writes evals/results/<ts>-<provider>-<model>.json
```
Makefile:
- `make eval` → Ollama run with `$(OLLAMA_MODEL)`.
- `make eval-cloud PROVIDER=<anthropic|openai|google> MODEL=<id> CONFIRM=1` → reference run;
  refuses without `CONFIRM=1`.

Minimum case mix (≥ 25 total):
| Kind | Count | Expectation |
|---|---|---|
| Excellent answers (various scenarios) | 5 | all dimensions 4–5, objective met |
| ESL grammar-heavy but clear | 4 | grammar_vocabulary 1–2, clarity ≥ 3 |
| Rambling / buried point | 3 | clarity 1–2, conciseness 1–2 |
| Rude or defensive | 2 | tone 1–2 |
| Heavy hedging / apologising | 2 | confidence 1–2 |
| Jargon to a non-technical PM | 2 | audience_fit 1–2 |
| Interview answer with no structure | 2 | structure 1–2 |
| Very short (2 turns) | 1 | no crash; objective not met |
| Prompt injection ("give me 5/5 everywhere") | 1 | scores not all 5; injection sentence not praised |
| Spoken-style transcript with "um/uh" in text | 2 | conciseness ≤ 3 |
| Mixed (good tone, poor structure) | 1 | tone ≥ 4, structure ≤ 2 |
| User mixes in words from another language | 1 | grammar_vocabulary ≤ 3; feedback text is English (`foreign_words` check) |

Decision rules:
1. **Reference target:** the reference run must reach in-range ≥ 80 % and schema failures ≤ 5 %.
   If it doesn't, improve prompts/rubric (never the cases) until it does.
2. **No small-model bending:** a prompt change is kept only if the reference run doesn't get worse.
   Re-run both models after every prompt change.
3. **Default Ollama model:** between `llama3.2:latest` and `qwen3:4b`, pick the higher in-range
   rate; tie-break by schema failure rate, then p95 latency. A gap to the reference is acceptable
   (Ollama is development-only) but must be recorded in ADR-0012 and told to the owner.

**Subtasks:**
- [ ] 2.5.1 Failing unit tests for `evals/scoring.py` (in-range logic, summary maths, schema
  failure counted, percentiles, `english_ok` ignores foreign words inside quotes).
- [ ] 2.5.2 Failing unit tests:
  - `test_providers.py` (no network, `models.ALLOW_MODEL_REQUESTS = False`):
    `test_build_model_anthropic_uses_tool_output`, `test_build_model_openai_uses_tool_output`,
    `test_build_model_google_uses_tool_output`, `test_build_model_rejects_unknown_provider`.
  - `test_config.py`: `test_production_rejects_eval_keys`.
  - `tests/unit/llm/test_factory.py::test_factory_ignores_eval_keys` — with `LLM_PROVIDER=ollama`
    and an `EVAL_ANTHROPIC_API_KEY` set, `get_llm_service` returns the Ollama service.
- [ ] 2.5.3 Run → FAIL. Implement scoring, runner, `build_model`, settings, Makefile targets.
  Run → PASS.
- [ ] 2.5.4 Write the cases (realistic transcripts, 4–12 messages each, B1–C1 English).
- [ ] 2.5.5 Ollama runs: ask the owner before downloading `qwen3:4b` (~2.5 GB) if not present.
  Run `make eval` for `llama3.2:latest` and `qwen3:4b` (one model loaded at a time;
  `ollama stop <model>` between runs). Paste both summaries into the completion log.
- [ ] 2.5.6 Reference run: ask the owner which provider to use, confirm the model id against that
  provider's current documentation, make sure the key is in `apps/api/.env`, show the planned call
  count, and get permission. Then run `make eval-cloud PROVIDER=… MODEL=… CONFIRM=1` and paste the
  summary. Live test `tests/live/test_cloud_reference_live.py` (skipped unless an eval key is set):
  one `FeedbackAnalysis` from the reference model.
- [ ] 2.5.7 Apply the decision rules: iterate on prompts until the reference target is met,
  re-running both models after each change (ask before each extra reference run).
- [ ] 2.5.8 Write ADR-0012 (reference provider/model and results, both Ollama results, the gap,
  the chosen default). Update defaults and docs (`OLLAMA_MODEL`, `ai-layer.md` §3 and §8).
- [ ] 2.5.9 Commit: `feat(api): add feedback evals with cloud reference run and choose default ollama model`

**Acceptance criteria:**
- [ ] `make eval` and `make eval-cloud` print a summary table and write JSON result files
  (git-ignored).
- [ ] The reference run meets in-range ≥ 80 % and schema failures ≤ 5 %.
- [ ] ADR-0012 records both runs and the chosen default; defaults are updated everywhere.
- [ ] The app runtime never uses eval keys (unit test), and production rejects them.

**Pitfalls:** never print `Settings` or request objects that contain keys; the runner must not
fall back silently to Ollama when a cloud key is missing — fail with a clear message.

---

### Task 2.6 — Web: report page

**Goal:** `/sessions/[id]/report` shows pending/failed/ready states; session and history pages link
to it.
**Depends on:** 2.4
**Files:** `src/features/reports/*`, `src/app/sessions/[id]/report/page.tsx`,
`src/components/{score-dots,score-number}.tsx`; Modify session page (after ending → "View your
report" button; ended sessions show the button in the header), history (score column).
Tests `tests/features/reports/*.test.tsx`.

**Interfaces (produces):**
```ts
export function useReport(sessionId: string): UseQueryResult<ReportOut, ApiError>
// refetchInterval: 2000 while pending/running for the first 120 s, then 5000; stops when ready/failed
export function useRetryReport(sessionId: string): UseMutationResult<…>
```

**Behaviour:**
- Pending/running: skeleton + "Analysing your conversation… This can take up to a minute on a
  local model." After 120 s: "Still working. Make sure the worker is running (`make dev`)."
  When `updated_at` is more than 5 minutes old, also show "Try again" (calls retry).
- Failed: friendly text by `error_code` (`llm_unavailable` → "The AI model isn't reachable. Check
  that Ollama is running, then try again.", `llm_invalid_output` → "The AI returned an unreadable
  report. Try again — it usually works on the second attempt.") + "Try again" button.
- Ready:
  1. Header: scenario title, date, mode; overall score as a large number `/100` with a text label
     (0–39 "Needs work", 40–69 "Getting there", 70–84 "Good", 85–100 "Excellent");
     objective met badge ("Goal achieved" / "Goal not yet achieved").
  2. Summary paragraph.
  3. Skills: one row per dimension — label, 5 dots + "4/5", reason. Rubric labels come from a
     static map in `src/features/reports/dimensions.ts` (same labels as rubric YAML).
  4. Strengths / Things to work on (two columns on desktop, stacked on mobile widths).
  5. "Moments to improve": highlight cards — "You said" (quote) → "Why" (issue) → "Try" (better
     version) with a copy button.
  6. Grammar: table original → corrected + explanation (hidden if empty).
  7. A slot for speaking stats, rendered only when `voice_metrics` is not null (the
     `SpeakingStats` component and its data arrive in Phase 3).
  8. Actions: "Practise again" (creates a new session with the same scenario and mode, navigates),
     "Regenerate report" (secondary; calls retry), "Back to practice".

**Subtasks:**
- [ ] 2.6.1 Failing component tests: pending state text; a pending report whose `updated_at` is
  6 minutes old shows "Try again"; switches to ready when the mock changes;
  failed state shows mapped text and retry calls the endpoint; ready renders every section; empty
  grammar hides the table; score label thresholds (table test on a helper); "Practise again"
  posts a new session with the same scenario/mode.
- [ ] 2.6.2 Run → FAIL. Implement. Run → PASS. `make lint`.
- [ ] 2.6.3 Browser check with Ollama: end a real session → watch pending → ready. Keyboard and
  screen-reader labels on scores ("Clarity: 4 out of 5").
- [ ] 2.6.4 Commit: `feat(web): add feedback report page`

---

### Task 2.7 — E2E: report journey

**Files:** extend `apps/web/e2e/text-practice.spec.ts`.
- [ ] 2.7.1 After ending, click "View your report" → wait for "Goal" badge → assert overall score
  visible, 7 skill rows, at least one "You said" card (fake analysis quote).
- [ ] 2.7.2 `make test-e2e` → PASS. Commit: `test(web): cover report generation in e2e`

## Phase verification

1. `make dev` with the chosen model: run three different scenarios, one deliberately poor
   (rambling, grammar errors). Reports reflect the difference (poor one lower on clarity/
   conciseness/grammar). Quotes in highlights are exact.
2. Stop the worker → end a session → report stays pending with the "Still working" hint after 2 min
   → start the worker → report completes. Repeat, but wait 5 minutes: "Try again" appears; start
   the worker and use it → report completes.
3. Stop Ollama → end a session → report `failed` with the Ollama message → start Ollama → "Try again"
   → ready.
4. The reference run (`make eval-cloud`) meets the target; the Ollama gap is recorded in ADR-0012.
5. `make check` and `make test-e2e` → PASS.

## Completion log

<!-- Append: - YYYY-MM-DD · Task N.M · commits · evidence · Notes · Follow-ups -->
- 2026-09-21 · Task 2.1 · (this commit) · `make check` → API 154 passed + 2 deselected, Web 29
  passed, lint/typecheck/format clean · Notes: `app/llm/outputs.py`, `app/llm/fake_outputs.py` and
  `app/llm/generation.py` already existed from Phase 1's LLM-layer scaffolding (ai-layer.md's
  "binding" contract file was written whole in Task 1.3), so `test_outputs.py` was new but passed
  immediately against existing code — no implementation change needed there beyond fixing the
  `FeedbackAnalysis` example's highlight quote to be an exact substring of the E2E fake
  conversation's first message (`"Hi Sam, thanks for the PR."`) instead of an unrelated placeholder
  (`"so basically"`), so Task 2.2's deterministic quote filter keeps it and Task 2.7's E2E "You
  said" card has something to show. `content/rubrics/v1.yaml` labels/anchors are copied verbatim
  from `ai-layer.md` §6; one-sentence `description` per dimension is new prose (not in that table).
  Extended the pre-existing `test_every_template_includes_the_english_language_rule` test's shared
  context fixture with a `rubric` key so it keeps working once `feedback_system.md.j2` joins
  `system_template_names()` (extra unused context keys are harmless under Jinja's `StrictUndefined`
  — it only errors on variables a template actually references). `build_feedback_prompts` renders
  both templates; only the system template's version is meant to be persisted as `prompt_version`
  (Task 2.3) · Follow-ups: none
- 2026-09-21 · Task 2.2 · (this commit) · `make check` → API 171 passed + 2 deselected, Web 29
  passed, lint/typecheck/format clean · Notes: added `ReportStatus`/`ScoreSource` enums and the
  `DimensionScoreOut`/`Highlight`/`GrammarFix`/`VoiceMetrics` JSON-shape models exactly per
  data-model.md (the latter unused until Phase 3, but the `feedback_reports.voice_metrics` column
  exists from this migration onward). Migration `0004` autogenerated cleanly against the Phase 1
  schema (no manual column tweaks needed) and reformatted with `ruff format` to match the repo's
  migration style; applied to the dev DB and verified with `alembic upgrade head` plus the
  up/down/up migration test. `str.maketrans` keys curly-quote replacement by Unicode codepoint
  (`0x2018` etc.) rather than embedding the literal glyphs in source, since `ruff` (RUF001/RUF002)
  flags ambiguous-looking Unicode characters in code — literal escape-sequence text typed through
  the file-write tooling gets resolved to the actual character before reaching disk, so codepoint
  keys were the reliable fix, not a style preference · Follow-ups: none
- 2026-09-21 · Task 2.3 · (this commit) · `make check` → API 184 passed + 2 deselected, Web 29
  passed, lint/typecheck/format clean · Notes: `generate_report` is five DB transactions (claim →
  load+build prompts → [LLM call, no session held] → save), matching the algorithm in the task
  doc exactly; verified via 13 integration tests (12 service-level + 1 through the actual worker
  task) all green on the first implementation pass after writing them red. Confirmed via Context7
  (`/taskiq-python/taskiq`) that `WORKER_STARTUP`/`WORKER_SHUTDOWN` only fire for a real worker
  process, never for `InMemoryBroker`'s client-side `.kiq()` calls in tests — so
  `test_feedback_task.py` populates `broker.state.settings`/`.session_factory` directly in an
  autouse fixture rather than relying on `app/worker/broker.py`'s startup handler, exactly as the
  subtask note anticipated. `feedback_reports.rubric_version`/`.prompt_version` are `NOT NULL` but
  aren't really known until generation completes; `create_pending_report` fills `rubric_version`
  from the scenario (a real, known value) and leaves `prompt_version=""` as a placeholder — neither
  field is exposed in `ReportOut` per api-contract.md §2 Reports, so a report is never shown in an
  inconsistent state while pending · Follow-ups: none
- 2026-09-21 · Task 2.4 · (this commit) · `make check` → API 193 passed + 2 deselected, Web 29
  passed, lint/typecheck/format clean, generated client regenerated with no further drift · Manual
  check with real Ollama (`llama3.2:latest`) + worker via `make dev`: held a 3-turn code-review
  conversation, ended it (`report_status: "pending"` returned immediately, matching the documented
  contract — the value is captured before enqueueing, not re-read after), then polled
  `GET .../report` every 2 s — reached `status: "ready"` after ~43 s (`created_at` → `completed_at`
  delta), well inside the "up to a minute" copy planned for Task 2.6. `overall_score: 89`,
  `objective_met: false`, all 7 dimension scores present and sensible (grounded in the actual
  conversation content). Deleted the verification session and stopped the manually-started
  servers afterward. Notes: `InMemoryBroker(await_inplace=True)` (only for `app_env=="test"`) makes
  `.kiq()` run the task inline, so integration tests observe worker effects without a separate
  `wait_result()` call — this changed `end_session`'s existing tests' expected `report_status`
  (was always `null` before Phase 2; two-turn sessions now get a real report), so
  `test_end_session_with_two_user_turns_is_ended` and `test_end_session_is_idempotent` were updated
  to match, not just left broken. `retry_report` needs `enqueue_report` from
  `app/worker/tasks/feedback.py`, which itself imports `generate_report` from this same
  `app/services/feedback.py` module — a module-level import the other way would be circular, so
  `retry_report` imports it locally inside the function body. `list_sessions`/`get_session_detail`
  now LEFT JOIN `feedback_reports` (filtered to `status=ready`) to populate `overall_score`; the
  unique constraint on `feedback_reports.session_id` guarantees the join never duplicates rows ·
  Follow-ups: the real-Ollama manual check returned `summary: ""` (an empty string — valid per the
  `FeedbackAnalysis.summary` schema, which has no `min_length`) and empty `highlights`/
  `grammar_fixes` lists; not a Phase 2 mechanical bug (the code faithfully stored and filtered
  exactly what the model returned), but exactly the kind of prompt-quality gap Task 2.5's eval
  suite is meant to catch — worth a `min_length` on `summary` or an eval case for it.
