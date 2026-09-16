# Glossary

| Term | Meaning in this project |
|---|---|
| **Scenario** | A practice situation: persona + objective + opening line (built-in YAML or user-created "custom"). |
| **Persona** | The character the AI plays in a scenario (e.g. "Dana, product manager"). |
| **Session** (`practice_sessions`) | One practice conversation on a scenario, `text` or `voice` mode. Not a login session. |
| **Turn** | One message by the user or the persona. "User turns" are limited to 20 per session. |
| **Report** (`feedback_reports`) | The feedback generated after a session ends. |
| **Dimension** | A scored skill: clarity, conciseness, structure, audience_fit, tone, confidence, grammar_vocabulary, fluency, pronunciation. |
| **Rubric** | Versioned YAML describing how each LLM dimension is scored 1–5. |
| **Highlight** | A quote of the user's own words + issue + better version. |
| **Speaking stats / voice metrics** | Words per minute, filler words, long pauses, hard-to-catch words, fluency score — computed by code from Deepgram word timings. |
| **Filler word** | "um", "uh", etc. as tagged by Deepgram or listed in `FILLER_TOKENS`. |
| **Hard-to-catch word** | A word Deepgram transcribed with confidence < 0.60. Never called a pronunciation error. |
| **Pronunciation attempt** | One recording of one read-aloud sentence scored by Azure. |
| **Scripted assessment** | Pronunciation scoring where the expected text (reference text) is known. |
| **Phoneme** | A single speech sound (e.g. /k/ in "cache"). |
| **Coach note** | A remembered recurring weakness used to personalise future practice (max 8 active). |
| **Drill** | A short daily exercise (3 per day) targeting weak spots. |
| **Baseline / assessment** | The guided first measurement (text + voice + pronunciation) shown on progress charts. |
| **Streak** | Consecutive local days with at least one completed session, drill or pronunciation attempt. |
| **PTT** | Push-to-talk: user holds a button/Space while speaking. |
| **Hands-free** | Deepgram decides when the user finished speaking (end-of-turn). |
| **Barge-in** | Interrupting the AI while it speaks — not supported. |
| **Relay** | The backend component that connects the browser WebSocket, Deepgram and the LLM for voice sessions. |
| **Local user** | The single built-in user used before accounts exist (Q1). |
| **BYOK** | Bring your own key — users add their own LLM API key (Phase 9). |
| **Fake provider** | Deterministic in-process stand-in for Ollama/Deepgram/Azure used in tests and offline UI work. |
| **Spike** | A short, throwaway experiment to answer a technical question; findings become an ADR. |
| **Eval** | Offline quality test of LLM feedback against expected score ranges. |
| **Q1 / Q2** | Milestones (not calendar quarters): Q1 core product, Q2 accounts & go-live readiness. |
