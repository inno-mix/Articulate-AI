"""Feedback transcripts: filtering, indexing and the character budget (ai-layer.md §4.2)."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.domain.enums import MessageRole, MessageSource
from app.models import Message

OMITTED_MARKER = "[… earlier turns omitted …]"


@dataclass(frozen=True)
class TranscriptLine:
    index: int
    speaker: Literal["USER", "PERSONA"]
    text: str
    message_id: UUID


def build_transcript(
    messages: list[Message], *, max_chars: int = 6000
) -> tuple[list[TranscriptLine], bool]:
    """Non-system messages as `TranscriptLine`s. Truncates to `max_chars`, keeping the first two
    lines and as many of the latest lines as fit; the bool reports whether it truncated."""
    lines = [
        TranscriptLine(
            index=message.seq,
            speaker="USER" if message.role == MessageRole.USER else "PERSONA",
            text=message.content,
            message_id=message.id,
        )
        for message in messages
        if message.source != MessageSource.SYSTEM
    ]

    total_chars = sum(len(line.text) for line in lines)
    if total_chars <= max_chars or len(lines) <= 2:
        return lines, False

    kept = lines[:2]
    budget = max_chars - sum(len(line.text) for line in kept)
    tail: list[TranscriptLine] = []
    for line in reversed(lines[2:]):
        if len(line.text) > budget:
            break
        tail.insert(0, line)
        budget -= len(line.text)

    return [*kept, *tail], True


def format_transcript(lines: list[TranscriptLine], persona_name: str, truncated: bool) -> str:
    """`"[3] USER: …"` / `"[4] PERSONA (Dana): …"`, one per line."""
    formatted: list[str] = []
    for i, line in enumerate(lines):
        speaker = "USER" if line.speaker == "USER" else f"PERSONA ({persona_name})"
        formatted.append(f"[{line.index}] {speaker}: {line.text}")
        if truncated and i == 1:
            formatted.append(OMITTED_MARKER)
    return "\n".join(formatted)
