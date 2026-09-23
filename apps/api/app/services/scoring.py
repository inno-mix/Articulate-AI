"""Deterministic scoring: quote checks and score maths (ai-layer.md §7, code not LLM)."""

import re
from string import punctuation
from uuid import UUID

from app.llm.outputs import GrammarFixOut, HighlightOut
from app.models import Message
from app.schemas.json_types import GrammarFix, Highlight, SpeechData
from app.voice.metrics import LOW_CONFIDENCE

_MIN_QUOTE_CHARS = 3
# Curly quotes by codepoint (left/right single U+2018/2019, left/right double U+201C/201D) to
# straight equivalents — avoids embedding the literal glyphs in source (ruff RUF001).
_QUOTE_TRANSLATION = str.maketrans({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'})


def normalise_text(s: str) -> str:
    """Lower-case, straighten curly quotes, collapse whitespace, strip edge punctuation."""
    text = s.translate(_QUOTE_TRANSLATION).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(punctuation + " ")


def find_quote_message(quote: str, user_messages: list[Message]) -> Message | None:
    """The first user message containing `quote` (normalised). `None` if too short or absent."""
    normalised_quote = normalise_text(quote)
    if len(normalised_quote) < _MIN_QUOTE_CHARS:
        return None
    for message in user_messages:
        if normalised_quote in normalise_text(message.content):
            return message
    return None


def filter_highlights(items: list[HighlightOut], user_messages: list[Message]) -> list[Highlight]:
    """Keep only highlights whose quote is actually in a user message."""
    filtered: list[Highlight] = []
    for item in items:
        message = find_quote_message(item.quote, user_messages)
        if message is None:
            continue
        filtered.append(
            Highlight(
                message_id=message.id,
                quote=item.quote,
                issue=item.issue,
                better_version=item.better_version,
            )
        )
    return filtered


def _quote_has_low_confidence_word(quote: str, speech: SpeechData) -> bool:
    """Whether any word in `quote` matches a word the STT was < `LOW_CONFIDENCE` sure of."""
    quote_words = {normalise_text(word) for word in quote.split()} - {""}
    return any(
        word.confidence < LOW_CONFIDENCE and normalise_text(word.word) in quote_words
        for word in speech.words
    )


def filter_grammar_fixes(
    items: list[GrammarFixOut],
    user_messages: list[Message],
    *,
    speech_by_message: dict[UUID, SpeechData] | None = None,
) -> list[GrammarFix]:
    """Keep only grammar fixes whose `original` is actually in a user message.

    For voice turns, also drops a fix whose `original` uses a word the STT was unsure about
    (`speech_by_message`, keyed by message id) — a "grammar fix" built on a possible
    mis-transcription isn't trustworthy feedback.
    """
    speech_by_message = speech_by_message or {}
    filtered: list[GrammarFix] = []
    for item in items:
        message = find_quote_message(item.original, user_messages)
        if message is None:
            continue
        speech = speech_by_message.get(message.id)
        if speech is not None and _quote_has_low_confidence_word(item.original, speech):
            continue
        filtered.append(
            GrammarFix(
                original=item.original, corrected=item.corrected, explanation=item.explanation
            )
        )
    return filtered


def to_score_100(score_5: int) -> int:
    """1..5 → 0/25/50/75/100 (data-model.md conventions)."""
    return (score_5 - 1) * 25


def overall_score(scores_5: list[int]) -> int:
    """Rounded mean of the 0-100 scores. Raises `ValueError` if `scores_5` is empty."""
    if not scores_5:
        raise ValueError("scores_5 must not be empty")
    scores_100 = [to_score_100(score) for score in scores_5]
    return round(sum(scores_100) / len(scores_100))
