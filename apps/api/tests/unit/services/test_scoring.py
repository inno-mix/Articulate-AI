from uuid import uuid4

import pytest

from app.domain.enums import MessageRole, MessageSource
from app.llm.outputs import GrammarFixOut, HighlightOut
from app.models import Message
from app.schemas.json_types import SpeechData, SpeechWord
from app.services.scoring import (
    filter_grammar_fixes,
    filter_highlights,
    find_quote_message,
    normalise_text,
    overall_score,
    to_score_100,
)


def _user_message(content: str) -> Message:
    return Message(
        id=uuid4(), seq=1, role=MessageRole.USER, content=content, source=MessageSource.TEXT
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hi Sam, thanks for the PR.", "hi sam, thanks for the pr"),
        ("SO BASICALLY", "so basically"),
        ("  extra   spaces  ", "extra spaces"),
        ("She said " + chr(0x2018) + "hello" + chr(0x2019) + " to me.", "she said 'hello' to me"),
        ("  --so basically--  ", "so basically"),
    ],
)
def test_normalise_text(raw: str, expected: str) -> None:
    assert normalise_text(raw) == expected


def test_find_quote_message_found() -> None:
    messages = [_user_message("Hi Sam, thanks for the PR.")]

    found = find_quote_message("thanks for the PR", messages)

    assert found is messages[0]


def test_find_quote_message_not_found() -> None:
    messages = [_user_message("Hi Sam, thanks for the PR.")]

    assert find_quote_message("completely unrelated text", messages) is None


def test_find_quote_message_too_short() -> None:
    messages = [_user_message("Hi Sam, thanks for the PR.")]

    assert find_quote_message("hi", messages) is None


def test_filter_highlights_sets_message_id() -> None:
    message = _user_message("Hi Sam, thanks for the PR.")
    items = [
        HighlightOut(quote="thanks for the PR", issue="vague", better_version="be specific"),
        HighlightOut(quote="never said this", issue="invented", better_version="n/a"),
    ]

    filtered = filter_highlights(items, [message])

    assert len(filtered) == 1
    assert filtered[0].message_id == message.id
    assert filtered[0].quote == "thanks for the PR"


def test_filter_grammar_fixes_drops_unmatched_original() -> None:
    message = _user_message("I am agree with this change.")
    items = [
        GrammarFixOut(original="I am agree", corrected="I agree", explanation="verb form"),
        GrammarFixOut(original="never said this", corrected="x", explanation="y"),
    ]

    filtered = filter_grammar_fixes(items, [message])

    assert len(filtered) == 1
    assert filtered[0].original == "I am agree"


def test_filter_grammar_fixes_drops_fix_with_low_confidence_word() -> None:
    message = _user_message("I am agree with this change.")
    speech = SpeechData(
        words=[
            SpeechWord(word="i", start=0.0, end=0.1, confidence=0.95, is_filler=False),
            SpeechWord(word="am", start=0.1, end=0.2, confidence=0.90, is_filler=False),
            SpeechWord(word="agree", start=0.2, end=0.3, confidence=0.40, is_filler=False),
            SpeechWord(word="with", start=0.3, end=0.4, confidence=0.95, is_filler=False),
        ],
        duration_s=0.4,
        stt_model="nova-3",
    )
    items = [GrammarFixOut(original="I am agree", corrected="I agree", explanation="verb form")]

    filtered = filter_grammar_fixes(items, [message], speech_by_message={message.id: speech})

    assert filtered == []


def test_filter_grammar_fixes_keeps_fix_with_high_confidence_words() -> None:
    message = _user_message("I am agree with this change.")
    speech = SpeechData(
        words=[
            SpeechWord(word="i", start=0.0, end=0.1, confidence=0.95, is_filler=False),
            SpeechWord(word="am", start=0.1, end=0.2, confidence=0.90, is_filler=False),
            SpeechWord(word="agree", start=0.2, end=0.3, confidence=0.85, is_filler=False),
        ],
        duration_s=0.3,
        stt_model="nova-3",
    )
    items = [GrammarFixOut(original="I am agree", corrected="I agree", explanation="verb form")]

    filtered = filter_grammar_fixes(items, [message], speech_by_message={message.id: speech})

    assert len(filtered) == 1
    assert filtered[0].original == "I am agree"


def test_filter_grammar_fixes_without_speech_data_is_unaffected() -> None:
    message = _user_message("I am agree with this change.")
    items = [GrammarFixOut(original="I am agree", corrected="I agree", explanation="verb form")]

    filtered = filter_grammar_fixes(items, [message], speech_by_message={})

    assert len(filtered) == 1


@pytest.mark.parametrize(("score_5", "expected"), [(1, 0), (2, 25), (3, 50), (4, 75), (5, 100)])
def test_to_score_100(score_5: int, expected: int) -> None:
    assert to_score_100(score_5) == expected


def test_overall_score_averages() -> None:
    assert overall_score([3, 4, 5]) == 75


def test_overall_score_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        overall_score([])
