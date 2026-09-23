"""Deepgram Aura-2 TTS adapter (voice-and-pronunciation.md §2.5 step 5).

Unlike STT (see `deepgram_stt.py`), the SDK has no gap here (ADR-0013): `speak.v1.connect()` and
`speak.v1.audio.generate()` both accept everything this adapter needs as typed kwargs.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable

import httpx
from deepgram import AsyncDeepgramClient
from deepgram.core.api_error import ApiError
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import SpeakV1ControlMessage, SpeakV1TextMessage

from app.core.errors import SpeechUnavailableError
from app.voice.deepgram_common import deepgram_request_options

SAMPLE_RATE = 24000
ENCODING = "linear16"


class DeepgramTextToSpeech:
    """Implements `TextToSpeech`."""

    def __init__(
        self,
        api_key: str,
        *,
        client_factory: Callable[[], AsyncDeepgramClient] | None = None,
    ) -> None:
        self._api_key = api_key
        self._client_factory = client_factory or (lambda: AsyncDeepgramClient(api_key=api_key))

    def synthesize(self, *, voice: str, sentences: AsyncIterator[str]) -> AsyncIterator[bytes]:
        return self._synthesize(voice, sentences)

    async def _synthesize(self, voice: str, sentences: AsyncIterator[str]) -> AsyncIterator[bytes]:
        client = self._client_factory()
        connect_cm = client.speak.v1.connect(
            model=voice,
            encoding=ENCODING,
            sample_rate=SAMPLE_RATE,
            **deepgram_request_options(),
        )
        try:
            connection = await connect_cm.__aenter__()
        except (ApiError, OSError) as exc:
            raise SpeechUnavailableError() from exc

        try:
            queue: asyncio.Queue[bytes | None] = asyncio.Queue()

            def on_message(message: object) -> None:
                if isinstance(message, bytes | bytearray):
                    queue.put_nowait(bytes(message))
                elif getattr(message, "type", None) == "Flushed":
                    queue.put_nowait(None)

            connection.on(EventType.MESSAGE, on_message)
            listen_task = asyncio.create_task(connection.start_listening())

            sent_any = False
            async for sentence in sentences:
                if not sentence:
                    continue
                await connection.send_text(SpeakV1TextMessage(type="Speak", text=sentence))
                sent_any = True

            if sent_any:
                await connection.send_control(SpeakV1ControlMessage(type="Flush"))
                while True:
                    chunk = await queue.get()
                    if chunk is None:
                        break
                    yield chunk

            await connection.send_control(SpeakV1ControlMessage(type="Close"))
            listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listen_task
        finally:
            with contextlib.suppress(Exception):
                await connect_cm.__aexit__(None, None, None)

    async def synthesize_mp3(self, *, voice: str, text: str) -> bytes:
        client = self._client_factory()
        try:
            chunks = [
                chunk
                async for chunk in client.speak.v1.audio.generate(
                    text=text, model=voice, **deepgram_request_options()
                )
            ]
        except (ApiError, httpx.HTTPError, OSError) as exc:
            raise SpeechUnavailableError() from exc
        return b"".join(chunks)
