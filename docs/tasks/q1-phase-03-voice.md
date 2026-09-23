# Phase 3 — Voice Practice

> **Milestone:** Q1 · **Depends on:** Phase 2 · **Needs:** `DEEPGRAM_API_KEY` in `apps/api/.env`
> (ask the owner; Deepgram usage costs money — tell the owner before running live tests)
> **For agentic workers:** follow `docs/guides/agent-workflow.md`. Tick subtasks as you go.

**Goal:** The user practises scenarios by speaking: push-to-talk or hands-free, live transcript,
the persona answers aloud, and the report adds speaking stats and a fluency score.

**Architecture:** One browser↔API WebSocket per voice session. `VoiceSessionRelay` (state machine)
relays mic PCM to Deepgram STT, runs the LLM, splits sentences, streams Deepgram TTS PCM back.
Pure `metrics.py` computes speaking stats from saved word timings; the report worker adds them.
Browser: AudioWorklet capture → `PcmChunker` → socket; `PcmPlayer` schedules TTS audio.

**Read before starting:** `product-spec.md` F4, `voice-and-pronunciation.md` §1–3, §6–7
(all of it, carefully), ADR-0003, ADR-0009, ADR-0011, `testing-strategy.md` §2 (event-loop rule).
Context7: `/deepgram/deepgram-python-sdk` (listen v1/v2 connect, speak v1 connect, events,
REST speak), `/websites/developers_deepgram` (filler words, endpointing, UtteranceEnd, Flux
end-of-turn, Aura-2 voices, TTS parameters).

**Out of scope:** pronunciation scoring (Phase 4), drills (Phase 6), barge-in, storing audio.

---

## File map

```
apps/api/spikes/deepgram/{README.md,stt_compare.py,tts_check.py,ws_client.py}     (throwaway)
docs/decisions/0013-deepgram-stt-model.md
apps/api/app/voice/{__init__,base,fake,fake_assets,metrics,sentences,fillers,voices,protocol,relay}.py
apps/api/app/voice/{deepgram_common,deepgram_stt,deepgram_tts}.py
apps/api/app/schemas/voice.py
apps/api/app/api/v1/{voice,tts}.py
apps/api/app/deps.py                              (+ get_stt, get_tts)
apps/api/app/services/feedback.py                 (+ voice metrics, fluency)
apps/api/app/services/me.py                       (tts_voice validation)
apps/api/tests/unit/voice/{test_metrics,test_sentences,test_fillers,test_protocol,test_deepgram_stt,test_deepgram_tts}.py
apps/api/tests/integration/api/{test_voice_ws,test_tts_preview,test_voices}.py
apps/api/tests/integration/services/test_feedback_voice.py
apps/api/tests/live/test_deepgram_live.py
apps/api/tests/fixtures/audio/hello_um.wav        (owner-recorded or generated; see 3.1)
apps/api/tests/fixtures/deepgram/*.json           (event payloads captured in the spike)
apps/web/public/worklets/pcm-capture-processor.js
apps/web/src/lib/audio/{pcm,mic-capture,pcm-player,voice-socket}.ts
apps/web/src/lib/api/events.ts                    (+ voice events)
apps/web/src/features/voice/{hooks/use-voice-session.ts,components/*}
apps/web/src/features/reports/components/speaking-stats.tsx
apps/web/tests/lib/audio/{pcm,voice-socket}.test.ts
apps/web/tests/features/voice/*.test.tsx  apps/web/tests/features/reports/speaking-stats.test.tsx
apps/web/e2e/voice-practice.spec.ts
```

---

### Task 3.1 — Spike: Deepgram STT model, TTS voices and parameters (throwaway)

**Goal:** Evidence-based choice between Flux and Nova-3, and verified TTS details. Output is an ADR,
not production code.
**Depends on:** Deepgram key available.
**Files:** `apps/api/spikes/deepgram/*` (not imported by the app), `docs/decisions/0013-deepgram-stt-model.md`.

**Questions to answer (record each with evidence):**
1. Nova-3 streaming with `filler_words=true`: are "um/uh" returned as words? Is there a flag
   marking them as fillers, or only the token text?
2. Flux (`listen.v2`, `flux-general-en`): are filler words returned (try `filler_words`)? Are
   word-level `start`/`end`/`confidence` present? Which events signal end of turn, and what's the
   typical delay after the speaker stops?
3. Nova-3 end-of-turn: with `endpointing=300` + `utterance_end_ms=1000`, how long after speech ends
   do `speech_final` / `UtteranceEnd` arrive? With `send_finalize()` (push-to-talk), how quickly
   does the final result arrive, and is it marked `from_finalize`?
4. Does `keyterm` improve recognition of "Kubernetes", "PostgreSQL", "idempotent" in the sample?
5. TTS: time to first audio byte for a 1-sentence text over `speak.v1` WebSocket with
   `linear16`/24 kHz; confirm the six voice ids in `voice-and-pronunciation.md` §7 exist (replace
   any that don't); is there a speed parameter for Aura-2?
6. SDK v5: exact method for REST TTS (MP3) and pre-recorded file transcription (for Phase 6).
7. `mip_opt_out=true` (ADR-0016): confirm the SDK v5 parameter name and that `listen.v1`,
   `listen.v2`, `speak.v1` (WebSocket), REST speak and pre-recorded transcription all accept it
   without errors or warnings. Every spike script sets it.

**Subtasks:**
- [x] 3.1.1 Ask the owner to record two clips on their Mac (QuickTime → New Audio Recording):
  (a) a ~15 s stand-up update with a few natural "um/uh", mentioning Kubernetes and PostgreSQL;
  (b) a ~10 s answer ending with a clear 2-second silence. Convert:
  `afconvert -f WAVE -d LEI16@16000 -c 1 in.m4a out.wav`. Store in `apps/api/spikes/deepgram/audio/`
  (git-ignored except the one copied later to `tests/fixtures/audio/hello_um.wav` **with the
  owner's consent**; otherwise generate a fixture with TTS — note TTS audio has no fillers).
- [x] 3.1.2 `stt_compare.py`: stream each clip in real time (100 ms chunks with `asyncio.sleep`)
  to Nova-3 and Flux; log all events with timestamps relative to the last audio chunk; print a
  summary table.
- [x] 3.1.3 `tts_check.py`: open a speak WebSocket per voice id, send one sentence + flush, measure
  first-byte latency and total bytes; try the REST MP3 endpoint; probe a speed parameter.
- [x] 3.1.4 Write ADR-0013 with the tables and the decision. Decision rule: prefer the model that
  returns filler words **and** word timings; if both do, prefer lower end-of-turn latency for
  hands-free; if Flux lacks fillers, choose Nova-3.
- [x] 3.1.5 Update `voice-and-pronunciation.md` §2.5/§6/§7, `local-development.md`
  (`DEEPGRAM_STT_MODEL` default), `.env.example`, and `product-spec.md` F12/§9 (state whether the
  speaking-speed setting will exist). Tell the owner the result.
- [x] 3.1.6 Commit: `docs: record deepgram stt model decision (adr-0013)` (spike scripts may be
  committed under `spikes/` for reference; audio files are not).

**Acceptance criteria:**
- [x] ADR-0013 answers all seven questions with measured evidence.

---

### Task 3.2 — Speaking stats, filler detection, sentence splitter (pure)

**Goal:** Fully tested pure functions used by the relay and the report worker.
**Depends on:** 3.1
**Read before starting:** `voice-and-pronunciation.md` §2.5 step 4, §3.
**Files:** `app/voice/{metrics,sentences,fillers}.py`; tests `tests/unit/voice/test_{metrics,sentences,fillers}.py`.

**Interfaces (produces):**
```python
# app/voice/fillers.py
FILLER_TOKENS: frozenset[str]
def is_filler(token: str, *, provider_flag: bool | None = None) -> bool   # provider flag wins when not None

# app/voice/metrics.py  (constants at top: LONG_PAUSE_S=2.0, LOW_CONFIDENCE=0.60, PACE_OK=(110,170), PACE_WIDE=(90,190))
def compute_voice_metrics(turns: list[SpeechData]) -> VoiceMetrics
def fluency_reason(m: VoiceMetrics) -> str        # e.g. "Pace 142 wpm (aim 110–170) · 3.1 fillers per 100 words · 0.5 long pauses per minute"
def speaking_summary(m: VoiceMetrics) -> str      # one line for the feedback prompt

# app/voice/sentences.py
class SentenceSplitter:
    def push(self, delta: str) -> list[str]       # returns complete chunks ready for TTS
    def flush(self) -> list[str]                  # remaining text (stripped, non-empty)
```

**Subtasks:**
- [x] 3.2.1 Failing parametrised tests for metrics: no turns → all counts 0, `wpm=0`,
  `fluency_score=1` (no speech can't be fluent; say so in the docstring); normal pace 140 wpm, no
  fillers → 5; 100 wpm → 4; 80 wpm → 3; filler rate 4 → −1; 7 → −2; long pauses 3/min → −1;
  combined penalties clamp at 1; turns with < 3 non-filler words excluded from pace; only short
  turns → `pace_measured=false`, `wpm=0` and **no** pace penalty; hard-to-catch words
  distinct, lower-cased, ≤ 10, fillers excluded; `filler_examples` ≤ 5 distinct.
- [x] 3.2.2 Failing tests for fillers: "um", "Uh," (punctuation stripped), "like" is **not** a
  filler, provider flag overrides.
- [x] 3.2.3 Failing tests for the splitter: splits "Hello there. How are you?" into two chunks
  when streamed char by char; doesn't split "e.g. this" or "v2.1 is out" mid-token (require
  whitespace after the terminator and ≥ 20 chars); long run-on text is split at a comma/space after
  200 chars; flush returns the tail; no empty chunks.
- [x] 3.2.4 Run → FAIL. Implement. Run → PASS.
- [x] 3.2.5 Commit: `feat(api): add speaking stats, filler detection and sentence splitter`

---

### Task 3.3 — Deepgram adapters, fakes, voices and TTS preview

**Goal:** `SpeechToText`/`TextToSpeech` implementations (Deepgram + fakes), `GET /voices`,
`GET /tts/preview`, and `tts_voice` validation.
**Depends on:** 3.1, 3.2
**Read before starting:** `voice-and-pronunciation.md` §2.5–2.6, §6–7; ADR-0013; ADR-0016;
`api-contract.md` §2 (Voices, Voice).
**Files:** `app/voice/{base,fake,deepgram_common,deepgram_stt,deepgram_tts,voices}.py`, `app/deps.py`,
`app/api/v1/tts.py`, `app/api/v1/me.py` (`GET /voices` lives here), `app/services/me.py`.
Add dependency: `uv add deepgram-sdk` (pin the major version 5). Tests listed in the file map.

**Interfaces (produces):** Protocols exactly as `voice-and-pronunciation.md` §2.6, plus:
```python
# app/voice/deepgram_stt.py
# DEVIATION FROM THE ORIGINAL PLAN (recorded here per agent-workflow.md's "spikes may change
# later subtasks" rule): ADR-0013 found that deepgram-sdk 5.3.4's typed listen.v1.connect() has
# no `filler_words` kwarg and silently drops request_options["additional_query_parameters"] for
# WS connects — using it as originally planned would make the live adapter strip every "um"/"uh"
# server-side, silently breaking Task 3.2's whole filler-rate feature. DeepgramSpeechToText opens
# a raw `websockets` connection with a hand-built query string instead (the workaround ADR-0013
# proved works), using AsyncDeepgramClient only where the SDK still has no gap (TTS).
class DeepgramSpeechToText:            # implements SpeechToText
    def __init__(self, api_key: str, model: str, *, connector: WebsocketConnector | None = None): ...
# app/voice/deepgram_tts.py  (no SDK gap here — speak.v1.connect() and audio.generate() both work)
class DeepgramTextToSpeech:            # implements TextToSpeech
    def __init__(self, api_key: str, *, client_factory=None): ...
# app/voice/deepgram_common.py
def deepgram_request_options() -> dict[str, Any]     # {"mip_opt_out": True} (+ shared options found in the spike)
# app/voice/voices.py
@dataclass(frozen=True) class Voice: id: str; label: str
VOICES: tuple[Voice, ...]; def is_known_voice(voice_id: str) -> bool
# app/deps.py
def get_stt(settings: SettingsDep) -> SpeechToText   # fake | deepgram; created lazily — a missing key never blocks startup,
                                                     # it raises SpeechUnavailableError("Deepgram API key is not configured") on first use
def get_tts(settings: SettingsDep) -> TextToSpeech
# errors: SpeechUnavailableError (503 "speech_unavailable")
```
Fake behaviour (documented for tests and `make dev-fake`):
- `FakeSpeechToText(script=None)`: default script = interim "hello", final words
  `[hello 0.0–0.4 c=0.98, um 0.5–0.7 c=0.90 filler, there 0.8–1.2 c=0.55]`, then `end_of_turn`.
  Emits the script after `finalize()` **or** after receiving 5 audio chunks (hands-free).
  Options: `open_delay_s` (simulates a slow connection), `silent=True` (never emits anything);
  `received_chunks` records the audio it got, for assertions.
- `FakeTextToSpeech`: 2 400 zero bytes per sentence; `synthesize_mp3` returns a constant tiny MP3
  byte string stored in `app/voice/fake_assets.py`.

Adapter seams: TTS wraps SDK connection objects behind `client_factory` so unit tests inject a fake
client/connection. STT's `connector` plays the same role for the raw websocket (tests inject a
fake connector that replays recorded event dicts as JSON text frames) — both use real event
payload shapes captured in the spike, saved as JSON fixtures under `tests/fixtures/deepgram/`.

**Subtasks:**
- [x] 3.3.1 Failing unit tests `test_deepgram_stt.py`: maps interim results → `interim`; final
  results → `final` with `SpeechWord`s (filler flags set); end-of-turn signal (per ADR-0013) →
  `end_of_turn`; `finalize()` calls the SDK finalize; connection errors → `SpeechUnavailableError`;
  `keyterm` passed (≤ 20); `test_connection_opts_out_of_model_improvement` (`mip_opt_out` is true
  on every connection).
- [x] 3.3.2 Failing unit tests `test_deepgram_tts.py`: sends each sentence as it arrives and exactly
  one flush per turn (after the last sentence); yields audio
  bytes in order; stops after the flushed event; REST MP3 uses `respx` mock; HTTP 5xx →
  `SpeechUnavailableError`; both the WebSocket connection and the REST request carry
  `mip_opt_out=true`.
- [x] 3.3.3 Failing integration tests: `test_voices.py` (`GET /voices` returns 6 voices);
  `test_tts_preview.py` (fake returns `audio/mpeg`; unknown voice → 422; empty text or > 200 chars → 422);
  extend `test_me.py` (`PATCH /settings` with unknown `tts_voice` → 422).
- [x] 3.3.4 Run → FAIL. Implement. Run → PASS. `make gen-client`.
- [x] 3.3.5 Live test `tests/live/test_deepgram_live.py`: stream `hello_um.wav` → at least one
  final with words; TTS one sentence → > 0 bytes. Run `make test-live` (tell the owner first).
- [x] 3.3.6 Commit: `feat(api): add deepgram speech adapters, voices and tts preview`

---

### Task 3.4 — Voice relay and WebSocket endpoint

**Goal:** `WS /sessions/{id}/voice` implementing the protocol and state machine.
**Depends on:** 3.3
**Read before starting:** `voice-and-pronunciation.md` §2 (every row), `testing-strategy.md` §2
(event-loop rule); Context7 for `httpx-ws` ASGI testing.
**Files:** `app/voice/{protocol,relay}.py`, `app/schemas/voice.py`, `app/api/v1/voice.py`,
`app/domain/limits.py` (+ `HANDS_FREE_IDLE_SECONDS = 20`), `app/services/sessions.py`
(`delete_session` in-use check). Add dev dependency: `uv add --dev httpx-ws`. Tests `tests/unit/voice/test_protocol.py`,
`tests/integration/api/test_voice_ws.py`.

**Interfaces (produces):**
```python
# app/voice/protocol.py — Pydantic models with `type` Literal discriminators
ClientMessage = Annotated[Start | PttDown | PttUp | CancelTurn | Resume | EndSession | Ping, Field(discriminator="type")]
ServerEvent = Ready | State | Transcript | UserTurn | AssistantDelta | AssistantTurn | AudioEnd | Limit | Error | Paused | SessionEnded | Pong
def parse_client_message(raw: str) -> ClientMessage     # raises ProtocolError → server sends error(code="bad_message", fatal=False)

# app/voice/relay.py
@dataclass
class VoiceDeps:
    session_factory: async_sessionmaker[AsyncSession]; redis: Redis; settings: Settings
    stt: SpeechToText; tts: TextToSpeech; llm: LLMService
    clock: Callable[[], float] = time.monotonic
class VoiceSessionRelay:
    def __init__(self, ws: WebSocket, *, user: User, session_id: UUID, deps: VoiceDeps) -> None
    async def run(self) -> None      # returns when the socket closes or the session ends
```
Implementation notes (binding):
- Handshake validation before `accept()` is not possible for close codes in all servers — accept,
  then validate and `close(code=...)` with the documented 44xx codes.
- One-socket-per-session: Redis key `voice:session:<id>` SET NX with 30 s TTL refreshed every 10 s;
  released on exit.
- Use `asyncio.TaskGroup` for: client receive loop, turn processing, heartbeat. Cancel everything on
  disconnect; always close Deepgram connections in `finally`.
- User turn: accumulate `final` events' words; on end (PTT up → `finalize()` then wait ≤ 2 s for
  finals; hands-free → `end_of_turn`), build text from non-empty words; if no non-filler words →
  send `state` back to listening/idle without saving.
- Save user message via `add_message(... source=voice, speech=SpeechData)` in its own transaction;
  check turn limit first (send `limit: turn_limit_reached` and stop accepting turns).
- Assistant turn: `build_history` + voice-mode role-play prompt; pipe `llm.stream_chat` →
  `SentenceSplitter` → queue → `tts.synthesize` → `ws.send_bytes`; send `assistant_delta` for each
  delta; on first audio chunk send `state: speaking`; after TTS completes send `audio_end`, save the
  assistant message, send `assistant_turn`, then `state` idle/listening.
- LLM/STT/TTS errors → `error` event (`fatal=false`), state back to idle/listening; the user turn
  stays saved.
- `end_session` message → call `end_session` service (commit + enqueue), send `session_ended`,
  close 1000.
- Usage: record `stt` (`audio_seconds` = bytes / 32 000), `tts` (`characters`), `llm`.
- STT opening: buffer audio received while `open_session` is pending (at most 5 s of audio; drop
  the oldest beyond that) and send it in order once open; if opening fails → non-fatal
  `error speech_unavailable`, back to idle/listening.
- Hands-free idle: if listening lasts `HANDS_FREE_IDLE_SECONDS` without any transcript event, close
  the STT session, send `state idle` and `paused`, ignore audio until `resume` (then open a new
  STT session and send `state listening`).
- `delete_session` returns 409 `session_in_use` while the Redis key `voice:session:<id>` exists.
- DB sessions are opened only to load context or save a message — never across STT/LLM/TTS awaits.
- Replies use `TEMPERATURE["roleplay"]`; TTS gets exactly one flush per assistant turn.

**Subtasks:**
- [ ] 3.4.1 Failing unit tests `test_protocol.py`: parses each client message; rejects unknown type
  and invalid JSON; server events serialise with `type`.
- [ ] 3.4.2 Failing integration tests `test_voice_ws.py` (fakes; `httpx-ws`):
  - `test_rejects_text_mode_session_with_4409`
  - `test_rejects_other_users_session_with_4404`
  - `test_second_connection_is_rejected_with_4409`
  - `test_start_returns_ready_with_stt_model`
  - `test_ptt_turn_saves_user_message_with_speech_and_streams_reply` — sequence:
    start → ptt_down → 3 binary chunks → ptt_up → expect `state thinking`, `user_turn` with
    content `"hello um there"` (message content keeps filler words exactly as spoken; the
    filler flags live in `speech.words`), ≥1 `assistant_delta`, `state speaking`, binary audio,
    `audio_end`, `assistant_turn`, `state idle`.
  - `test_hands_free_turn_ends_on_end_of_turn` (5 chunks → fake emits end_of_turn)
  - `test_audio_ignored_while_idle_in_ptt_mode` (no user turn created)
  - `test_filler_only_turn_is_not_saved` (script with only "um")
  - `test_llm_error_sends_nonfatal_error_and_returns_to_idle`
  - `test_turn_limit_sends_limit_event`
  - `test_end_session_message_ends_and_queues_report`
  - `test_bad_message_sends_error_and_keeps_socket_open`
  - `test_turn_too_long_is_finalized` (fake clock advanced past 90 s)
  - `test_usage_events_recorded_for_stt_tts_llm`
  - `test_audio_sent_while_stt_is_opening_is_not_lost` (fake `open_delay_s=0.2`; every chunk
    reaches `received_chunks` in order)
  - `test_hands_free_pauses_after_idle_and_resumes` (`silent=True` fake; clock past 20 s →
    `paused`; `resume` → `state listening`)
  - `test_delete_session_with_open_voice_socket_returns_409`
- [ ] 3.4.3 Run → FAIL. Implement. Run → PASS.
- [ ] 3.4.4 Manual check with real Deepgram + Ollama using a tiny script
  `apps/api/spikes/deepgram/ws_client.py` that streams `hello_um.wav` over the WebSocket and saves
  received audio to a WAV; listen to it.
- [ ] 3.4.5 Commit: `feat(api): add voice session relay over websocket`

**Pitfalls:** never `await ws.send_*` from two tasks at once without a lock (use an
`asyncio.Lock` in a `send_json`/`send_bytes` helper); Deepgram connections time out when idle —
open per turn as designed; uvicorn `--reload` kills sockets (expected).

---

### Task 3.5 — Report: speaking stats and fluency

**Goal:** Voice session reports include `voice_metrics` and a `fluency` dimension.
**Depends on:** 3.2 (can run in parallel with 3.3/3.4)
**Files:** Modify `app/services/feedback.py`, `app/services/scoring.py` (voice grammar-fix
filter), `app/llm/prompts/feedback_user.md.j2` (speech-recognition note); Test
`tests/integration/services/test_feedback_voice.py`, `tests/unit/services/test_scoring.py`.

**Subtasks:**
- [ ] 3.5.1 Failing tests: voice session with speech on user messages → report has `voice_metrics`,
  8 dimension scores (fluency last, reason from `fluency_reason`), overall includes fluency, 8
  `skill_scores`; `speaking_summary` appears in the rendered user prompt (assert via fake LLM
  capturing the prompt); text session unchanged (7 dims, `voice_metrics` null); voice session whose
  user messages have no speech data → `voice_metrics` null, 7 dims; the fluency `skill_scores` row
  has `scorer="metrics:v1"` and no `rubric_version`; for voice sessions the user prompt says USER
  lines come from speech recognition; a grammar fix whose `original` contains a word with
  confidence < 0.60 is dropped while one on high-confidence words is kept (unit test on
  `filter_grammar_fixes(..., speech_by_message=...)` — a new keyword-only parameter
  `speech_by_message: dict[UUID, SpeechData] | None = None` added to the Phase 2 function).
- [ ] 3.5.2 Run → FAIL. Implement. Run → PASS. `make gen-client` if schemas changed.
- [ ] 3.5.3 Commit: `feat(api): add speaking stats and fluency to voice reports`

---

### Task 3.6 — Web audio library

**Goal:** Capture, chunk, send, receive and play audio reliably.
**Depends on:** 3.4
**Read before starting:** `voice-and-pronunciation.md` §1–2.
**Files:** `public/worklets/pcm-capture-processor.js`, `src/lib/audio/{pcm,mic-capture,pcm-player,voice-socket}.ts`,
`src/lib/api/events.ts`. Tests `tests/lib/audio/{pcm,voice-socket}.test.ts`.

**Interfaces (produces):**
```ts
// pcm.ts (pure)
export function downsample(input: Float32Array, inRate: number, outRate: number): Float32Array
export function floatToInt16(input: Float32Array): Int16Array      // clamps to [-1, 1]
export function int16ToFloat32(input: Int16Array): Float32Array
export function rms(input: Float32Array): number
export class PcmChunker {                                            // accumulates and emits fixed-size chunks
  constructor(opts: { inRate: number; outRate?: 16000; chunkSamples?: 1600; onChunk: (c: Int16Array) => void })
  push(frame: Float32Array): void
  flush(): void
}
// mic-capture.ts
export class MicPermissionError extends Error {}
export interface AudioSource { start(onChunk: (c: Int16Array) => void): Promise<void>; stop(): void; readonly level: number }
export class MicCapture implements AudioSource { … }
// pcm-player.ts
export interface AudioSink { resume(): Promise<void>; enqueue(pcm16: ArrayBuffer): void; stop(): void; onDrained(cb: () => void): () => void }
export class PcmPlayer implements AudioSink { constructor(sampleRate?: 24000) }
// voice-socket.ts
export type VoiceClientMessage = …   // mirrors protocol
export type VoiceServerEvent = … | { type: "audio"; data: ArrayBuffer }
export class VoiceSocket {
  constructor(url: string, WebSocketImpl?: typeof WebSocket)
  connect(): Promise<void>; send(m: VoiceClientMessage): void; sendAudio(c: Int16Array): void
  onEvent(cb: (e: VoiceServerEvent) => void): () => void; close(): void
  readonly closeCode: number | null
}
```

**Subtasks:**
- [ ] 3.6.1 Failing tests `pcm.test.ts`: downsample 48k→16k length and averaging; identity when
  rates equal; `floatToInt16` clamps and scales (1.0 → 32767, −1.0 → −32768); chunker emits exact
  1600-sample chunks across uneven pushes and flushes the remainder.
- [ ] 3.6.2 Failing tests `voice-socket.test.ts` (mock WebSocket class): JSON events parsed and
  typed; binary frames emitted as `audio`; `sendAudio` sends the underlying buffer slice; close code
  exposed; unknown event types ignored with a console warning.
- [ ] 3.6.3 Run → FAIL. Implement (the worklet is ~20 lines: `process(inputs)` posts
  `inputs[0][0].slice()` when present; returns `true`). Run → PASS.
- [ ] 3.6.4 Commit: `feat(web): add audio capture, playback and voice socket libraries`

**Pitfalls:** `AudioContext` must be created/resumed inside a user gesture; `slice()` the worklet
buffer (it's reused); binary WebSocket frames need `binaryType = "arraybuffer"`.

---

### Task 3.7 — Web: voice session UI and speaking stats

**Goal:** Voice sessions are fully usable; reports show speaking stats.
**Depends on:** 3.5, 3.6
**Files:** `src/features/voice/*`, session page (render voice view when `mode === "voice"`),
scenario detail (enable "Start voice practice"), `src/features/reports/components/speaking-stats.tsx`.
Tests `tests/features/voice/*.test.tsx`, `tests/features/reports/speaking-stats.test.tsx`.

**Interfaces (produces):**
```ts
export function useVoiceSession(opts: { sessionId: string; inputMode: "push_to_talk" | "hands_free";
  source?: AudioSource; sink?: AudioSink; socketFactory?: (url: string) => VoiceSocket }): {
  phase: "not_started" | "connecting" | "ready" | "ended" | "failed";
  state: "idle" | "listening" | "thinking" | "speaking"; paused: boolean;
  interimText: string; messages: MessageOut[]; assistantDraft: string;
  level: number; elapsedSeconds: number; error: { code: string; message: string } | null;
  start(): Promise<void>; pttDown(): void; pttUp(): void; resume(): void; end(): Promise<void>; reconnect(): Promise<void>;
}
```

**Behaviour:**
- Start screen: "Start voice session" (user gesture creates AudioContexts and asks for the mic),
  input-style toggle (default from `/settings`), tip "Hold Space or the button to talk".
- Mic permission denied → message with steps to allow the microphone for `localhost:3000`.
- Main view: state indicator (icon + text: "Ready — hold to talk", "Listening…", "Thinking…",
  "Speaking…") in an `aria-live="polite"` region; large push-to-talk button (pointerdown/up +
  Space keydown/keyup; ignores key repeat; releases on window blur); hands-free shows a pulsing
  "Listening" state with the mic level meter; interim transcript shown in a muted bubble; messages
  list as in text mode; timer "mm:ss / 20:00"; turns left; "End session".
- Client stops sending audio when state ≠ listening; stops playback on end/unmount.
- Errors: non-fatal error → toast with `errorMessage(code)`; socket closed unexpectedly →
  "Connection lost" + "Reconnect".
- `paused` → "Paused — tap to continue" button that sends `resume` (Space also resumes).
- `limit` events → explanatory banner; `session_too_long` → session ends.
- After `session_ended` → same ended panel as text with "View your report".
- Report page `SpeakingStats`: WPM with the 110–170 target band (or "Not enough speech to measure
  pace yet" when `pace_measured` is false), filler count + rate + example
  chips, long pauses per minute, "Words that were hard to catch" with the note "This can be caused
  by background noise or speaking fast — it doesn't necessarily mean mispronunciation.", fluency
  appears in the skills list.

**Subtasks:**
- [ ] 3.7.1 Failing hook/component tests with fake `AudioSource`, `AudioSink` and socket:
  start sends `start` with the chosen input mode; Space down/up sends `ptt_down`/`ptt_up` once
  (repeat ignored); audio only forwarded while listening; `user_turn`/`assistant_turn` update the
  list; binary audio goes to the sink; state indicator text changes; permission error message;
  unexpected close shows "Connection lost"; `session_ended` shows the report link; `paused` shows
  the continue button, which sends `resume`.
- [ ] 3.7.2 Failing tests for `SpeakingStats` (renders values, hides when null, wording of the
  hard-to-catch note, "not enough speech" text when `pace_measured` is false).
- [ ] 3.7.3 Run → FAIL. Implement. Run → PASS. `make lint`.
- [ ] 3.7.4 Browser check with real Deepgram + Ollama (`make dev`): two PTT turns and two
  hands-free turns; audio plays smoothly; no echo loop (headphones off test); console clean.
  Record end-of-turn → first audio latency in the completion log.
- [ ] 3.7.5 Commit: `feat(web): add voice practice session and speaking stats`

---

### Task 3.8 — E2E: voice journey

**Files:** `apps/web/e2e/voice-practice.spec.ts`.
- [ ] 3.8.1 Spec (fake providers, fake mic): open "Daily stand-up update" → "Start voice
  practice" → "Start voice session" → hold the talk button 1.5 s (mouse down/up) → user message
  "hello um there" visible → assistant message visible → state returns to "Ready" → **second** PTT
  turn (a report needs ≥ 2 user turns) → End session → View report → "Speaking stats" shows
  2 filler words and "Not enough speech to measure pace yet" (the fake turns are too short to
  measure).
- [ ] 3.8.2 `make test-e2e` → PASS. Update phase status. Commit:
  `test(web): add voice practice e2e journey`

## Phase verification

1. Real voice session (`make dev`, Deepgram + Ollama): 4 turns mixing PTT and hands-free; persona
   replies are short and spoken naturally; no markdown read aloud.
2. Say something with deliberate "um"s → report shows them; speak very fast → pace flagged.
3. Disconnect Wi-Fi mid-session → friendly error; reconnect works; session continues.
4. Deny the mic permission → clear instructions.
5. 20-minute limit verified with a temporarily lowered limit in a test (not manually).
6. `make check` and `make test-e2e` → PASS. Deepgram usage for the phase noted in the log.

## Completion log

<!-- Append: - YYYY-MM-DD · Task N.M · commits · evidence · Notes · Follow-ups -->

- 2026-09-23 · Task 3.1 · commit 8dbec79 · ADR-0013 written with measured evidence for all seven
  questions (real Deepgram calls against two owner-recorded clips); `make check` ✅ (214 api + 45
  web passed) · Notes: Nova-3 ships (Flux has no filler-word feature and never reached `EndOfTurn`
  within 3.3s on either clip). `deepgram-sdk` 5.3.4 added as a dependency (needed to run the spike
  itself, one task earlier than Task 3.3's file map implies). Found three real SDK-vs-docs gaps by
  reading the installed source, not by guessing: (1) `listen.v1/v2.connect()` have no
  `filler_words` kwarg and silently ignore `request_options["additional_query_parameters"]` for
  WS connects — getting `filler_words=true` onto the wire needs a hand-built `websockets.connect()`
  (proven working, transcript showed "um"/"uh"); (2) the documented `send_finalize()` /
  `send_close_stream()` / `send_flush()` / `send_close()` convenience methods don't exist — the
  real API is `send_control(<Type>ControlMessage(type=...))` with message types imported from
  `deepgram.extensions.types.sockets`, not the documented `deepgram.listen.v1.types`; (3)
  `connection.start_listening()` blocks until close and must run via `asyncio.create_task(...)`,
  not be awaited inline — awaiting it inline stalls audio sending until Deepgram's ~10-13s
  inactivity timeout (`net0001`) closes the socket. All three are recorded in ADR-0013's
  "Implications for Task 3.3" so the production adapter doesn't rediscover them. Push-to-talk
  finalize latency measured at 0.36s vs. ~3.3s for natural endpointing — matches the architecture's
  plan to call `Finalize` on `ptt_up`. TTS: all six curated Aura-2 voices confirmed to exist,
  ~0.36-0.38s first-byte latency; `speed` works via REST only (confirmed by byte-length scaling
  0.7x/1.0x/1.5x), not on the live `speak.v1` WebSocket — the planned AI-speaking-speed setting
  (F12) is dropped, documented in `product-spec.md` and `voice-and-pronunciation.md` §7.
  Follow-ups: re-check for a `deepgram-sdk` patch release before Task 3.3 in case any of the three
  gaps are fixed upstream.

- 2026-09-23 · Task 3.2 · commit 87c8d65 · `make check` ✅ (249 api + 45 web passed, 35 new
  voice unit tests) · Notes: added `SpeechWord`/`SpeechData` to `app/schemas/json_types.py`
  (binding shapes from `data-model.md`, not yet created by an earlier task but required by
  `compute_voice_metrics`'s signature). `fillers.py`: `is_filler` strips ASCII punctuation and
  lower-cases before matching `FILLER_TOKENS`; provider flag wins when not `None`. `metrics.py`:
  pace (`wpm`) is computed only from turns with ≥3 non-filler words, using *those turns'* own
  summed word count and duration (not diluted by short turns' duration) — an explicit reading of
  the "Initial heuristic" note, since the spec doesn't pin down whether short turns' duration
  should count toward the denominator. `hard_to_catch_words`/`filler_examples` cap by keeping the
  first N distinct values in encounter order. `fluency_score` forces 1 whenever zero words (filler
  or not) were spoken at all, overriding the additive formula (which would otherwise leave a
  no-turns/no-speech case at the default 5). `sentences.py`: the ≥20-char gate applies to the
  *whole current buffer*, not the candidate sentence itself — once the buffer reaches 20 chars, it
  splits at the *earliest* sentence-end found within it (which can be well before char 20); this
  is what makes "Hello there. How are you?" resolve to two chunks when streamed char-by-char (the
  first split happens retroactively once the buffer crosses 20 chars, then the 12-char remainder
  "How are you?" never re-crosses 20 chars and comes out via `flush()` instead).

- 2026-09-24 · Task 3.3 · commit 6d0327a · `make check` ✅ (278 api + 45 web passed; 5
  live tests correctly deselected by default); `make test-live` ✅ (2/2 passed against real
  Deepgram: streaming STT on `tests/fixtures/audio/hello_um.wav` produced a final transcript with
  words, TTS produced non-empty MP3 bytes) · Notes: **deviated from the planned interface** for
  `DeepgramSpeechToText` — updated Task 3.3's own "Interfaces" block above before writing code
  (agent-workflow.md's "spikes may change later subtasks" rule): it now takes a `connector`
  (raw-websocket seam) instead of `client_factory: Callable[[], AsyncDeepgramClient]`, because
  ADR-0013 showed the typed SDK client can't carry `filler_words` for streaming — using it as
  originally planned would have silently broken Task 3.2's whole filler-rate feature in
  production. `DeepgramTextToSpeech` keeps the originally planned `client_factory` design (ADR-0013
  found no SDK gap there). Added `SpeechWord`-per-message parsing: a Nova-3 message can carry a
  final transcript *and* `speech_final=true` at once, so `_parse_message` can emit both a `final`
  and an `end_of_turn` `TranscriptEvent` from a single wire message — confirmed against the real
  event shapes from the Task 3.1 spike output, now also captured as JSON fixtures under
  `tests/fixtures/deepgram/`. Added `websockets` as an explicit dependency (already resolved
  transitively via `deepgram-sdk`, just not previously pinned directly). Live-test fixture:
  copied the owner's real `spikes/deepgram/audio/clip-a.wav` recording to
  `tests/fixtures/audio/hello_um.wav` — owner explicitly chose the real recording over a
  synthetic TTS fixture when asked (synthetic audio has no real fillers per the architecture doc,
  so it would exercise the pipeline less realistically). `GET /voices` and `GET /tts/preview`
  match `api-contract.md` §2 exactly; `SettingsUpdate.tts_voice` now validates against
  `is_known_voice()` (422 on unknown, matching the existing `_valid_timezone` validator pattern).
  `FakeTextToSpeech.synthesize_mp3` returns a real ~480-byte MP3 (silence) generated once via
  `ffmpeg`/`libmp3lame` and embedded as base64 in `app/voice/fake_assets.py`, not empty bytes, so
  a browser or test asserting on content-type/playability doesn't get a decode error.
  Follow-ups: none — `deepgram-sdk` still at 5.3.4 (latest 5.x on PyPI as of this check), so the
  raw-websocket workaround stays necessary.
