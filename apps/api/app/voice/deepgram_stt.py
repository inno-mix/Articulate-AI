"""Deepgram Nova-3 streaming STT adapter (ADR-0013).

Opens a raw `websockets` connection instead of using `AsyncDeepgramClient.listen.v1.connect()`:
that typed method has no `filler_words` kwarg and silently drops
`request_options["additional_query_parameters"]` for WebSocket connects in deepgram-sdk 5.3.4
(confirmed by reading the SDK source during the Task 3.1 spike), which would make the adapter
strip every "um"/"uh" server-side. See ADR-0013's "Implications for Task 3.3".
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlencode

from websockets.exceptions import WebSocketException

from app.core.errors import SpeechUnavailableError
from app.schemas.json_types import SpeechWord
from app.voice.base import TranscriptEvent
from app.voice.deepgram_common import deepgram_request_options
from app.voice.fillers import is_filler

LISTEN_URL = "wss://api.deepgram.com/v1/listen"
MAX_KEYTERMS = 20


@runtime_checkable
class WebsocketLike(Protocol):
    async def send(self, message: bytes | str) -> None: ...
    def __aiter__(self) -> AsyncIterator[bytes | str]: ...


WebsocketConnectionContext = AbstractAsyncContextManager[WebsocketLike]


WebsocketConnector = Callable[[str, dict[str, str]], WebsocketConnectionContext]


def _default_connector(url: str, headers: dict[str, str]) -> WebsocketConnectionContext:
    import websockets

    return websockets.connect(url, additional_headers=headers)


def _build_listen_url(model: str, keyterms: list[str]) -> str:
    params: list[tuple[str, str]] = [
        ("model", model),
        ("language", "en-US"),
        ("encoding", "linear16"),
        ("sample_rate", "16000"),
        ("channels", "1"),
        ("interim_results", "true"),
        ("punctuate", "true"),
        ("smart_format", "true"),
        ("filler_words", "true"),
        ("endpointing", "300"),
        ("utterance_end_ms", "1000"),
        ("vad_events", "true"),
        ("mip_opt_out", "true" if deepgram_request_options()["mip_opt_out"] else "false"),
    ]
    for term in keyterms[:MAX_KEYTERMS]:
        params.append(("keyterm", term))
    return f"{LISTEN_URL}?{urlencode(params)}"


def _speech_word(raw: dict[str, Any]) -> SpeechWord:
    word = raw["word"]
    return SpeechWord(
        word=word,
        start=raw["start"],
        end=raw["end"],
        confidence=raw["confidence"],
        is_filler=is_filler(word),
    )


def _parse_message(raw: bytes | str) -> list[TranscriptEvent]:
    """Parse one Deepgram `listen.v1` JSON message into zero, one or two transcript events.

    A turn's closing message often carries the final transcript *and* `speech_final=true` at
    once, so both a `final` and an `end_of_turn` event can come out of a single message.
    """
    message = json.loads(raw)
    if message.get("type") != "Results":
        return []
    alternatives = message.get("channel", {}).get("alternatives", [])
    if not alternatives:
        return []
    alt = alternatives[0]
    transcript = alt.get("transcript", "")
    is_final = bool(message.get("is_final"))
    speech_final = bool(message.get("speech_final"))

    events: list[TranscriptEvent] = []
    if transcript:
        if is_final:
            words = [_speech_word(w) for w in alt.get("words", [])]
            events.append(TranscriptEvent(kind="final", text=transcript, words=words))
        else:
            events.append(TranscriptEvent(kind="interim", text=transcript))
    if speech_final:
        events.append(TranscriptEvent(kind="end_of_turn", text=""))
    return events


class DeepgramSpeechToTextSession:
    """Implements `SpeechToTextSession` over a raw Deepgram `listen.v1` websocket."""

    def __init__(self, ws: WebsocketLike, cm: WebsocketConnectionContext) -> None:
        self._ws = ws
        self._cm = cm
        self._queue: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._closed = False
        self._receiver_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, chunk: bytes) -> None:
        try:
            await self._ws.send(chunk)
        except (WebSocketException, OSError) as exc:
            raise SpeechUnavailableError() from exc

    async def finalize(self) -> None:
        try:
            await self._ws.send(json.dumps({"type": "Finalize"}))
        except (WebSocketException, OSError) as exc:
            raise SpeechUnavailableError() from exc

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(WebSocketException, OSError):
            await self._ws.send(json.dumps({"type": "CloseStream"}))
        self._receiver_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, WebSocketException, OSError):
            await self._receiver_task
        with contextlib.suppress(WebSocketException, OSError):
            await self._cm.__aexit__(None, None, None)

    def events(self) -> AsyncIterator[TranscriptEvent]:
        return self._iter_events()

    async def _iter_events(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event

    async def _receive_loop(self) -> None:
        try:
            async for raw in self._ws:
                for event in _parse_message(raw):
                    await self._queue.put(event)
        except (WebSocketException, OSError):
            pass
        finally:
            await self._queue.put(None)


class DeepgramSpeechToText:
    """Implements `SpeechToText` for Nova-3 (ADR-0013)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        connector: WebsocketConnector | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._connector = connector or _default_connector

    async def open_session(self, *, keyterms: list[str]) -> DeepgramSpeechToTextSession:
        url = _build_listen_url(self.model, keyterms)
        headers = {"Authorization": f"Token {self._api_key}"}
        cm = self._connector(url, headers)
        try:
            ws = await cm.__aenter__()
        except (WebSocketException, OSError) as exc:
            raise SpeechUnavailableError() from exc
        return DeepgramSpeechToTextSession(ws, cm)
