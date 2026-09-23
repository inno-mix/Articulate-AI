from app.schemas.json_types import SpeechData, SpeechWord
from app.voice.metrics import compute_voice_metrics, fluency_reason, speaking_summary


def _word(
    word: str,
    start: float,
    end: float,
    *,
    confidence: float = 0.9,
    is_filler: bool = False,
) -> SpeechWord:
    return SpeechWord(word=word, start=start, end=end, confidence=confidence, is_filler=is_filler)


def _turn(words: list[SpeechWord], *, duration_s: float, stt_model: str = "nova-3") -> SpeechData:
    return SpeechData(words=words, duration_s=duration_s, stt_model=stt_model)


def _plain_words(
    n: int, *, start: float = 0.0, step: float = 0.3, prefix: str = "word"
) -> list[SpeechWord]:
    words = []
    t = start
    for i in range(n):
        words.append(_word(f"{prefix}{i}", t, t + 0.2))
        t += step
    return words


def test_no_turns_gives_all_zero_counts_and_fluency_one() -> None:
    metrics = compute_voice_metrics([])
    assert metrics.speaking_seconds == 0
    assert metrics.words == 0
    assert metrics.wpm == 0
    assert metrics.pace_measured is False
    assert metrics.filler_count == 0
    assert metrics.filler_rate_per_100 == 0
    assert metrics.filler_examples == []
    assert metrics.long_pause_count == 0
    assert metrics.long_pauses_per_min == 0
    assert metrics.hard_to_catch_words == []
    assert metrics.fluency_score == 1


def test_normal_pace_140_wpm_no_fillers_scores_5() -> None:
    # 14 non-filler words over a 6s (0.1 min) turn => 140 wpm.
    turn = _turn(_plain_words(14), duration_s=6.0)
    metrics = compute_voice_metrics([turn])
    assert metrics.pace_measured is True
    assert metrics.wpm == 140.0
    assert metrics.fluency_score == 5


def test_pace_100_wpm_scores_4() -> None:
    # 10 non-filler words over a 6s (0.1 min) turn => 100 wpm (outside PACE_OK, inside PACE_WIDE).
    turn = _turn(_plain_words(10), duration_s=6.0)
    metrics = compute_voice_metrics([turn])
    assert metrics.wpm == 100.0
    assert metrics.fluency_score == 4


def test_pace_80_wpm_scores_3() -> None:
    # 8 non-filler words over a 6s (0.1 min) turn => 80 wpm (outside PACE_WIDE).
    turn = _turn(_plain_words(8), duration_s=6.0)
    metrics = compute_voice_metrics([turn])
    assert metrics.wpm == 80.0
    assert metrics.fluency_score == 3


def test_filler_rate_4_per_100_scores_minus_1() -> None:
    # 100 non-filler words + 4 fillers => filler_rate_per_100 = 4. Pace held at 140 wpm (neutral).
    words = _plain_words(100) + [_word("um", 50.0, 50.2, is_filler=True) for _ in range(4)]
    turn = _turn(words, duration_s=100 / 140 * 60)
    metrics = compute_voice_metrics([turn])
    assert metrics.filler_rate_per_100 == 4.0
    assert metrics.fluency_score == 4


def test_filler_rate_7_per_100_scores_minus_2() -> None:
    words = _plain_words(100) + [_word("uh", 50.0, 50.2, is_filler=True) for _ in range(7)]
    turn = _turn(words, duration_s=100 / 140 * 60)
    metrics = compute_voice_metrics([turn])
    assert metrics.filler_rate_per_100 == 7.0
    assert metrics.fluency_score == 3


def test_long_pauses_3_per_minute_scores_minus_1() -> None:
    # One turn, 60s long, with exactly 3 gaps > LONG_PAUSE_S between words => 3 long pauses/min.
    words = []
    t = 0.0
    last_end = 0.0
    for i in range(4):
        words.append(_word(f"word{i}", t, t + 0.2))
        last_end = t + 0.2
        t += 2.5  # gap of 2.3s > LONG_PAUSE_S(2.0) after each of the first 3 words
    # pad with plenty of neutral-pace words (no further gaps) so wpm stays in PACE_OK
    words += _plain_words(140, start=last_end + 0.1, step=0.3, prefix="pad")
    turn = _turn(words, duration_s=60.0)
    metrics = compute_voice_metrics([turn])
    assert metrics.long_pause_count == 3
    assert metrics.long_pauses_per_min == 3.0
    assert metrics.fluency_score == 4


def test_combined_penalties_clamp_at_1() -> None:
    # Bad pace (-2), bad filler rate (-2) and 3 long-pauses/min (-1) at once => floor at 1, not -1.
    words: list[SpeechWord] = []
    t = 0.0
    for i in range(32):
        words.append(_word(f"w{i}", t, t + 0.1))
        t += 0.15
    for _ in range(10):
        words.append(_word("um", t, t + 0.1, is_filler=True))
        t += 0.15
    for _ in range(3):
        t += 2.5  # long pause (> LONG_PAUSE_S)
        words.append(_word("gap", t, t + 0.1))
        t += 0.15
    turn = _turn(words, duration_s=60.0)  # 35 non-filler words over 1 min => 35 wpm
    metrics = compute_voice_metrics([turn])
    assert metrics.long_pauses_per_min == 3.0
    assert metrics.filler_rate_per_100 > 6
    assert metrics.wpm < 90
    assert metrics.fluency_score == 1


def test_turns_with_fewer_than_3_non_filler_words_are_excluded_from_pace() -> None:
    short_turn = _turn(_plain_words(2), duration_s=1.0)  # only 2 non-filler words
    long_turn = _turn(_plain_words(14), duration_s=6.0)  # 14 words / 6s => 140 wpm
    metrics = compute_voice_metrics([short_turn, long_turn])
    assert metrics.pace_measured is True
    assert metrics.wpm == 140.0  # the short turn must not dilute/skew the pace calculation
    assert metrics.words == 16  # but its words still count toward the overall word total


def test_only_short_turns_leave_pace_unmeasured_with_no_penalty() -> None:
    turn_a = _turn(_plain_words(1), duration_s=1.0)
    turn_b = _turn(_plain_words(2), duration_s=1.0)
    metrics = compute_voice_metrics([turn_a, turn_b])
    assert metrics.pace_measured is False
    assert metrics.wpm == 0
    assert metrics.fluency_score == 5  # no pace penalty applied


def test_hard_to_catch_words_are_distinct_lowercased_capped_at_10_and_exclude_fillers() -> None:
    words = [_word("Kubernetes", 0.0, 0.3, confidence=0.4)]
    words.append(_word("kubernetes", 0.4, 0.7, confidence=0.3))  # duplicate, different case
    words.append(_word("clear", 0.8, 1.0, confidence=0.95))  # high confidence, excluded
    # low-confidence filler word, excluded
    words.append(_word("um", 1.1, 1.3, confidence=0.1, is_filler=True))
    for i in range(12):
        words.append(_word(f"mumble{i}", 2.0 + i * 0.3, 2.2 + i * 0.3, confidence=0.2))
    turn = _turn(words, duration_s=10.0)
    metrics = compute_voice_metrics([turn])
    assert len(metrics.hard_to_catch_words) <= 10
    assert "kubernetes" in metrics.hard_to_catch_words
    assert metrics.hard_to_catch_words.count("kubernetes") == 1
    assert "clear" not in metrics.hard_to_catch_words
    assert "um" not in metrics.hard_to_catch_words


def test_filler_examples_are_distinct_and_capped_at_5() -> None:
    fillers = ["um", "Um", "uh", "UH", "erm", "er", "ah", "hmm"]
    words = [_word(w, i * 0.3, i * 0.3 + 0.2, is_filler=True) for i, w in enumerate(fillers)]
    turn = _turn(words, duration_s=10.0)
    metrics = compute_voice_metrics([turn])
    assert len(metrics.filler_examples) <= 5
    assert len(metrics.filler_examples) == len(set(metrics.filler_examples))


def test_fluency_reason_mentions_pace_filler_rate_and_pauses() -> None:
    turn = _turn(_plain_words(14), duration_s=6.0)
    metrics = compute_voice_metrics([turn])
    reason = fluency_reason(metrics)
    assert "140" in reason
    assert "wpm" in reason
    assert "filler" in reason.lower()
    assert "pause" in reason.lower()


def test_fluency_reason_handles_unmeasured_pace() -> None:
    turn = _turn(_plain_words(1), duration_s=1.0)
    metrics = compute_voice_metrics([turn])
    reason = fluency_reason(metrics)
    assert reason  # never empty
    assert "wpm" not in reason or "not measured" in reason.lower()


def test_speaking_summary_is_nonempty_and_mentions_fluency_score() -> None:
    turn = _turn(_plain_words(14), duration_s=6.0)
    metrics = compute_voice_metrics([turn])
    summary = speaking_summary(metrics)
    assert summary
    assert str(metrics.fluency_score) in summary


def test_speaking_summary_handles_no_speech() -> None:
    metrics = compute_voice_metrics([])
    summary = speaking_summary(metrics)
    assert summary
    assert isinstance(summary, str)
