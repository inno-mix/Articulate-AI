# Voice & Pronunciation

> Deepgram (STT + TTS) via the official Python SDK v5 (`deepgram-sdk`, `AsyncDeepgramClient`).
> Azure AI Speech pronunciation assessment (scripted mode).
> Look up current APIs with Context7 before coding: `/deepgram/deepgram-python-sdk`,
> `/websites/developers_deepgram`, `/websites/learn_microsoft_en-us_azure_ai-services_speech-service`.

## 1. Audio formats (binding)

| Direction | Format | Chunking |
|---|---|---|
| Browser mic → API (voice session) | Raw PCM16 little-endian, mono, **16 000 Hz** | binary WS frames of ~100 ms (3 200 bytes) |
| API → Deepgram STT | same bytes, `encoding=linear16`, `sample_rate=16000` | forwarded as received |
| Deepgram TTS → API → browser | Raw PCM16 LE, mono, **24 000 Hz** (`encoding=linear16`, `sample_rate=24000`) | forwarded as received (binary WS frames) |
| Browser → API (pronunciation, drills) | WAV (RIFF, PCM16, mono, 16 000 Hz) | single multipart upload |
| TTS preview | MP3 (`audio/mpeg`) from Deepgram REST | single response |

Browser capture (`apps/web/src/lib/audio/mic-capture.ts`):
- `getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true,
  channelCount: 1 } })`.
- `AudioContext` + `AudioWorkletNode` loading `/worklets/pcm-capture-processor.js`. The worklet
  only copies channel 0 of each render quantum and posts it to the main thread.
- On the main thread, `PcmChunker` (`src/lib/audio/pcm.ts`, pure and unit-tested) downsamples from
  the context rate (usually 48 000) to 16 000 by averaging, converts Float32 → Int16, and emits
  1 600-sample (100 ms) chunks.
- Exposes `start(onChunk)`, `stop()`, `level` (RMS 0–1 for the meter).

Browser playback (`pcm-player.ts`): an `AudioContext({ sampleRate: 24000 })` that schedules each
received Int16 chunk as an `AudioBuffer` back-to-back (`nextStartTime` queue); emits `drained`
when the queue empties; `stop()` clears the queue.

WAV writer (`wav.ts`): `encodeWav(int16Chunks: Int16Array[], sampleRate = 16000): Blob` (44-byte
header).

## 2. Voice session WebSocket — `WS /api/v1/sessions/{id}/voice`

### 2.1 Handshake
- All phases: the request guard (Phase 0) closes the socket with `4403` if an `Origin` header is
  present and not in `CORS_ORIGINS`, and rejects unknown `Host` headers.
- Q1: no auth. Q2: cookie auth (close `4401` without a valid session); `Origin` becomes required.
- Session must exist, belong to the user, `mode=voice`, `status=active`; otherwise close `4404` /
  `4409`.
- Only one active voice socket per session (second connection → close `4409`).

### 2.2 Messages — client → server
| Frame | Payload | Meaning |
|---|---|---|
| text | `{"type":"start","input_mode":"push_to_talk"\|"hands_free"}` | must be first; server replies `ready` |
| binary | PCM16 16 kHz chunk | ignored unless state is `listening` (hands-free) or PTT is held |
| text | `{"type":"ptt_down"}` | push-to-talk pressed → state `listening` |
| text | `{"type":"ptt_up"}` | push-to-talk released → server finalizes STT and ends the turn |
| text | `{"type":"cancel_turn"}` | discard the current user turn (nothing saved) |
| text | `{"type":"resume"}` | hands-free only: leave `paused` and start listening again |
| text | `{"type":"end_session"}` | end the session (same as REST end) |
| text | `{"type":"ping"}` | server replies `pong` |

### 2.3 Messages — server → client
| Frame | Payload |
|---|---|
| text | `{"type":"ready","state":"idle"\|"listening","stt_model":"nova-3"}` |
| text | `{"type":"state","value":"idle"\|"listening"\|"thinking"\|"speaking"}` |
| text | `{"type":"transcript","text":"...","is_final":false}` (interim, for live display) |
| text | `{"type":"user_turn","message":MessageOut}` (saved user message) |
| text | `{"type":"assistant_delta","text":"..."}` |
| text | `{"type":"assistant_turn","message":MessageOut}` (saved assistant message) |
| binary | PCM16 24 kHz TTS audio |
| text | `{"type":"audio_end"}` (no more TTS audio for this turn) |
| text | `{"type":"limit","reason":"turn_too_long"\|"session_too_long"\|"turn_limit_reached"\|"daily_voice_limit"}` (`daily_voice_limit` from Phase 10) |
| text | `{"type":"error","code":"speech_unavailable"\|"llm_unavailable"\|...,"message":"...","fatal":bool}` |
| text | `{"type":"session_ended","status":"ended"\|"abandoned","report_status":"pending"\|null}` |
| text | `{"type":"paused","reason":"no_speech"}` (hands-free: 20 s of listening without speech) |
| text | `{"type":"pong"}` |

### 2.4 Server state machine (`app/voice/relay.py` → `VoiceSessionRelay`)

```
idle ──ptt_down / (hands_free: start)──► listening
listening ──ptt_up / STT end-of-turn──► thinking      (empty transcript → back to listening/idle)
thinking ──first TTS audio──► speaking
speaking ──all TTS audio sent + audio_end──► idle (PTT) | listening (hands-free)
listening (hands-free) ──20 s without any transcript──► idle + `paused` event   (STT connection closed)
idle (paused) ──resume──► listening
any ──end_session / limit / fatal error──► closed
```
- Audio frames received in `thinking`/`speaking` are dropped (no barge-in). The client also stops
  sending while not listening.
- Turn > 90 s → finalize the turn early and send `limit: turn_too_long`.
- Hands-free idle: `HANDS_FREE_IDLE_SECONDS = 20` (in `app/domain/limits.py`); on pause the server
  sends `state` `idle` and `paused`, closes the STT connection and ignores audio until `resume`.
- Session > 20 min → send `limit: session_too_long`, end the session.
- User turn saved only if the final transcript has ≥ 1 non-filler word.
- The client may disconnect at any time; the relay closes Deepgram connections and leaves the
  session `active` (the user can reconnect).

### 2.5 Turn pipeline
1. **STT:** one Deepgram streaming connection per user turn (opened on `listening`, closed at end of
   turn) to keep costs low and avoid idle timeouts. Params (Nova-3 path):
   `model=nova-3, language=en-US, encoding=linear16, sample_rate=16000, channels=1,
   interim_results=true, punctuate=true, smart_format=true, filler_words=true,
   endpointing=<ms>, utterance_end_ms=1000, vad_events=true, mip_opt_out=true`, plus `keyterm`
   for the scenario's technical terms (≤ 20). Flux path uses
   `client.listen.v2.connect(model="flux-general-en", …, mip_opt_out=true)` and its end-of-turn
   events. **The spike (Phase 3, Task 3.1) decides which path ships.**
   Opening the connection takes time: audio chunks that arrive while it is opening are buffered in
   order (max 5 s, oldest dropped beyond that) and sent as soon as it is open, so the first words of
   a turn aren't lost. If opening fails, the turn fails with `speech_unavailable`.
2. Final result words → `SpeechWord` list (`is_filler` = Deepgram-tagged filler or token in
   `FILLER_TOKENS`) → saved in `messages.speech`.
3. **LLM:** `stream_chat` with the voice-mode role-play prompt.
4. **Sentence splitting** (`app/voice/sentences.py`): buffer deltas; emit a chunk when the buffer
   contains a sentence end (`.`, `?`, `!` followed by whitespace or end) and is ≥ 20 chars, or when
   it exceeds 200 chars at a comma/space; flush the rest at the end.
5. **TTS:** one Deepgram speak WebSocket per assistant turn (`client.speak.v1.connect(model=<voice>,
   encoding="linear16", sample_rate=24000, mip_opt_out=true)`); send each sentence with
   `send_text` as soon as the splitter emits it; send **one** `send_flush` when the LLM reply is
   complete (never per sentence — Deepgram allows 20 flushes per 60 s and frequent flushes lower
   audio quality); forward audio bytes to the browser as they arrive; after `Flushed` + queue empty,
   send `audio_end`.
6. Save the assistant message; record `usage_events` (`stt` seconds, `tts` characters, `llm`).

### 2.6 Provider interfaces (binding) — `app/voice/base.py`

```python
@dataclass(frozen=True)
class TranscriptEvent:
    kind: Literal["interim", "final", "end_of_turn"]
    text: str
    words: list[SpeechWord]          # empty for interim

class SpeechToTextSession(Protocol):
    async def send_audio(self, chunk: bytes) -> None: ...
    async def finalize(self) -> None: ...          # flush remaining audio, request final result
    def events(self) -> AsyncIterator[TranscriptEvent]: ...
    async def close(self) -> None: ...

class SpeechToText(Protocol):
    model: str
    async def open_session(self, *, keyterms: list[str]) -> SpeechToTextSession: ...

class TextToSpeech(Protocol):
    def synthesize(self, *, voice: str, sentences: AsyncIterator[str]) -> AsyncIterator[bytes]: ...
    async def synthesize_mp3(self, *, voice: str, text: str) -> bytes: ...

class PrerecordedTranscriber(Protocol):
    async def transcribe_wav(self, wav: bytes, *, keyterms: list[str]) -> SpeechData: ...
```
Fakes (`app/voice/fake.py`): `FakeSpeechToText(script: list[TranscriptEvent])` emits the script
after `finalize()`; `FakeTextToSpeech` yields 2 400 zero bytes (50 ms) per sentence and a tiny valid
MP3 for previews; `FakePrerecordedTranscriber(result: SpeechData | None = None)` — the default
result uses the same three words as the default `FakeSpeechToText` script.
Fakes are only used when the matching `*_PROVIDER=fake` is set.

Missing keys: the Deepgram and Azure adapters are created lazily. If `DEEPGRAM_API_KEY` or the Azure
settings are missing, the app still starts (earlier phases don't need them); the first voice or
pronunciation request fails with 503 `speech_unavailable` / `pronunciation_unavailable` and the
message "… is not configured".

## 3. Speaking stats — `app/voice/metrics.py` (pure functions, fully unit-tested)

```python
FILLER_TOKENS = {"uh", "um", "uhm", "erm", "er", "ah", "hmm", "mhm", "mm"}
LONG_PAUSE_S = 2.0
LOW_CONFIDENCE = 0.60

def compute_voice_metrics(turns: list[SpeechData]) -> VoiceMetrics: ...
```
- `speaking_seconds` = Σ turn `duration_s`.
- `words` = count of non-filler words; `wpm` = non-filler words ÷ minutes, computed only over turns
  with ≥ 3 non-filler words; `pace_measured` = at least one such turn exists (otherwise `wpm = 0`
  and the pace penalty below is skipped).
- `filler_count` = count of filler words; `filler_rate_per_100` = `filler_count / max(words,1) * 100`.
- `long_pause_count` = gaps `next.start - prev.end > 2.0` within a turn;
  `long_pauses_per_min` = `long_pause_count / (speaking_seconds / 60)`.
- `hard_to_catch_words` = distinct lower-cased non-filler words with confidence < 0.60 (≤ 10).
- `fluency_score` (1–5): start at 5, subtract:
  - pace: −1 if `wpm` outside 110–170; −2 if outside 90–190
  - fillers: −1 if rate > 3; −2 if rate > 6
  - pauses: −1 if `long_pauses_per_min` > 2
  - clamp to 1..5. (Initial heuristic — tune with real recordings; keep constants in one place.)
- Turns with < 3 non-filler words are excluded from pace (too short to measure).
- No speech at all → counts 0, `wpm = 0`, `fluency_score = 1`.

UI wording rule: "hard to catch" words are **never** called pronunciation errors.

## 4. Pronunciation assessment (Azure)

### 4.1 Interface (binding) — `app/pronunciation/base.py`
```python
@dataclass(frozen=True)
class PronunciationResult:
    pron_score: float
    accuracy: float
    fluency: float
    completeness: float
    words: list[WordAssessment]
    duration_ms: int

class PronunciationAssessor(Protocol):
    provider: str
    async def assess(self, *, wav: bytes, reference_text: str, locale: str = "en-US") -> PronunciationResult: ...
```
Errors (in `app/core/errors.py`): `PronunciationUnavailableError` (503
`pronunciation_unavailable`), `InvalidAudioError` (400 `invalid_audio`) and its subclass
`NoSpeechRecognisedError`.
Fake: `FakePronunciationAssessor` returns 90 for every word except words listed in
`low_words` (score 40, `Mispronunciation`).

### 4.2 Azure call (default: REST API for short audio)
- `POST https://{AZURE_SPEECH_REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-US&format=detailed`
- Headers: `Ocp-Apim-Subscription-Key: <AZURE_SPEECH_KEY>`,
  `Content-Type: audio/wav; codecs=audio/pcm; samplerate=16000`, `Accept: application/json`,
  `Pronunciation-Assessment: base64(json)` with
  `{"ReferenceText": <sentence>, "GradingSystem": "HundredMark", "Granularity": "Phoneme",
  "Dimension": "Comprehensive", "EnableMiscue": true}`.
- Limits: audio ≤ 30 s (REST short audio limit for pronunciation). Timeout 15 s. Retry once on
  5xx/timeout; 429 → `PronunciationUnavailableError` with retry hint.
- Parse `NBest[0]`: `PronunciationAssessment.{AccuracyScore, FluencyScore, CompletenessScore,
  PronScore}`; `Words[].{Word, PronunciationAssessment.{AccuracyScore, ErrorType}, Phonemes[]}`.
- **Spike (Phase 4, Task 4.1):** confirm the endpoint form for the created resource, the JSON
  shape, whether phoneme scores are returned via REST, and whether "heard as" (N-best phonemes) is
  available only through the Speech SDK (`azure-cognitiveservices-speech`,
  `PronunciationAssessmentConfig` + `NBestPhonemeCount`). If the SDK is needed for `heard_as`, the
  adapter uses the SDK with a push stream; otherwise REST ships and `heard_as` stays `null`.
- Free tier (F0): 5 audio hours/month, **1 concurrent request** → the service serialises Azure
  calls with an `asyncio.Semaphore(settings.azure_speech_max_concurrency)` (default 1).

### 4.3 WAV validation — `app/pronunciation/wav.py`
`validate_wav(data: bytes, *, max_seconds: float) -> WavInfo` using the stdlib `wave` module:
RIFF/WAVE, `nchannels == 1`, `sampwidth == 2`, `framerate == 16000`, duration 0.3 s ≤ d ≤ max.
Otherwise raise `InvalidAudioError` (→ 400 `invalid_audio`).

### 4.4 Score presentation
- Word colours: ≥ 80 green ("good"), 60–79 amber ("close"), < 60 red ("practise").
  Always show the number and a text label as well (accessibility).
- `error_type` labels: `Omission` → "skipped", `Insertion` → "extra word",
  `Mispronunciation` → "mispronounced".
- Weak word rule (coach notes/drills): same word (case-insensitive) with accuracy < 60 in ≥ 2
  attempts within 30 days.

## 5. Deepgram pre-recorded (drills) — `app/voice/deepgram_prerecorded.py`
`transcribe_wav` → Deepgram pre-recorded API with `model=nova-3, language=en-US, punctuate=true,
smart_format=true, filler_words=true, mip_opt_out=true`; returns `SpeechData`. Max 90 s. Check the SDK method name
with Context7 (`client.listen.v1.media.transcribe_file` in SDK v5 at time of writing).

## 6. Deepgram data use (binding) — `app/voice/deepgram_common.py`
Every Deepgram request sets `mip_opt_out=true` (ADR-0016, security rule S13): streaming STT
(`listen.v1` and `listen.v2`), pre-recorded STT, the TTS WebSocket and the TTS REST call used for
previews (`/v1/speak?...&mip_opt_out=true`). Adapters get their shared options from
`deepgram_request_options() -> dict[str, Any]` in this module instead of repeating the flag, and
their unit tests assert it. Spike scripts and live tests set it too.

## 7. Curated TTS voices — `app/voice/voices.py`
Six Aura-2 English voices, e.g. `aura-2-thalia-en`, `aura-2-asteria-en`, `aura-2-andromeda-en`,
`aura-2-apollo-en`, `aura-2-arcas-en`, `aura-2-helena-en`. **Verify each id exists** in Deepgram's
current voice list during the Phase 3 spike; replace any that don't.
