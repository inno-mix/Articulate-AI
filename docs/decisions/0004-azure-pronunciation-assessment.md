# 0004. Azure AI Speech for pronunciation assessment

- Status: Accepted
- Date: 2026-09-17

## Context
Target users are mostly non-native speakers; pronunciation feedback matters. Deepgram confidence is
not a reliable mispronunciation signal (recognisers often "auto-correct" to the intended word).
Researched options (2026-09): Azure (~$1/audio hour reported, 5 free hours/month on F0, phoneme
level, N-best phonemes via SDK), SpeechSuper ($0.006/sentence, $20/month minimum), SpeechAce
($40–125/month plans), ELSA (enterprise), open-source models (too heavy/research-grade).

## Decision
- Azure AI Speech pronunciation assessment, **scripted** (read-aloud) mode, `en-US`,
  `HundredMark`, `Phoneme` granularity, miscue on, **no prosody** (paid add-on).
- A separate Pronunciation Practice feature; conversations stay Deepgram-only.
- Behind the `PronunciationAssessor` Protocol so the provider can be swapped.
- REST short-audio API by default; Speech SDK only if the Phase 4 spike shows it's needed for
  "heard as" phonemes (records ADR-0014).
- F0 limit of 1 concurrent request → serialise calls with a semaphore.

## Consequences
- Second cloud account/key; free tier is dev-only; production needs the paid tier.
- Unscripted pronunciation scoring of free conversation is out of scope.

## Alternatives considered
- SpeechAce Pro — good exam-style scores; more expensive per attempt; kept as fallback.
- SpeechSuper — cheaper than SpeechAce, monthly minimum.
- Deepgram confidence only — misleading; used only as a soft "hard to catch" hint.
