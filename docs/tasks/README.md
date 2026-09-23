# Build Plan — Tasks

> **For agentic workers:** Required: follow `docs/guides/agent-workflow.md`. Recommended skill:
> `superpowers:subagent-driven-development` (fresh subagent per task + review) or
> `superpowers:executing-plans` (inline). Subtasks use `- [ ]` checkboxes — tick them as you go.

**Spec:** [`docs/product-spec.md`](../product-spec.md) · **Architecture:** [`docs/architecture/`](../architecture/)

## 1. Roadmap and status

| Phase | File | Milestone | Depends on | Status |
|---|---|---|---|---|
| 0 | [Foundations](q1-phase-00-foundations.md) | Q1 | – | Done (2026-09-17) |
| 1 | [Text practice](q1-phase-01-text-practice.md) | Q1 | 0 | Done (2026-09-18) |
| 2 | [Feedback engine](q1-phase-02-feedback-engine.md) | Q1 | 1 | Done (2026-09-22) |
| 3 | [Voice practice](q1-phase-03-voice.md) | Q1 | 2 · Deepgram key | In progress (Task 3.1) |
| 4 | [Pronunciation practice](q1-phase-04-pronunciation.md) | Q1 | 0, 3 (audio libs, TTS) · Azure key | Not started |
| 5 | [Progress, assessment, coach memory](q1-phase-05-progress.md) | Q1 | 2, 3, 4 | Not started |
| 6 | [Writing coach, custom scenarios, drills, settings](q1-phase-06-more-practice.md) | Q1 | 5 | Not started |
| 7 | [Accounts, onboarding & profile](q2-phase-07-accounts-onboarding.md) | Q2 | Q1 done | Not started |
| 8 | [Reminder & summary emails](q2-phase-08-reminder-emails.md) | Q2 | 7 | Not started |
| 9 | [Bring your own AI key](q2-phase-09-byok.md) | Q2 | 7 | Not started |
| 10 | [Launch-readiness](q2-phase-10-launch-readiness.md) | Q2 | 8, 9 | Not started |

Status values: `Not started` · `In progress (Task N.M)` · `Blocked (<reason>)` · `Done (YYYY-MM-DD)`.
Update this table whenever a phase changes state.

```
0 ─► 1 ─► 2 ─► 3 ─► 4 ─► 5 ─► 6 ─┬─► 7 ─┬─► 8 ─┐
                                  │      └─► 9 ─┴─► 10
                                  └─ (Q1 exit)
```

## 2. Global constraints (apply to every task)

- Python **3.12**, `uv`; Node **≥ 22**, `pnpm` 10; Next.js **16** App Router; PostgreSQL **17**;
  Redis **7**; Pydantic AI **v2**; Deepgram Python SDK **v5**; Taskiq + taskiq-redis.
- API base path `/api/v1`; error envelope `{"error": {"code","message","details"}}`
  (`api-contract.md` §1).
- Ports: web 3000, api 8000 (bound to 127.0.0.1), Postgres 5432, Redis 6379, Mailpit 8025/1025,
  Ollama 11434. E2E runs use web 3100, api 8100, Redis db 2 and database `articulate_e2e`.
- Keep DB sessions short (never across LLM/Deepgram/Azure awaits); every `skill_scores` row records
  its `scorer`; LLM calls use the temperatures in `ai-layer.md` §4.3.
- Local user id `00000000-0000-0000-0000-000000000001`, email `local@articulate.localhost`.
- Dimension keys: `clarity, conciseness, structure, audience_fit, tone, confidence,
  grammar_vocabulary, fluency, pronunciation`.
- Limits: 20 user turns/session · 1,000 chars/message · voice session 20 min · voice turn 90 s ·
  pronunciation audio ≤ 30 s · drill audio ≤ 90 s · 8 active coach notes · 3 drills/day.
- Audio: mic PCM16 mono 16 kHz; TTS PCM16 mono 24 kHz; uploads WAV PCM16 mono 16 kHz.
- No raw audio stored. No secrets in code, logs or responses.
- Every Deepgram request sets `mip_opt_out=true` (ADR-0016).
- Prompt or rubric changes: re-run `make eval` and, with the owner's OK, `make eval-cloud`
  (ADR-0015). Eval keys are never used by the app runtime.
- No profile screen in Q1: the local user keeps the default profile (B2, UTC) until Phase 7.
- Ollama and fake providers are development/test only.
- The repo path contains a space — quote it.

## 3. How to execute a phase

1. Create the phase branch (`git switch -c phase-<NN>-<slug>` from `main`, see
   `agent-workflow.md` §2a) and set the phase status to `In progress (Task N.1)`.
2. For each task: read its "Read before starting" list → do the subtasks in order (TDD) → verify
   acceptance criteria → log evidence in the phase's **Completion log**.
3. Run the phase's **Phase verification** + `make test-e2e`.
4. Request a code review of the phase diff (`code-review` skill or owner review).
5. Set status `Done (date)`; summarise to the owner in plain language.

Spikes (Tasks 3.1 and 4.1) produce an ADR and may change later subtasks — if they do, update the
phase file **before** continuing and tell the owner.

## 4. Task template

````markdown
### Task N.M — <Title>

**Goal:** one sentence.
**Depends on:** Task N.K
**Read before starting:** `docs/...#section`, `docs/...`
**Files:**
- Create: `exact/path.py`
- Modify: `exact/path.py`
- Test: `tests/exact/test_path.py`

**Interfaces:**
- Consumes: `name(signature) -> type` (from Task N.K)
- Produces: `name(signature) -> type` (used by Task N.L)

**Subtasks:**
- [ ] N.M.1 Write failing tests in `tests/...`:
  - `test_<behaviour>` — Given …, when …, then …
- [ ] N.M.2 Run `<command>` → expect FAIL (`<reason>`)
- [ ] N.M.3 Implement … (key code shown when it pins a contract)
- [ ] N.M.4 Run `<command>` → expect PASS; run `make check` → PASS
- [ ] N.M.5 Commit: `feat(scope): message`

**Acceptance criteria:**
- [ ] observable behaviour 1
- [ ] observable behaviour 2

**Pitfalls:** things that commonly go wrong here.
````

## 5. Level of detail

Task files pin down **contracts, file paths, test cases, commands and acceptance criteria**, and
show code where it fixes an interface or a non-obvious detail. Implementation bodies are written
by the executing agent via TDD against those contracts, after checking current library docs.
This keeps the plan correct even when a library's API has moved since planning.
