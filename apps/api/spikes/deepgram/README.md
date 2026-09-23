# Deepgram spike (Task 3.1)

Throwaway scripts (agent-workflow.md rule A10) that answer the seven questions in
[`docs/tasks/q1-phase-03-voice.md`](../../../../docs/tasks/q1-phase-03-voice.md) Task 3.1. Findings
are recorded in [`docs/decisions/0013-deepgram-stt-model.md`](../../../../docs/decisions/0013-deepgram-stt-model.md).
Nothing here is imported by the app.

## Setup

- `DEEPGRAM_API_KEY` must be set in `apps/api/.env`.
- Two 16 kHz mono PCM16 WAV clips at `audio/clip-a.wav` and `audio/clip-b.wav` (git-ignored):
  - `clip-a.wav` — ~15s, a few natural "um"/"uh", mentions "Kubernetes" and "PostgreSQL".
  - `clip-b.wav` — ~10s, ends with a clear 2-second silence.

Record with QuickTime → New Audio Recording, then:

```bash
afconvert -f WAVE -d LEI16@16000 -c 1 in.m4a audio/clip-a.wav
```

## Run

```bash
cd "apps/api"
uv run python spikes/deepgram/stt_compare.py   # Q1-Q4, Q6 (pre-recorded), Q7 (STT side)
uv run python spikes/deepgram/tts_check.py     # Q5, Q6 (REST TTS), Q7 (TTS side)
```

Both scripts print a timestamped event log per run and a summary table. Every request sets
`mip_opt_out=True` (ADR-0016) — check the printed error lists for any rejection of that parameter.

## Files

- `ws_client.py` — shared `EventLog` (timestamped event recorder) and `stream_wav_pcm` (paces a WAV
  file out as ~100ms PCM16 chunks like a live mic).
- `stt_compare.py` — streams both clips to Nova-3 (`listen.v1`) and Flux (`listen.v2`), compares
  filler words, word timings/confidence, keyterm effect, and end-of-turn latency (natural
  endpointing vs. `send_finalize()`).
- `tts_check.py` — opens a `speak.v1` WebSocket per curated voice id, measures time-to-first-byte;
  probes the REST MP3 endpoint and the `speed` parameter.
