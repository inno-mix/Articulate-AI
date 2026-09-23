# Articulate AI — Product & Design Spec

> **Status:** Draft — pending owner review · **Date:** 2026-09-17 · **Owner:** Micko Matamorosa
> This is the source of truth for *what* we build and *why*. The architecture docs explain *how*;
> the task docs in `docs/tasks/` explain *in what order*. If code and this spec disagree, stop and
> ask — then update whichever is wrong in the same change.

---

## 1. Summary

Articulate AI is an AI communication coach for **software engineers who want to communicate well in
English** — mostly non-native speakers. Users practise realistic workplace conversations (stand-ups,
explaining technical work to non-technical people, interviews, code review, pushing back on
deadlines) by **text or voice**, then get a feedback report with scores, quoted examples and better
phrasing. A separate **pronunciation practice** feature scores read-aloud sentences full of technical
vocabulary.

The product is built **local-first**: it must be fully working on the owner's machine before any
deployment work starts.

## 2. Goals and non-goals

### Goals
1. Engineers improve clarity, conciseness, structure, tone, confidence, grammar, fluency and
   pronunciation through repeated, realistic practice.
2. Feedback is specific (quotes the user's own words) and actionable (shows a better version).
3. Progress is visible over time.
4. Everything runs locally with Ollama during development; real users bring their own LLM key.

### Non-goals (for now)
- Billing / subscriptions / trials (every user gets every feature).
- Deployment, hosting, AWS, Cognito.
- Slack integration.
- Mobile apps (desktop browsers only: latest Chrome, Edge, Safari, Firefox).
- Admin panel (content lives in YAML files in the repo).
- Team / organization accounts.
- Languages other than English (US English voices and assessment locale by default).
- Storing raw audio recordings.
- Interrupting the AI while it speaks ("barge-in").
- Rhythm/intonation (prosody) scoring from Azure (paid add-on; revisit later).

## 3. Decisions log

| # | Topic | Decision | Source |
|---|---|---|---|
| D1 | Practice modes | Text **and** voice | Owner |
| D2 | Target users | Software engineers improving spoken & written English, mostly non-native speakers | Default adopted — change if needed |
| D3 | Frontend | Next.js (App Router, TypeScript) — UI only | Owner |
| D4 | Backend | Python + FastAPI — all business logic | Owner |
| D5 | LLM during development | Ollama on the developer machine only; the API refuses to start with Ollama when `APP_ENV=production` | Owner |
| D6 | LLM for real users | Bring-your-own-key: Anthropic, OpenAI or Gemini. Built last (Phase 9) | Owner |
| D7 | Speech-to-text & text-to-speech | Deepgram | Owner |
| D8 | Pronunciation scoring | Azure AI Speech pronunciation assessment, scripted (read-aloud) mode, no prosody | Owner |
| D9 | Login | Q1: no login (one built-in local user). Q2: email + password, behind an interface so AWS (likely Cognito) can replace it later | Owner |
| D10 | Email | Account emails (verification, password reset) + reminder emails + weekly progress summary. Mailpit locally | Owner |
| D11 | Billing | Later (out of scope) | Owner |
| D12 | Hosting | Local first; deployment decided later | Owner |
| D13 | Scope | Full feature set for all users, no trial or tiers | Owner |
| D14 | Deepgram & Azure keys | Owned by the app (server env vars), never sent to the browser. Revisit in Phase 9 | Default adopted — change if needed |
| D15 | Voice style | Push-to-talk **and** hands-free (automatic end-of-turn); push-to-talk is the default; no barge-in | Default adopted — change if needed |
| D16 | Audio storage | Raw audio is never stored; only transcripts, word timings and scores | Default adopted — change if needed |
| D17 | Sign-in methods (Q2) | Email + password only | Default adopted — change if needed |
| D18 | Background jobs | Taskiq with Redis (ARQ was rejected: maintenance-only) | Architecture |
| D19 | LLM library | Pydantic AI v2 behind our own `LLMService` interface | Architecture |
| D20 | Feedback-quality checks | From Phase 2, evals also run against one cloud **reference** model using the owner's own key (development only; the app runtime stays on Ollama). Quality targets are measured on the reference model (ADR-0015) | Owner |
| D21 | Deepgram data use | Every Deepgram request sets `mip_opt_out=true` so practice audio isn't used for Deepgram model training (ADR-0016) | Owner |
| D22 | Profile editing | Profile screen and timezone detection ship in Q2 (Phase 7). Q1 uses the local user's default profile | Owner |
| D23 | Language of the app | In Q1 every AI output — persona replies, hints, feedback, rewrites, scenarios, drills — is in English, in simple wording matched to the learner's English level. The user's native language is stored but not used by any prompt in Q1 (revisit in Q2) | Owner |

Architecture decisions have ADRs in `docs/decisions/`.

## 4. Users and core journeys

**Persona — "Ravi", backend engineer, 4 years' experience, B2 English.** Writes code well; freezes in
stand-ups, over-explains to PMs, says "um" a lot, mispronounces *cache* and *queue*.

Core journeys (Q1, single local user):
1. **Practise a scenario by text** → pick scenario → chat with the AI playing the other person →
   end → read report → retry.
2. **Practise a scenario by voice** → same, but speaking; live transcript; AI answers aloud; report
   adds speaking stats.
3. **Pronunciation practice** → pick a sentence set → read each sentence aloud → see per-word and
   per-sound scores → hear the correct pronunciation → retry.
4. **Daily drills** → open Drills → complete 3 short exercises aimed at weak spots.
5. **Improve a message** → paste a Slack message / email / PR description → pick a goal → get a
   rewrite with explanations.
6. **Rehearse a real situation** → describe it → AI generates a custom scenario → practise it.
7. **Track progress** → dashboard with trends per skill, streak, filler-word and pace trends.

Added in Q2:
8. **Sign up / log in / verify email / reset password / onboarding / edit profile.**
9. **Receive reminder and weekly summary emails.**
10. **Add own AI key** (Anthropic/OpenAI/Gemini), choose model, see usage.

## 5. Feature specification

Each feature lists its phase (see `docs/tasks/README.md`).

### F1. Scenario library (Phase 1)
- 15 built-in scenarios for engineers + 2 assessment scenarios, stored as YAML in
  `apps/api/content/scenarios/` and seeded into the database.
- Each scenario: `slug`, `title`, `category`, `difficulty` (1–3), `summary`, `persona`
  (`name`, `role`, `personality`, `goals`), `user_objective`, `opening_line`,
  `success_criteria` (list), `recommended_mode` (`text`|`voice`|`either`), `rubric_version`.
- Categories: `status_updates`, `stakeholder_communication`, `interviews`, `code_review`,
  `negotiation`, `meetings`, `career`.
- Built-in slugs:
  `standup-update`, `explain-tech-debt-to-pm`, `incident-status-update`,
  `behavioral-interview-conflict`, `system-design-interview-url-shortener`,
  `code-review-give-feedback`, `code-review-respond-to-pushback`, `push-back-on-deadline`,
  `clarify-vague-requirements`, `sprint-demo`, `ask-senior-for-help`,
  `one-on-one-promotion`, `client-call-scope-change`, `explain-architecture-to-new-teammate`,
  `disagree-in-design-review`.
- Assessment slugs: `assessment-explain-your-project` (text), `assessment-standup` (voice).
- Library page: filter by category, difficulty and recommended mode.

### F2. Text practice (Phase 1)
- Start a session from a scenario; the AI sends the scenario's `opening_line` first.
- AI replies stream token-by-token (Server-Sent Events).
- AI stays in character, replies in 1–3 sentences, never grades during the conversation, ignores
  requests to change its role or reveal instructions.
- The persona always replies in English (D23). If the user writes in another language, the persona
  stays in character, replies in English and encourages them to continue in English.
- **Hint** button: returns one suggestion (≤ 30 words) for what the user could say next.
- Limits: max **20 user turns** per session, max **1,000 characters** per user message.
- User can end the session at any time; ending with fewer than 2 user turns marks the session
  `abandoned` (no report).
- User can delete any of their sessions from History; this deletes the conversation, its report
  and its scores.
- Crisis safety: if a user message indicates self-harm or crisis, the AI steps out of character with
  a fixed supportive message and the session is flagged (`safety_flag = true`).

### F3. Feedback report (Phase 2)
- Generated in the background after a session ends; the report page shows a progress state until
  ready (polls every 2 s, then every 5 s after 2 minutes). After 120 s it explains that generation
  is taking longer; if the report
  has made no progress for 5 minutes (e.g. the worker stopped) it offers "Try again".
- Contents:
  - `summary` (2–3 sentences) and `objective_met` (yes/no).
  - Scores 1–5 for seven language dimensions: `clarity`, `conciseness`, `structure`,
    `audience_fit`, `tone`, `confidence`, `grammar_vocabulary`, each with a one-line reason.
  - Voice sessions add `fluency` (1–5, computed by code, not the LLM) and **speaking stats**:
    words per minute, filler words (count, rate, examples), long pauses, "hard to catch" words.
  - Overall score = mean of available dimension scores, shown as 0–100.
  - 1–3 strengths, 1–3 improvements.
  - Up to 5 highlights: an exact quote of the user's words, the issue, and a better version.
    Highlights whose quote is not found in the user's messages are dropped (anti-hallucination).
  - Up to 8 grammar fixes: original, corrected, explanation.
  - "Retry this scenario" button.
- All feedback is written in English (D23), in simple wording suited to the learner's level.
- Rubric is versioned YAML (`apps/api/content/rubrics/v1.yaml`); reports record the rubric
  version and the model used.

### F4. Voice practice (Phase 3)
- Same sessions as text, `mode = voice`.
- Browser captures mic audio (echo cancellation on, 16 kHz mono PCM) and streams it over one
  WebSocket to FastAPI; FastAPI relays to Deepgram STT and streams the live transcript back.
- Two input styles (user setting, default push-to-talk):
  - **Push-to-talk:** hold the button (or Space) to talk; release ends the turn.
  - **Hands-free:** Deepgram's end-of-turn detection ends the turn. After 20 s of listening with no
    speech, listening pauses ("Paused — tap to continue") so silence isn't streamed or billed.
- AI reply streams from the LLM, is split into sentences, sent to Deepgram TTS (Aura-2) and played
  back as it arrives. Mic input is ignored while the AI is thinking/speaking (no barge-in).
- Visible state indicator: `listening` / `thinking` / `speaking`.
- Max voice session length: **20 minutes**; max single turn: **90 seconds**.
- Words, timings and confidence are saved per user turn; raw audio is discarded.
- The STT model (Flux vs Nova-3) is chosen by a spike at the start of Phase 3.

### F5. Pronunciation practice (Phase 4)
- 5 built-in sentence sets (10 sentences each), YAML in `apps/api/content/pronunciation/`:
  `tech-terms-1`, `tech-terms-2`, `meeting-phrases`, `numbers-and-units`, `tricky-sounds`.
- User records one sentence at a time (max 30 s, WAV 16 kHz mono PCM, recorded in the browser).
- Backend sends it to Azure pronunciation assessment (scripted: `ReferenceText` = sentence,
  `HundredMark`, `Phoneme` granularity, miscue enabled, locale `en-US`).
- Result: overall pronunciation, accuracy, fluency and completeness scores (0–100); each word
  colour-coded (≥ 80 green, 60–79 amber, < 60 red) with error type; clicking a word shows its
  sounds (phonemes) with scores and plays the correct pronunciation (Deepgram TTS).
- Words scoring < 60 in two or more attempts become coach notes and feed drills.

### F6. Progress (Phase 5)
- Dashboard: latest score per dimension (average of last 5 data points) and change vs the 5
  before; trend chart per dimension (30 / 90 days); sessions completed; current streak;
  filler-word rate and words-per-minute trends; pronunciation score trend.
- Streak: consecutive days (user's timezone) with at least one completed session, drill or
  pronunciation attempt.
- Scores are only compared when they come from the same **scorer** (the AI model, or the
  speaking-stats / pronunciation engine). Charts mark where the scorer changed, and the baseline is
  shown only if it was measured by the current scorer (otherwise the app suggests retaking it).

### F7. Baseline assessment (Phase 5)
- A guided flow: one text scenario (`assessment-explain-your-project`), one voice scenario
  (`assessment-standup`) and 3 pronunciation sentences.
- Results are stored like normal data with `purpose = assessment` and shown as the baseline line on
  progress charts. Can be retaken; the latest one is the baseline.

### F8. Coach memory (Phase 5)
- After each report, the LLM updates up to **8 active coach notes** (e.g. "Over-explains before
  giving the main point"). Each note has a dimension, text, evidence quote and `times_seen`.
- The 3 most-seen active notes are added to future role-play and drill prompts.
- The user can view notes and dismiss any note.

### F9. Writing coach (Phase 6)
- Input: text (≤ 4,000 chars), channel (`slack`, `email`, `pr_description`, `other`), goal
  (`clearer`, `shorter`, `more_polite`, `more_assertive`), optional context (≤ 500 chars).
- Output (in English, D23): rewrite, list of changes (what + why), one tone note. History list of
  past rewrites. Input written in another language is rewritten into English.

### F10. Custom scenarios (Phase 6)
- User describes a real situation (≤ 1,000 chars) → AI drafts a scenario (title, persona,
  objective, opening line, success criteria, category, difficulty) → user reviews/edits → saves.
- Custom scenarios appear in the library under "My scenarios" and can be deleted.

### F11. Daily drills (Phase 6)
- 3 drills per day, generated lazily the first time the Drills page is opened that day (user's
  timezone). Kinds: `explain_concept` (voice or text, ≤ 60 s), `rephrase` (rewrite one of the
  user's weak sentences from a past report), `pronunciation` (3 weak words/sentences),
  `filler_free_minute` (speak 60 s on a topic; scored on filler rate and pace).
- Each drill gets short feedback (score 1–5 + one tip). Completing drills counts toward the streak.
- Voice drills upload a WAV (≤ 90 s) and use Deepgram pre-recorded transcription.

### F12. Settings (Phase 6)
- Practice: default mode (text/voice), voice input style (push-to-talk/hands-free), AI voice
  (curated list of 6 Aura-2 voices) with preview, microphone test (level meter). **No AI speaking
  speed setting**: the Phase 3 spike (ADR-0013) confirmed Deepgram's `speed` parameter only works
  on the REST TTS endpoint (used for the voice preview), not on the `speak.v1` WebSocket that
  streams audio during a live voice session — so a speed setting couldn't affect the thing it
  would be for. The voice preview itself still plays at normal speed.
- "About your data": what is stored locally and which services receive audio/text.
- Q2 adds: profile (Phase 7), reminders on/off + time and weekly summary on/off (Phase 8), AI keys
  (Phase 9).
- **Q1 limitation (D22):** there is no profile screen before Q2. The local user keeps the default
  profile (seniority `mid`, English level `B2`, timezone `UTC`), so prompts assume B2 and streaks /
  "practised today" use UTC dates. `PATCH /api/v1/me/profile` exists from Phase 0 if a value must be
  changed earlier (see `docs/guides/local-development.md`).

### F13. Accounts & onboarding (Phase 7, Q2)
- Register (email + password ≥ 12 chars), verify email (link, 24 h), log in, log out, refresh,
  forgot/reset password (link, 1 h), delete account (deletes all data).
- Onboarding wizard (4 steps): role & seniority → English level & native language → goals & focus
  areas + timezone (detected from the browser) → offer the baseline assessment.
- Profile settings: display name, seniority, native language, English level (CEFR A2–C2), goals,
  focus areas (max 3), timezone. When the browser's timezone differs from the saved one, the app
  offers to update it.
- A CLI command moves the Q1 local user's data into a real account.

### F14. Reminder & summary emails (Phase 8, Q2)
- Daily practice reminder at the user's chosen local time, only if they haven't practised that day.
- Weekly progress summary (Monday 09:00 local) built from stats with a fixed template (no LLM).
- Every email has a one-click unsubscribe link. Mailpit catches emails locally.

### F15. Bring your own AI key (Phase 9, Q2)
- Add/replace/delete one key per provider (Anthropic, OpenAI, Gemini); choose active provider and
  model from an allowlist; the key is validated on save; stored encrypted (AES-256-GCM); only the
  last 4 characters are ever shown.
- Usage page: tokens and speech seconds per day.
- In production, a user with no key sees a prompt to add one; practice endpoints return
  `409 llm_not_configured`. In development, Ollama is the fallback.

## 6. Quality bar

- **Latency (local, M1 8 GB, 3–4B model):** text first token ≤ 3 s; voice "end of turn → AI starts
  speaking" ≤ 6 s; report ready ≤ 90 s. (Cloud models in Q2 should be much faster.)
- **Report quality:** eval set of ≥ 25 transcripts. On the cloud **reference** model (D20):
  ≥ 80 % of dimension scores within the expected range and structured-output failure rate ≤ 5 %
  after retries. The default Ollama model's results are reported alongside; a documented gap is
  acceptable because Ollama is development-only.
- **Reliability:** every LLM/Deepgram/Azure failure shows a clear, retryable message; nothing
  crashes the page.
- **Accessibility:** keyboard operable (push-to-talk on Space), visible focus, colour is never the
  only signal (scores also shown as numbers/labels).
- **Tests:** backend services ≥ 80 % line coverage; every endpoint has at least one integration test;
  critical journeys covered by Playwright E2E with fake AI providers.

## 7. Milestones

| Milestone | Phases | Exit criteria |
|---|---|---|
| **Q1 — Core product (local, single user, no login)** | 0 Foundations · 1 Text practice · 2 Feedback engine · 3 Voice · 4 Pronunciation · 5 Progress · 6 More practice | All journeys 1–7 work on the owner's machine; all tests and evals pass |
| **Q2 — Accounts & go-live readiness** | 7 Accounts & onboarding · 8 Reminder emails · 9 Own AI key · 10 Launch-readiness | Journeys 8–10 work; security review done; full stack runs in Docker |

Q1/Q2 are milestones, not calendar quarters.

## 8. External services

| Service | Used for | Needed from | Account owner |
|---|---|---|---|
| Ollama (local) | LLM during development | Phase 0 | n/a |
| One cloud LLM (Anthropic, OpenAI or Google) | Reference model for evals only (D20) | Phase 2 | Owner (own key, dev only) |
| Deepgram | STT (streaming + pre-recorded), TTS — all requests opt out of model training (D21) | Phase 3 | Owner (app key) |
| Azure AI Speech (F0 free tier for dev) | Pronunciation assessment | Phase 4 | Owner (app key) |
| SMTP (Mailpit locally) | Emails | Phase 7 | n/a locally |
| Anthropic / OpenAI / Google | LLM for real users | Phase 9 | Each user |

Azure free tier: 5 audio hours/month, 1 concurrent request — fine for development only.

## 9. Open items (non-blocking)

- Deepgram STT model choice (Flux vs Nova-3) — decided by the Phase 3 spike: **Nova-3**
  (ADR-0013; Flux has no filler-word feature and didn't reach `EndOfTurn` in testing).
- Azure integration style (REST short-audio vs Speech SDK) — decided by the Phase 4 spike.
- Final Ollama model (`llama3.2:latest` vs `qwen3:4b`) and the cloud reference provider/model —
  decided in Phase 2 (Task 2.5).
- Deepgram TTS speed control availability — checked in the Phase 3 spike (ADR-0013): works on
  REST only, not the live WebSocket, so the speaking-speed setting is dropped (F12) rather than
  hidden.
- Production email sender (e.g. Amazon SES) and hosting — decided after Q2.
