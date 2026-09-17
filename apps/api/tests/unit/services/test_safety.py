import pytest

from app.services.safety import SAFETY_MESSAGE, detect_crisis


@pytest.mark.parametrize(
    "text",
    [
        "I want to kill myself",
        "I've been thinking about suicide",
        "I want to end my life",
        "I KEEP wanting to HURT MYSELF",
        "sometimes I don't want to live anymore",
    ],
)
def test_detects_crisis_phrases(text: str) -> None:
    assert detect_crisis(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "kill the process",
        "this bug is killing me",
        "the build died again",
        "let's talk about the stand-up",
    ],
)
def test_does_not_flag_harmless_sentences(text: str) -> None:
    assert detect_crisis(text) is False


def test_safety_message_is_non_empty() -> None:
    assert SAFETY_MESSAGE
    assert "danger" in SAFETY_MESSAGE.lower() or "harm" in SAFETY_MESSAGE.lower()
