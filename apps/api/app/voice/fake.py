"""Deepgram-shaped fakes for tests and `make dev-fake` (voice-and-pronunciation.md §2.6).

Used when `STT_PROVIDER=fake` / `TTS_PROVIDER=fake`.
"""

import asyncio
from collections.abc import AsyncIterator

from app.schemas.json_types import SpeechWord
from app.voice.base import TranscriptEvent
from app.voice.fake_assets import FAKE_MP3

HANDS_FREE_CHUNK_THRESHOLD = 5
FAKE_TTS_CHUNK_SILENCE = b"\x00" * 2400  # 50ms of PCM16 24kHz silence

_DEFAULT_FINAL_WORDS: tuple[SpeechWord, ...] = (
    SpeechWord(word="hello", start=0.0, end=0.4, confidence=0.98, is_filler=False),
    SpeechWord(word="um", start=0.5, end=0.7, confidence=0.90, is_filler=True),
    SpeechWord(word="there", start=0.8, end=1.2, confidence=0.55, is_filler=False),
)


def _default_script() -> list[TranscriptEvent]:
    return [
        TranscriptEvent(kind="interim", text="hello"),
        TranscriptEvent(kind="final", text="hello um there", words=list(_DEFAULT_FINAL_WORDS)),
        TranscriptEvent(kind="end_of_turn", text=""),
    ]


class FakeSpeechToTextSession:
    """A single fake turn: replays `script` after `finalize()` or 5 audio chunks."""

    def __init__(self, script: list[TranscriptEvent], *, silent: bool = False) -> None:
        self._script = script
        self._silent = silent
        self.received_chunks: list[bytes] = []
        self._release = asyncio.Event()

    async def send_audio(self, chunk: bytes) -> None:
        self.received_chunks.append(chunk)
        if len(self.received_chunks) >= HANDS_FREE_CHUNK_THRESHOLD:
            self._release.set()

    async def finalize(self) -> None:
        self._release.set()

    async def close(self) -> None:
        self._release.set()

    def events(self) -> AsyncIterator[TranscriptEvent]:
        return self._events()

    async def _events(self) -> AsyncIterator[TranscriptEvent]:
        if self._silent:
            return
        await self._release.wait()
        for event in self._script:
            yield event


class FakeSpeechToText:
    """Implements `SpeechToText`. Each `open_session()` call gets its own session/state."""

    model = "fake"

    def __init__(
        self,
        script: list[TranscriptEvent] | None = None,
        *,
        open_delay_s: float = 0.0,
        silent: bool = False,
    ) -> None:
        self._script = script if script is not None else _default_script()
        self._open_delay_s = open_delay_s
        self._silent = silent
        self.sessions: list[FakeSpeechToTextSession] = []

    async def open_session(self, *, keyterms: list[str]) -> FakeSpeechToTextSession:
        if self._open_delay_s:
            await asyncio.sleep(self._open_delay_s)
        session = FakeSpeechToTextSession(self._script, silent=self._silent)
        self.sessions.append(session)
        return session


class FakeTextToSpeech:
    """Implements `TextToSpeech`. Yields silent PCM16 chunks and a tiny fixed MP3 preview."""

    def __init__(self) -> None:
        self.synthesized_sentences: list[str] = []

    def synthesize(self, *, voice: str, sentences: AsyncIterator[str]) -> AsyncIterator[bytes]:
        return self._synthesize(sentences)

    async def _synthesize(self, sentences: AsyncIterator[str]) -> AsyncIterator[bytes]:
        async for sentence in sentences:
            self.synthesized_sentences.append(sentence)
            yield FAKE_TTS_CHUNK_SILENCE

    async def synthesize_mp3(self, *, voice: str, text: str) -> bytes:
        return FAKE_MP3
