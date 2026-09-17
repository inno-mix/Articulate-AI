from app.domain.enums import MessageRole, MessageSource
from app.llm.base import ChatTurn
from app.models import Message
from app.services.chat import build_history


def _message(seq: int, role: MessageRole, content: str, source: MessageSource) -> Message:
    return Message(seq=seq, role=role, content=content, source=source)


def test_build_history_keeps_opening_line() -> None:
    messages = [_message(0, MessageRole.ASSISTANT, "Hi there.", MessageSource.TEXT)]

    history = build_history(messages)

    assert history == [ChatTurn(role="assistant", content="Hi there.")]


def test_build_history_merges_consecutive_user_messages() -> None:
    messages = [
        _message(0, MessageRole.ASSISTANT, "Hi there.", MessageSource.TEXT),
        _message(1, MessageRole.USER, "First part.", MessageSource.TEXT),
        _message(2, MessageRole.USER, "Second part.", MessageSource.TEXT),
        _message(3, MessageRole.ASSISTANT, "Got it.", MessageSource.TEXT),
    ]

    history = build_history(messages)

    assert history == [
        ChatTurn(role="assistant", content="Hi there."),
        ChatTurn(role="user", content="First part.\n\nSecond part."),
        ChatTurn(role="assistant", content="Got it."),
    ]


def test_build_history_excludes_system_messages() -> None:
    messages = [
        _message(0, MessageRole.ASSISTANT, "Hi there.", MessageSource.TEXT),
        _message(1, MessageRole.USER, "I want to end my life.", MessageSource.TEXT),
        _message(2, MessageRole.ASSISTANT, "I'm stepping out for a moment.", MessageSource.SYSTEM),
    ]

    history = build_history(messages)

    assert history == [
        ChatTurn(role="assistant", content="Hi there."),
        ChatTurn(role="user", content="I want to end my life."),
    ]
