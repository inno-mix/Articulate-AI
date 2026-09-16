# 0003. Deepgram for speech-to-text and text-to-speech

- Status: Accepted
- Date: 2026-09-17

## Context
Voice practice needs low-latency streaming STT with word timings, confidence and filler words, and
streaming TTS. The owner chose Deepgram.

## Decision
- STT: Deepgram streaming via Python SDK v5 (`AsyncDeepgramClient`). Model is either Nova-3
  (`listen.v1`, `filler_words`, `endpointing`, `utterance_end_ms`) or Flux (`listen.v2`,
  model-integrated end-of-turn). The Phase 3 spike decides and records ADR-0013.
- TTS: Deepgram Aura-2 over the speak WebSocket (`speak.v1`), PCM16 24 kHz.
- Drills: Deepgram pre-recorded transcription.
- App-owned key (`DEEPGRAM_API_KEY`), server-side only.

## Consequences
- Voice features need internet and cost money per minute, even locally → `fake` providers for
  tests/UI work.
- Deepgram does not grade pronunciation → ADR-0004.

## Alternatives considered
- Browser Web Speech API — inconsistent across browsers, no word confidence/filler words.
- Local Whisper — too heavy for 8 GB alongside Ollama; no streaming TTS.

## Related
- ADR-0016: every Deepgram request opts out of the Model Improvement Program.
