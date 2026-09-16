# Phase 4 — Pronunciation Practice

> **Milestone:** Q1 · **Depends on:** Phase 3 (audio libraries, TTS preview)
> **Needs:** `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` (Azure Speech resource, **F0 free tier**) —
> ask the owner. F0 = 5 audio hours/month, 1 concurrent request.
> **For agentic workers:** follow `docs/guides/agent-workflow.md`. Tick subtasks as you go.

**Goal:** The user reads sentences full of technical vocabulary aloud and sees overall, per-word and
per-sound scores, hears the correct pronunciation, and retries.

**Architecture:** Browser records 16 kHz mono WAV (≤ 30 s) with the Phase 3 capture library →
multipart upload → WAV validation → `PronunciationAssessor` (Azure adapter chosen by the spike,
serialised by a semaphore) → attempt + `skill_scores(pronunciation)` saved → result returned
synchronously.

**Read before starting:** `product-spec.md` F5, `voice-and-pronunciation.md` §1, §4,
ADR-0004, `data-model.md` (`pronunciation_*`), `api-contract.md` §2 Pronunciation.
Context7: `/websites/learn_microsoft_en-us_azure_ai-services_speech-service`
(pronunciation assessment how-to, REST short audio, phoneme alphabet / IPA, N-best phonemes,
Python Speech SDK push streams).

**Out of scope:** unscripted/free-speech pronunciation scoring, prosody, storing audio,
pronunciation drills (Phase 6), coach notes from weak words (Phase 5).

---

## File map

```
apps/api/spikes/azure/{README.md,assess_rest.py,assess_sdk.py}       (throwaway)
docs/decisions/0014-azure-pronunciation-integration.md
apps/api/content/pronunciation/{tech-terms-1,tech-terms-2,meeting-phrases,numbers-and-units,tricky-sounds}.yaml
apps/api/app/content/pronunciation.py
apps/api/app/models/pronunciation.py
apps/api/migrations/versions/0005_pronunciation.py
apps/api/app/pronunciation/{__init__,base,errors,wav,fake,azure,parse}.py
apps/api/app/schemas/pronunciation.py
apps/api/app/services/pronunciation.py
apps/api/app/api/v1/pronunciation.py
apps/api/tests/unit/pronunciation/{test_wav,test_parse,test_azure,test_fake}.py
apps/api/tests/unit/content/test_pronunciation_content.py
apps/api/tests/integration/api/test_pronunciation.py
apps/api/tests/live/test_azure_live.py
apps/api/tests/fixtures/azure/*.json              (responses captured in the spike)
apps/web/src/lib/audio/wav.ts
apps/web/src/features/pronunciation/{api.ts,query-keys.ts,hooks/{use-sentence-recorder,use-attempt}.ts,components/*}
apps/web/src/app/pronunciation/page.tsx  apps/web/src/app/pronunciation/[set]/page.tsx
apps/web/tests/lib/audio/wav.test.ts  apps/web/tests/features/pronunciation/*.test.tsx
apps/web/e2e/pronunciation.spec.ts
```

---

### Task 4.1 — Spike: Azure integration style (throwaway)

**Goal:** Decide REST short-audio vs Speech SDK and confirm the response shape. Output: ADR-0014.
**Depends on:** Azure key available; a WAV from Phase 3 spike (or record one sentence from
`tech-terms-1` the same way).
**Files:** `apps/api/spikes/azure/*`, `docs/decisions/0014-azure-pronunciation-integration.md`,
`tests/fixtures/azure/*.json` (sanitised real responses — no keys, no personal data).

**Questions to answer:**
1. Which REST endpoint form works for the created resource (regional
   `https://{region}.stt.speech.microsoft.com/...` vs resource endpoint)? Status codes for a bad key
   and for > 30 s audio?
2. With `Granularity=Phoneme`, does REST return `Words[].Phonemes[]` with `AccuracyScore`?
   Are `Syllables` returned?
3. Can REST return IPA phonemes (e.g. a `PhonemeAlphabet: "IPA"` field in the header JSON), or is
   that SDK-only? What does the default alphabet look like for `en-US`?
4. Are N-best phonemes ("heard as") available via REST? Via the Python SDK
   (`azure-cognitiveservices-speech`, `PronunciationAssessmentConfig`, `nbest_phoneme_count`)?
5. Latency for a 5 s sentence (REST vs SDK), and behaviour of a second concurrent request on F0.
6. `ErrorType` values seen with `EnableMiscue=true` when a word is skipped or added.

**Subtasks:**
- [ ] 4.1.1 `assess_rest.py` with `httpx`: build the base64 header JSON, POST the WAV, print a
  summary and save the JSON response (sanitised) to `tests/fixtures/azure/rest_<case>.json` for:
  correct reading, a skipped word, an extra word, a deliberately mispronounced word.
- [ ] 4.1.2 `assess_sdk.py` with the Speech SDK (install only inside the spike:
  `uv run --with azure-cognitiveservices-speech python spikes/azure/assess_sdk.py`): same cases
  with `phoneme_alphabet="IPA"` and `nbest_phoneme_count=5` if supported; save JSON.
- [ ] 4.1.3 Write ADR-0014. Decision rule: use REST unless the SDK is required for IPA **or**
  N-best phonemes **and** the SDK works on macOS arm64 without extra system libraries. Record the
  chosen alphabet shown to users (IPA preferred).
- [ ] 4.1.4 Update `voice-and-pronunciation.md` §4.2 (final request details, alphabet, whether
  `heard_as` is populated). If the SDK is chosen, add `azure-cognitiveservices-speech` to the
  dependency list in `overview.md`/`AGENTS.md`.
- [ ] 4.1.5 Commit: `docs: record azure pronunciation integration decision (adr-0014)`

**Acceptance criteria:**
- [ ] ADR-0014 answers all six questions; fixtures exist for the four cases.

---

### Task 4.2 — Pronunciation content, models and seed

**Goal:** 5 sentence sets (10 sentences each) seeded into the database.
**Depends on:** 4.1
**Read before starting:** `data-model.md` (`pronunciation_sets`, `pronunciation_sentences`,
`pronunciation_attempts`, `skill_scores`), `coding-conventions.md` §5.
**Files:** content YAML, `app/content/pronunciation.py`, `app/models/pronunciation.py`, migration
`0005_pronunciation` (also adds `skill_scores.pronunciation_attempt_id`), `app/cli.py` (seed).
Tests `tests/unit/content/test_pronunciation_content.py`, extend `tests/integration/test_seed.py`.

**Content rules (Azure scores against the exact reference text):**
- Sentences 6–16 words, natural workplace English, one idea each.
- Spell out numbers and units in words ("thirty milliseconds", "ninety-nine point nine percent").
- No acronyms or symbols with more than one common pronunciation (avoid "SQL", "GIF", "char",
  "/", "&", "%"); prefer "Postgres" over "PostgreSQL".
- `focus_words` = 1–3 words from the sentence that the set targets (exact spelling as in text).

| Set slug | Title | Difficulty | Focus |
|---|---|---|---|
| tech-terms-1 | Everyday tech words | 1 | cache, queue, database, server, deploy, debug, library, variable, function, request |
| tech-terms-2 | Advanced tech words | 3 | Kubernetes, asynchronous, idempotent, deprecated, algorithm, architecture, authentication, repository, infrastructure, throughput |
| meeting-phrases | Meeting phrases | 1 | clarify, concern, priority, estimate, alternative, schedule, suggestion, follow up, agenda, decision |
| numbers-and-units | Numbers and units | 2 | milliseconds, percent, gigabytes, thousand, versus, fifteen/fifty, thirteen/thirty, quarter, deadline dates |
| tricky-sounds | Tricky sounds | 3 | th (three, throughput, thorough), r/l (release, rollback, reliable), v/w (version, workflow), vowel pairs (ship/sheep, full/fool), word stress (develop, environment) |

Examples:
```yaml
# content/pronunciation/tech-terms-1.yaml
slug: tech-terms-1
title: Everyday tech words
description: Common words engineers say every day.
difficulty: 1
position: 1
sentences:
  - text: We cleared the cache and the page loaded much faster.
    focus_words: [cache]
  - text: The job is waiting in the queue behind two larger tasks.
    focus_words: [queue]
```

**Subtasks:**
- [ ] 4.2.1 Failing tests: all 5 files load; each has exactly 10 sentences; every focus word
  appears in its sentence (case-insensitive); no digits or forbidden symbols in any sentence; word
  count 6–16; seed idempotent; changed sentence text updates via `content_hash`.
- [ ] 4.2.2 Run → FAIL. Write the content, loader, models, migration (review), seed wiring.
  Run → PASS. `make seed` prints `pronunciation_sets: created=5`.
- [ ] 4.2.3 Commit: `feat(api): add pronunciation content and models`

**Pitfalls:** updating a sentence's text must not break past attempts — update in place keeps the
id (attempts then refer to the new text; acceptable, note it in the loader docstring). Removing a
sentence from YAML does **not** delete it (log a warning instead).

---

### Task 4.3 — WAV validation, assessor adapters and parsing

**Goal:** `PronunciationAssessor` with Azure (per ADR-0014) and fake implementations.
**Depends on:** 4.1
**Read before starting:** `voice-and-pronunciation.md` §4 (all).
**Files:** `app/pronunciation/{base,errors,wav,fake,azure,parse}.py`, `app/deps.py`
(`get_pronunciation_assessor`, singleton per process so the semaphore is shared; created lazily —
missing Azure settings never block startup and raise
`PronunciationUnavailableError("Azure Speech is not configured")` on first use).
Add `uv add python-multipart` (needed for uploads in Task 4.4). Tests
`tests/unit/pronunciation/*`.

**Interfaces (produces):** exactly `voice-and-pronunciation.md` §4.1, plus:
```python
# app/pronunciation/wav.py
@dataclass(frozen=True) class WavInfo: duration_s: float; sample_rate: int; channels: int
def validate_wav(data: bytes, *, max_seconds: float, min_seconds: float = 0.3) -> WavInfo   # InvalidAudioError
# app/pronunciation/parse.py
def parse_azure_result(payload: dict[str, Any], *, duration_ms: int) -> PronunciationResult
    # NBest[0]; maps ErrorType; phonemes; heard_as from NBestPhonemes[0] when it differs from the expected phoneme
# app/pronunciation/azure.py
class AzurePronunciationAssessor:   # implements PronunciationAssessor
    def __init__(self, *, key: str, region: str, max_concurrency: int, http: httpx.AsyncClient | None = None): ...
# errors (app/core/errors.py): InvalidAudioError (400 invalid_audio) → NoSpeechRecognisedError; PronunciationUnavailableError (503 pronunciation_unavailable)
```

**Subtasks:**
- [ ] 4.3.1 Failing tests `test_wav.py` (use `tests/factories.make_wav`): valid 1 s file; stereo →
  error; 44.1 kHz → error; 8-bit → error; > 30 s → error; < 0.3 s → error; garbage bytes → error.
- [ ] 4.3.2 Failing tests `test_parse.py` using the spike fixtures: overall scores mapped; word
  error types mapped (an unknown `ErrorType` becomes `"Other"` instead of failing); phonemes
  present; `heard_as` set only when different (if the fixture has
  N-best); empty `NBest` or `RecognitionStatus != "Success"` because nothing was heard →
  `NoSpeechRecognisedError` (subclass of `InvalidAudioError`, message "We couldn't hear any
  speech — try again closer to the microphone."), so the API returns 400 `invalid_audio`
  (a user-fixable problem, not an outage).
- [ ] 4.3.3 Failing tests `test_azure.py` (`respx`): request URL/query/headers (header JSON
  decodes to the documented fields); success parse; 401 → `PronunciationUnavailableError` (logged
  as a configuration problem); 429 → unavailable with retry hint; 5xx retried once then error;
  timeout → error; semaphore: two concurrent calls with `max_concurrency=1` never overlap (use a
  mocked slow response and track concurrent count).
- [ ] 4.3.4 Failing tests `test_fake.py`: `low_words` get 40 + `Mispronunciation`; others 90.
- [ ] 4.3.5 Run → FAIL. Implement (REST or SDK per ADR-0014; if SDK, wrap its callback API with
  `asyncio.to_thread`/futures and keep the same interface). Run → PASS.
- [ ] 4.3.6 Live test `tests/live/test_azure_live.py`: assess the spike's correct-reading WAV →
  `pron_score > 0`, words non-empty. Tell the owner, then run `make test-live`.
- [ ] 4.3.7 Commit: `feat(api): add azure pronunciation assessor with wav validation`

---

### Task 4.4 — Pronunciation service and endpoints

**Goal:** Sets list/detail, attempt upload, attempt history.
**Depends on:** 4.2, 4.3
**Read before starting:** `api-contract.md` §2 Pronunciation.
**Files:** `app/schemas/pronunciation.py`, `app/services/pronunciation.py`,
`app/api/v1/pronunciation.py`. Test `tests/integration/api/test_pronunciation.py`.

**Interfaces (produces):**
```python
async def list_sets(db, user_id) -> list[PronunciationSetSummary]           # best_score = max pron_score over the set's sentences' latest attempts
async def get_set(db, user_id, slug) -> PronunciationSetDetail              # last_score per sentence
async def create_attempt(db, user_id, *, sentence_id: UUID, wav: bytes, purpose: AttemptPurpose,
                         assessor: PronunciationAssessor, assessment_id: UUID | None = None) -> PronunciationAttemptOut
    # validate wav → assess → save attempt → usage(kind=pronunciation, audio_seconds)
    # → skill_scores(pronunciation, round(pron_score), scorer=f"{assessor.provider}:pronunciation")
    #   only for purpose practice (purpose=practice) — Phase 5 adds assessment (purpose=assessment);
    #   drill attempts write NO row (the drill writes one when completed)
async def list_attempts(db, user_id, *, sentence_id: UUID | None, limit: int, cursor: str | None) -> Page[PronunciationAttemptOut]
```
Upload handling: read at most 1.2 MB (`await file.read(1_200_001)`; longer → 413
`payload_too_large`); accept content types `audio/wav`, `audio/x-wav`, `audio/wave`.
Phase 4 accepts `purpose` = `practice` or `drill`; `assessment` is rejected with 422 until Phase 5
adds the `assessment_id` form field (the service parameter exists now but stays unused).

**Subtasks:**
- [ ] 4.4.1 Failing tests: list sets (5, ordered by position, `best_score` null then set after an
  attempt); set detail with `last_score`; unknown set → 404; upload valid WAV (fake assessor) →
  201 with words and a `skill_scores` row; invalid WAV → 400 `invalid_audio`; oversize → 413;
  wrong content type → 400 `invalid_audio`; unknown sentence → 404; assessor unavailable → 503
  `pronunciation_unavailable` and nothing saved; attempt history paginates and filters by sentence;
  usage event recorded; the skill score has `scorer="fake:pronunciation"` and `purpose=practice`;
  a `purpose=drill` attempt writes no skill score; `purpose=assessment` → 422 (until Phase 5).
- [ ] 4.4.2 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [ ] 4.4.3 Commit: `feat(api): add pronunciation sets and attempts endpoints`

---

### Task 4.5 — Web: recorder and pronunciation pages

**Goal:** `/pronunciation` (sets) and `/pronunciation/[set]` (practise sentence by sentence).
**Depends on:** 4.4
**Files:** `src/lib/audio/wav.ts`, `src/features/pronunciation/*`, pages; enable
"Pronunciation" in the shell. Tests listed in the file map.

**Interfaces (produces):**
```ts
// wav.ts
export function encodeWav(chunks: Int16Array[], sampleRate?: 16000): Blob
// use-sentence-recorder.ts
export function useSentenceRecorder(opts: { maxSeconds: number; source?: AudioSource }): {
  state: "idle" | "recording"; seconds: number; level: number;
  start(): Promise<void>; stop(): Blob | null;     // auto-stops at maxSeconds and calls onAutoStop
  onAutoStop(cb: (wav: Blob) => void): () => void;
}
// use-attempt.ts
export function useSubmitAttempt(): UseMutationResult<PronunciationAttemptOut, ApiError, { sentenceId: string; wav: Blob; purpose?: "practice" | "assessment" | "drill" }>
```

**Behaviour:**
- Sets page: cards with title, description, difficulty, best score badge ("Not started" if null).
- Practice page: progress "Sentence 3 of 10"; the sentence in large text with focus words
  underlined; "Hear it" (plays the whole sentence via `/tts/preview` with the user's voice);
  record button (click to start, click to stop; Space works too; max 30 s with a countdown ring;
  level meter); "Assessing…" state while uploading.
- Result: overall score (0–100 + label), accuracy / fluency / completeness bars; the sentence
  re-rendered with each word coloured and labelled (≥ 80 "good", 60–79 "close", < 60 "practise";
  skipped words struck through with "skipped"; extra words shown in a separate "Extra words"
  line); clicking/pressing Enter on a word opens a popover: word score, its sounds with scores
  (and "sounded like …" when `heard_as` exists), "Hear this word" button.
- Actions: "Try again", "Next sentence", "Previous"; previous attempts for the sentence (last 3
  scores) listed under the result.
- Errors: `invalid_audio` → "We couldn't hear that clearly. Move closer to the microphone and try
  again."; `pronunciation_unavailable` → "Pronunciation scoring is unavailable right now. Try again
  in a moment."

**Subtasks:**
- [ ] 4.5.1 Failing tests: `encodeWav` writes a valid 44-byte header (RIFF size, fmt chunk,
  16 kHz, mono, 16-bit) and data length; recorder auto-stops at `maxSeconds` (fake timers);
  result view colours and labels by threshold; skipped/extra words rendering; popover shows
  phonemes and `heard_as`; "Hear this word" requests `/tts/preview` with the word; error messages
  mapped.
- [ ] 4.5.2 Run → FAIL. Implement. Run → PASS. `make lint`.
- [ ] 4.5.3 Browser check with real Azure (`make dev`): read 3 sentences from `tech-terms-2`,
  including one deliberately mispronounced word → it's flagged. Record latency.
- [ ] 4.5.4 Commit: `feat(web): add pronunciation practice pages`

---

### Task 4.6 — E2E: pronunciation journey

**Files:** `apps/web/e2e/pronunciation.spec.ts`.
- [ ] 4.6.1 Spec (fake assessor with `low_words=["cache"]` configured via the
  `FAKE_PRONUNCIATION_LOW_WORDS=cache` setting — add it to `Settings` (dev/test only) and to the
  E2E environment in `playwright.config.ts`):
  open Pronunciation → "Everyday tech words" → record 2 s → result shows "cache" labelled
  "practise" → open its popover → Next sentence.
- [ ] 4.6.2 `make test-e2e` → PASS. Update phase status. Commit:
  `test(web): add pronunciation e2e journey`

## Phase verification

1. Real Azure: complete one full set; scores look plausible; a deliberately skipped word shows as
   "skipped".
2. Two quick attempts in a row don't fail on F0 (semaphore serialises them).
3. Record in a noisy room → friendly `invalid_audio` or low scores, no crash.
4. `make check` and `make test-e2e` → PASS. Azure minutes used this phase noted in the log.

## Completion log

<!-- Append: - YYYY-MM-DD · Task N.M · commits · evidence · Notes · Follow-ups -->
