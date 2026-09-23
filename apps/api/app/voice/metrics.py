"""Speaking stats computed from a voice session (voice-and-pronunciation.md §3).

`fluency_score` is an initial heuristic — tune the constants below against real recordings.
"""

from app.schemas.json_types import SpeechData, VoiceMetrics

LONG_PAUSE_S = 2.0
LOW_CONFIDENCE = 0.60
PACE_OK = (110, 170)
PACE_WIDE = (90, 190)

MIN_WORDS_FOR_PACE = 3
MAX_HARD_TO_CATCH = 10
MAX_FILLER_EXAMPLES = 5


def compute_voice_metrics(turns: list[SpeechData]) -> VoiceMetrics:
    speaking_seconds = sum(turn.duration_s for turn in turns)

    words = 0
    filler_count = 0
    filler_examples: list[str] = []
    hard_to_catch_words: list[str] = []
    long_pause_count = 0
    pace_words = 0
    pace_seconds = 0.0
    total_word_count = 0

    for turn in turns:
        non_filler_in_turn = 0
        total_word_count += len(turn.words)

        for word in turn.words:
            if word.is_filler:
                filler_count += 1
                lowered = word.word.lower()
                if lowered not in filler_examples and len(filler_examples) < MAX_FILLER_EXAMPLES:
                    filler_examples.append(lowered)
            else:
                words += 1
                non_filler_in_turn += 1
                if word.confidence < LOW_CONFIDENCE:
                    lowered = word.word.lower()
                    if (
                        lowered not in hard_to_catch_words
                        and len(hard_to_catch_words) < MAX_HARD_TO_CATCH
                    ):
                        hard_to_catch_words.append(lowered)

        if non_filler_in_turn >= MIN_WORDS_FOR_PACE:
            pace_words += non_filler_in_turn
            pace_seconds += turn.duration_s

        for prev, nxt in zip(turn.words, turn.words[1:], strict=False):
            if nxt.start - prev.end > LONG_PAUSE_S:
                long_pause_count += 1

    pace_measured = pace_seconds > 0
    wpm = (pace_words / (pace_seconds / 60)) if pace_measured else 0.0
    filler_rate_per_100 = (filler_count / max(words, 1)) * 100
    long_pauses_per_min = (
        (long_pause_count / (speaking_seconds / 60)) if speaking_seconds > 0 else 0.0
    )

    if total_word_count == 0:
        # No speech at all can't be fluent, regardless of what the additive formula would give.
        fluency_score = 1
    else:
        fluency_score = 5
        if pace_measured:
            if wpm < PACE_WIDE[0] or wpm > PACE_WIDE[1]:
                fluency_score -= 2
            elif wpm < PACE_OK[0] or wpm > PACE_OK[1]:
                fluency_score -= 1
        if filler_rate_per_100 > 6:
            fluency_score -= 2
        elif filler_rate_per_100 > 3:
            fluency_score -= 1
        if long_pauses_per_min > 2:
            fluency_score -= 1
        fluency_score = max(1, min(5, fluency_score))

    return VoiceMetrics(
        speaking_seconds=speaking_seconds,
        words=words,
        wpm=round(wpm, 1),
        pace_measured=pace_measured,
        filler_count=filler_count,
        filler_rate_per_100=round(filler_rate_per_100, 1),
        filler_examples=filler_examples,
        long_pause_count=long_pause_count,
        long_pauses_per_min=round(long_pauses_per_min, 2),
        hard_to_catch_words=hard_to_catch_words,
        fluency_score=fluency_score,
    )


def fluency_reason(m: VoiceMetrics) -> str:
    """One-line breakdown of the fluency score, e.g. for a report tooltip."""
    if m.pace_measured:
        pace_part = f"Pace {m.wpm:.0f} wpm (aim {PACE_OK[0]}-{PACE_OK[1]})"
    else:
        pace_part = "Pace not measured (too little speech in any turn)"
    return (
        f"{pace_part} · {m.filler_rate_per_100:.1f} fillers per 100 words · "
        f"{m.long_pauses_per_min:.1f} long pauses per minute"
    )


def speaking_summary(m: VoiceMetrics) -> str:
    """One line describing the turn's speaking stats, for the feedback prompt."""
    if m.speaking_seconds == 0:
        return "No speech was recorded."
    minutes = m.speaking_seconds / 60
    if m.pace_measured:
        pace_clause = f"{m.wpm:.0f} words per minute"
    else:
        pace_clause = "pace not measurable (turns too short)"
    pause_word = "pause" if m.long_pause_count == 1 else "pauses"
    return (
        f"Spoke for {minutes:.1f} minutes at {pace_clause}, with {m.filler_count} filler words "
        f"({m.filler_rate_per_100:.1f} per 100 words) and {m.long_pause_count} long {pause_word}. "
        f"Fluency score: {m.fluency_score}/5."
    )
