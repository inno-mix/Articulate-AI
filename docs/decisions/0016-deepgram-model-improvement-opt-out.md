# 0016. Opt out of Deepgram's Model Improvement Program

- Status: Accepted
- Date: 2026-09-17
- Deciders: Owner (Micko Matamorosa)

## Context
Practice audio and transcripts often describe real workplace situations. Deepgram's API has a
`mip_opt_out` parameter that "opts out requests from the Deepgram Model Improvement Program"; it
**defaults to `false`**, i.e. requests are part of the program unless the caller opts out. Deepgram's
changelog (2026-03-05) states that Pay-as-you-Go and Growth customers can opt in or out without
affecting their pricing. The parameter is documented for pre-recorded and streaming speech-to-text and
for text-to-speech (REST and WebSocket).

## Decision
Every Deepgram request the app makes sets `mip_opt_out=true`:
streaming STT (Nova-3 `listen.v1` and Flux `listen.v2`), pre-recorded STT (drills), TTS WebSocket
(`speak.v1`) and TTS REST (previews). Adapters take these options from one shared helper so the flag
can't be forgotten, and unit tests assert it on every request type. Spikes and live tests set it too.

## Consequences
- Users' audio isn't used to improve Deepgram's models; the privacy page says so.
- If Deepgram's pricing terms change, revisit this ADR (check the plan in use before going live).
- The Phase 3 spike confirms the SDK v5 parameter name and that each endpoint accepts it.

## Alternatives considered
- Keep the default (opted in) — cheaper only on plans where opting out costs more; unnecessary privacy
  risk for sensitive content.
