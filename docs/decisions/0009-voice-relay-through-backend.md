# 0009. Relay voice audio through the backend

- Status: Accepted
- Date: 2026-09-17

## Context
Deepgram supports 30-second temporary tokens so browsers could connect directly, but the backend
needs trustworthy transcripts/timings and must drive the LLM and TTS.

## Decision
One browser↔API WebSocket per voice session; the API relays audio to Deepgram STT, runs the LLM,
streams Deepgram TTS audio back. Protocol in `docs/architecture/voice-and-pronunciation.md` §2.

## Consequences
- Keys never leave the server; transcripts can't be tampered with by the client.
- One extra network hop (negligible locally); the API process holds long-lived sockets.

## Alternatives considered
- Browser → Deepgram direct with temporary tokens — client-supplied transcripts, more client logic.
- Deepgram Voice Agent API — less control over prompts, storage and metrics.
