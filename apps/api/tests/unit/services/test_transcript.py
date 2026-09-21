from uuid import uuid4

from app.domain.enums import MessageRole, MessageSource
from app.models import Message
from app.services.transcript import TranscriptLine, build_transcript, format_transcript


def _message(seq: int, role: MessageRole, content: str, source: MessageSource) -> Message:
    return Message(id=uuid4(), seq=seq, role=role, content=content, source=source)


def test_excludes_system_messages() -> None:
    messages = [
        _message(0, MessageRole.ASSISTANT, "Hi there.", MessageSource.TEXT),
        _message(1, MessageRole.USER, "I want to end my life.", MessageSource.TEXT),
        _message(2, MessageRole.ASSISTANT, "I'm stepping out for a moment.", MessageSource.SYSTEM),
        _message(3, MessageRole.ASSISTANT, "Let's continue.", MessageSource.TEXT),
    ]

    lines, truncated = build_transcript(messages)

    assert [line.index for line in lines] == [0, 1, 3]
    assert truncated is False


def test_formats_speakers_and_indexes() -> None:
    message_id_a = uuid4()
    message_id_b = uuid4()
    lines = [
        TranscriptLine(index=3, speaker="USER", text="Hi Sam.", message_id=message_id_a),
        TranscriptLine(index=4, speaker="PERSONA", text="Hey, thanks!", message_id=message_id_b),
    ]

    result = format_transcript(lines, persona_name="Dana", truncated=False)

    assert result == "[3] USER: Hi Sam.\n[4] PERSONA (Dana): Hey, thanks!"


def test_truncates_keeping_first_two_and_latest() -> None:
    messages = [
        _message(0, MessageRole.ASSISTANT, "Opening line here.", MessageSource.TEXT),
        _message(1, MessageRole.USER, "First reply from the user.", MessageSource.TEXT),
        _message(2, MessageRole.ASSISTANT, "Middle turn that should drop.", MessageSource.TEXT),
        _message(3, MessageRole.USER, "Another middle turn to drop.", MessageSource.TEXT),
        _message(4, MessageRole.ASSISTANT, "Last assistant turn.", MessageSource.TEXT),
        _message(5, MessageRole.USER, "Final user turn.", MessageSource.TEXT),
    ]

    lines, truncated = build_transcript(messages, max_chars=80)

    assert truncated is True
    assert [line.index for line in lines[:2]] == [0, 1]
    assert 2 not in [line.index for line in lines]
    assert 3 not in [line.index for line in lines]
    assert lines[-1].index == 5


def test_no_truncation_marker_when_fits() -> None:
    messages = [
        _message(0, MessageRole.ASSISTANT, "Hi there.", MessageSource.TEXT),
        _message(1, MessageRole.USER, "Hi Sam, thanks for the PR.", MessageSource.TEXT),
    ]

    lines, truncated = build_transcript(messages)
    formatted = format_transcript(lines, persona_name="Sam", truncated=truncated)

    assert truncated is False
    assert "omitted" not in formatted
