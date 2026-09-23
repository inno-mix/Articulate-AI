# 0013. Deepgram STT model, TTS voices and parameters (Phase 3 spike)

- Status: Accepted
- Date: 2026-09-23

## Context

Phase 3 (voice practice) needs a decision between Nova-3 (`listen.v1`) and Flux (`listen.v2`) for
streaming STT, per ADR-0003. Task 3.1 ran real audio against both models with
`deepgram-sdk` 5.3.4 (the pinned major version) and recorded the evidence below. Two real clips
were used (owner-recorded, 16 kHz mono PCM16, converted with `afconvert`):

- `clip-a` (~16.4s): a stand-up update with natural "um"/"uh", mentioning "Kubernetes" and
  "PostgreSQL".
- `clip-b` (~6.6s): a short answer ending with a clear ~2s silence.

Full evidence and the scripts that produced it live in `apps/api/spikes/deepgram/` (throwaway,
never imported by the app). Every request set `mip_opt_out=true`.

**Headline finding, independent of the model choice:** `deepgram-sdk` 5.3.4's *typed* streaming
methods diverge substantially from both the Context7-indexed docs and the raw WebSocket protocol.
Three gaps were found by reading the installed SDK source (not by guessing) and confirmed live:

1. `client.listen.v1.connect()` and `client.listen.v2.connect()` have **no `filler_words` kwarg**,
   and `request_options["additional_query_parameters"]` is **silently dropped** for WebSocket
   connects (only `additional_headers` is applied — confirmed by reading
   `listen/v1/client.py`/`listen/v2/client.py`/`speak/v1/client.py`). The REST-documented
   convenience methods `send_finalize()`, `send_close_stream()`, `send_keep_alive()` (listen) and
   `send_flush()`/`send_close()` (speak) **do not exist**; the real API is
   `send_control(ListenV1ControlMessage(type="Finalize" | "CloseStream" | "KeepAlive"))` /
   `send_control(SpeakV1ControlMessage(type="Flush" | "Clear" | "Close"))`, with the message types
   imported from `deepgram.extensions.types.sockets` (not the documented
   `deepgram.listen.v1.types` / `deepgram.speak.v1.types`, which don't exist in this version).
2. `connection.start_listening()` is a **blocking receive loop** (`async for message in
   websocket`) that only returns on close. It must be run as a background task
   (`asyncio.create_task(connection.start_listening())`) concurrently with sending audio — awaiting
   it inline (as the SDK's own async example implies) stalls the send loop until Deepgram's
   ~10-13s inactivity timeout closes the socket with error `net0001`.
3. `client.speak.v1.audio.generate()` returns `typing.AsyncIterator[bytes]` (an async generator of
   chunks), not an object with `.stream.getvalue()` as shown in the docs. It also has **no
   `speed` kwarg**; `request_options["additional_query_parameters"]` **does** work here (REST
   calls go through `http_client.py`, which does apply it), confirmed by `speed` measurably
   changing output byte length (see §5).

These are all Task 3.3 implementation constraints, not scoring/decision inputs — see
"Implications for Task 3.3" below.

## Decision

**Ship Nova-3** (`listen.v1`, `model=nova-3`) for streaming STT. Flux is not used in Q1.

Per the decision rule in the task: prefer the model that returns filler words *and* word timings;
if both do, prefer lower end-of-turn latency; if Flux lacks fillers, choose Nova-3. Flux lacks a
working filler-word signal (§2) and did not reach `EndOfTurn` within a 3s post-audio window on
either clip (§3), so Nova-3 wins outright — the latency tiebreaker was never reached.

## Evidence

### 1. Nova-3 word timings/confidence (Q1, part 1)

Both streaming and pre-recorded Nova-3 responses return per-word `start`, `end`, `confidence`,
`punctuated_word` (no `speaker`/`language` used yet). Example word from a streaming `Results`
event:
```json
{"word": "so", "start": 0.08, "end": 0.4, "confidence": 0.88, "punctuated_word": "So,"}
```

### 2. Filler words (Q1, part 2 / Q2)

- **Nova-3**: no explicit "is this a filler" flag on the word object — fillers are returned as
  literal transcribed tokens ("um", "uh") only when `filler_words=true` is actually sent. Because
  of SDK gap #1 above, the typed `listen.v1.connect()` **cannot** send `filler_words=true`, so a
  streaming connection through the SDK silently strips "um"/"uh" (Deepgram's documented default
  behaviour when the flag is unset). Confirmed with two side-by-side runs of `clip-a`:
  - Via the SDK's typed `connect()` (flag unreachable): *"So, yesterday, I finished the migration
    script for the [...] database, and today I'm going to look into why the Kubernetes pods keep
    restarting in staging. It's probably a memory limit issue..."* — no fillers.
  - Via a raw `websockets.connect()` with `filler_words=true` built into the query string by hand
    (bypassing the SDK's `connect()`, same audio/model/params otherwise): *"So, **um**, yesterday,
    I finished the migration script for the [...] database, and, **uh**, today I'm going to look
    into why the Kubernetes pods keep restarting in staging. It's, **um**, probably a memory limit
    issue..."* — fillers present.
  - `listen.v1.media.transcribe_file()` (pre-recorded/batch): `filler_words` **is** a real typed
    kwarg here (unlike the streaming connect methods) and worked first try: *"So, **um**,
    yesterday, I finished the migration script for the PostgreSQL database. And, **uh**, today,
    I'm going to look into why the Kubernetes pods keep restarting in staging..."*
- **Flux**: no filler flag or filler tokens appear anywhere in Deepgram's own Flux event examples
  (`Update`/`StartOfTurn`/`EagerEndOfTurn`/`EndOfTurn`, checked via Context7), and the SDK's
  `listen.v2.connect()` has no `filler_words` kwarg either. Flux has no documented filler-word
  feature at all, streaming or otherwise.

### 3. End-of-turn latency (Q2, Q3)

| Run | Model | Trigger | Delay after last audio chunk |
|---|---|---|---|
| `clip-a`, natural endpointing | Nova-3 | `speech_final=true` (endpointing=300, utterance_end_ms=1000) | 3.36s |
| `clip-a`, with keyterm | Nova-3 | `speech_final=true` | 3.35s |
| `clip-b`, natural endpointing | Nova-3 | `speech_final=true` | 3.37s |
| `clip-b`, `send_control(Finalize)` right after last chunk (push-to-talk) | Nova-3 | `Results` with `from_finalize=true` | **0.36s** |
| `clip-a`, no manual end signal | Flux | — | **no `EndOfTurn` within 3.3s wait** (`events_seen` only reached `StartOfTurn`/`Update`) |
| `clip-b`, no manual end signal | Flux | — | **no `EndOfTurn` within 3.3s wait** |

Nova-3's `speech_final` consistently arrived ~3.3-3.4s after the last audio chunk regardless of
keyterm — that ceiling is our own trailing-silence design in the spike script (we stop feeding
audio and Nova-3 needs `utterance_end_ms=1000` of true silence plus buffering delay), not a
Deepgram outlier. `send_finalize` (the push-to-talk path) cuts this to ~0.36s, matching the
architecture's plan to call it on `ptt_up`. Flux's default `eot_threshold`/`eot_timeout_ms` did
not fire in either test within the same window; the SDK's `ListenV2ControlMessage` has no
"ForceEndTurn" option to test the manual-trigger path (only `CloseStream`), so a faster Flux path
would need a raw-websocket control message — not pursued further since Nova-3 already wins on
fillers alone.

### 4. Keyterm effect on "Kubernetes"/"PostgreSQL"/"idempotent" (Q4)

- "Kubernetes" transcribed correctly in every run, with or without `keyterm`.
- "PostgreSQL" was consistently mis-transcribed in real-time streaming — *"the post GAR SQL
  data"* / *"Gur SQL database"* without keyterm; with `keyterm=["Kubernetes", "PostgreSQL",
  "idempotent"]`, an interim result briefly showed the correct *"...for the PostgreSQL"* before
  settling into a still-imperfect *"post greSQL"* split at finalization. Keyterm measurably helps
  but doesn't fully fix streaming recognition of this term in one pass.
- The **pre-recorded** (batch) transcription of the same clip, no keyterm needed, returned
  "PostgreSQL" correctly: *"...for the PostgreSQL database."* Batch transcription's extra
  processing pass handles domain terms better than the real-time path.
- "idempotent" was not in either clip's actual script (owner recorded closer paraphrases), so it
  wasn't directly exercised — not a blocker for the decision.

### 5. TTS voices, first-byte latency, speed (Q5)

All six curated voices from `voice-and-pronunciation.md` §7 exist and returned audio; none need
replacing.

| Voice | Exists | First-byte latency | Total bytes (one sentence) |
|---|---|---|---|
| `aura-2-thalia-en` | ✅ | 0.382s | 172,800 |
| `aura-2-asteria-en` | ✅ | 0.362s | 151,680 |
| `aura-2-andromeda-en` | ✅ | 0.384s | 165,120 |
| `aura-2-apollo-en` | ✅ | 0.360s | 176,640 |
| `aura-2-arcas-en` | ✅ | 0.381s | 161,280 |
| `aura-2-helena-en` | ✅ | 0.380s | 159,360 |

First-byte latency over `speak.v1` WS (linear16/24kHz) is consistently ~0.36-0.38s across voices —
comfortably fast for the "thinking → speaking" transition.

`speed` exists as a real parameter but **only on the REST `/v1/speak` endpoint**
(`client.speak.v1.audio.generate(..., request_options={"additional_query_parameters":
{"speed": ...}})` — no typed kwarg, see SDK gap #3). Confirmed working by output length scaling
inversely with speed for the same sentence: 0.7x → 32,688 bytes, 1.0x → 18,864 bytes, 1.5x →
13,248 bytes. **The `speak.v1` streaming WebSocket has no `speed` parameter at all** (not in the
typed signature, and Deepgram's own WS query-param docs never list one) — voice speed can only be
adjusted for TTS previews (REST), not for live conversation playback.

### 6. SDK v5 method names (Q6)

- REST TTS (MP3): `client.speak.v1.audio.generate(text=..., model=..., mip_opt_out=True)` →
  `typing.AsyncIterator[bytes]`; collect with `b"".join([c async for c in ...])`.
  (Docs' `response.stream.getvalue()` is stale for this version.)
- Pre-recorded transcription: `client.listen.v1.media.transcribe_file(request=<bytes>,
  model="nova-3", filler_words=True, mip_opt_out=True, ...)` → typed response with
  `.results.channels[0].alternatives[0]`. This one matches the docs.

### 7. `mip_opt_out` (Q7)

Set on every request across all five surfaces (`listen.v1` WS, `listen.v2` WS, `speak.v1` WS,
REST `/v1/speak`, pre-recorded `transcribe_file`) — zero errors or warnings in any run. Confirmed
this is a genuine typed kwarg on every one of those methods (not subject to the
`additional_query_parameters` gap, since it's a first-class parameter everywhere).

## Implications for Task 3.3

The production `app/voice/deepgram_stt.py` / `deepgram_tts.py` adapters must:
- Use `send_control(ListenV1ControlMessage(type="Finalize"))` on `ptt_up`, not `send_finalize()`.
- Use `send_control(ListenV1ControlMessage(type="CloseStream"))` to close, not
  `send_close_stream()`.
- Run `start_listening()` via `asyncio.create_task(...)`, never `await` it inline.
- Build the Nova-3 streaming connection with `filler_words=true` reaching the wire — since the
  typed `connect()` can't do this in SDK 5.3.4, either (a) open the WebSocket directly with
  `websockets.connect()` using a hand-built query string and reuse the SDK's typed event models
  for parsing, or (b) accept no server-side filler flag and rely entirely on the token-based
  `FILLER_TOKENS` fallback in `app/voice/fillers.py` (the interface already supports
  `provider_flag=None`). Recommend (a): pattern is already proven working in the spike
  (`spikes/deepgram/README.md` links the evidence); it keeps parity with the documented API
  instead of silently degrading transcript quality.
- Use `speak.v1.audio.generate()` for TTS previews only (not the primary voice-session TTS path,
  which stays on the WS per ADR-0009); collect its async-generator output into `bytes`.
- Re-run `pip index versions deepgram-sdk` / Context7 before starting 3.3 in case a 5.3.5+ patch
  closes any of these gaps; if so, prefer the typed API where it now works.

## Consequences

- Nova-3 ships as `DEEPGRAM_STT_MODEL` default (already `nova-3` in `app/core/config.py` — no
  change needed there).
- Filler-word detection needs a direct-websocket adapter in Task 3.3, not the SDK's `connect()` —
  slightly more code than planned, but isolated behind the existing `SpeechToText` Protocol so it
  doesn't leak into the relay or the rest of the app.
- No TTS speed control in live voice sessions (WS has none); a future speaking-speed *setting*
  (`product-spec.md` §9) would only be able to affect Deepgram TTS previews, not live playback —
  documented in `product-spec.md` F12/§9.
- Flux is not evaluated further; revisit only if Nova-3's real-time PostgreSQL-style term accuracy
  or its ~3.3s natural-endpointing latency becomes a problem in practice (`keyterm` already helps
  partially; push-to-talk's `Finalize` path sidesteps the latency question entirely at 0.36s).

## Alternatives considered

- **Flux (`listen.v2`)** — rejected: no filler-word feature, and `EndOfTurn` didn't fire within a
  generous 3.3s test window on either clip with default thresholds, so it couldn't even be
  compared on the latency tiebreaker.

## Related

- ADR-0003: Deepgram chosen for STT/TTS (this ADR resolves the "spike decides" note in ADR-0003
  and `voice-and-pronunciation.md` §2.5).
- ADR-0016: `mip_opt_out=true` on every request (confirmed working here).
