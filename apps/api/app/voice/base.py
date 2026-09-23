"""Speech provider interfaces (voice-and-pronunciation.md §2.6)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from app.schemas.json_types import SpeechData, SpeechWord


@dataclass(frozen=True)
class TranscriptEvent:
    kind: Literal["interim", "final", "end_of_turn"]
    text: str
    words: list[SpeechWord] = field(default_factory=list)  # empty for interim/end_of_turn


@runtime_checkable
class SpeechToTextSession(Protocol):
    async def send_audio(self, chunk: bytes) -> None: ...
    async def finalize(self) -> None: ...
    def events(self) -> AsyncIterator[TranscriptEvent]: ...
    async def close(self) -> None: ...


@runtime_checkable
class SpeechToText(Protocol):
    model: str

    async def open_session(self, *, keyterms: list[str]) -> SpeechToTextSession: ...


@runtime_checkable
class TextToSpeech(Protocol):
    def synthesize(self, *, voice: str, sentences: AsyncIterator[str]) -> AsyncIterator[bytes]: ...

    async def synthesize_mp3(self, *, voice: str, text: str) -> bytes: ...


@runtime_checkable
class PrerecordedTranscriber(Protocol):
    async def transcribe_wav(self, wav: bytes, *, keyterms: list[str]) -> SpeechData: ...
