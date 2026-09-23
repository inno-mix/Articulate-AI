import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace

import httpx
import pytest
import respx
from deepgram.core.events import EventType

from app.core.errors import SpeechUnavailableError
from app.voice.deepgram_tts import DeepgramTextToSpeech

DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"


class FakeSpeakConnection:
    def __init__(self, audio_by_sentence: dict[str, list[bytes]] | None = None) -> None:
        self.sent_texts: list[str] = []
        self.controls: list[str] = []
        self._audio_by_sentence = audio_by_sentence or {}
        self._message_handler = None
        self._closed = asyncio.Event()

    def on(self, event_type: object, handler: object) -> None:
        if event_type == EventType.MESSAGE:
            self._message_handler = handler

    async def send_text(self, message: object) -> None:
        text = message.text  # type: ignore[attr-defined]
        self.sent_texts.append(text)
        for chunk in self._audio_by_sentence.get(text, [f"audio-{text}".encode()]):
            self._message_handler(chunk)  # type: ignore[misc]

    async def send_control(self, message: object) -> None:
        control_type = message.type  # type: ignore[attr-defined]
        self.controls.append(control_type)
        if control_type == "Flush":
            self._message_handler(SimpleNamespace(type="Flushed"))  # type: ignore[misc]
        elif control_type == "Close":
            self._closed.set()

    async def start_listening(self) -> None:
        await self._closed.wait()


class FakeSpeakConnectCM:
    def __init__(self, connection: FakeSpeakConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> FakeSpeakConnection:
        return self._connection

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class FakeSpeakV1:
    def __init__(self, connection: FakeSpeakConnection) -> None:
        self._connection = connection
        self.connect_kwargs: dict[str, object] | None = None

    def connect(self, **kwargs: object) -> FakeSpeakConnectCM:
        self.connect_kwargs = kwargs
        return FakeSpeakConnectCM(self._connection)


class FakeDeepgramClient:
    def __init__(self, connection: FakeSpeakConnection) -> None:
        self.speak = SimpleNamespace(v1=FakeSpeakV1(connection))


async def _sentences(items: list[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


async def test_synthesize_sends_each_sentence_and_flushes_once() -> None:
    connection = FakeSpeakConnection()
    tts = DeepgramTextToSpeech("key", client_factory=lambda: FakeDeepgramClient(connection))

    chunks = [
        chunk
        async for chunk in tts.synthesize(
            voice="aura-2-thalia-en", sentences=_sentences(["Hi.", "Bye."])
        )
    ]

    assert connection.sent_texts == ["Hi.", "Bye."]
    assert connection.controls.count("Flush") == 1
    assert chunks == [b"audio-Hi.", b"audio-Bye."]


async def test_synthesize_stops_after_flushed_event() -> None:
    connection = FakeSpeakConnection(audio_by_sentence={"Hi.": [b"a", b"b"]})
    tts = DeepgramTextToSpeech("key", client_factory=lambda: FakeDeepgramClient(connection))

    chunks = [chunk async for chunk in tts.synthesize(voice="v", sentences=_sentences(["Hi."]))]

    assert chunks == [b"a", b"b"]


async def test_synthesize_closes_the_connection_after_flush() -> None:
    connection = FakeSpeakConnection()
    tts = DeepgramTextToSpeech("key", client_factory=lambda: FakeDeepgramClient(connection))

    _ = [chunk async for chunk in tts.synthesize(voice="v", sentences=_sentences(["Hi."]))]

    assert connection.controls[-1] == "Close"


async def test_synthesize_websocket_carries_mip_opt_out() -> None:
    connection = FakeSpeakConnection()
    fake_client = FakeDeepgramClient(connection)
    tts = DeepgramTextToSpeech("key", client_factory=lambda: fake_client)

    _ = [chunk async for chunk in tts.synthesize(voice="v", sentences=_sentences(["Hi."]))]

    assert fake_client.speak.v1.connect_kwargs is not None
    assert fake_client.speak.v1.connect_kwargs["mip_opt_out"] is True


async def test_synthesize_mp3_returns_bytes_and_carries_mip_opt_out() -> None:
    tts = DeepgramTextToSpeech("key")

    with respx.mock(assert_all_called=True) as router:
        route = router.post(url__startswith=DEEPGRAM_SPEAK_URL).mock(
            return_value=httpx.Response(200, content=b"mp3-bytes")
        )
        audio = await tts.synthesize_mp3(voice="aura-2-thalia-en", text="hi")

    assert audio == b"mp3-bytes"
    assert "mip_opt_out=true" in str(route.calls.last.request.url)


async def test_synthesize_mp3_5xx_raises_speech_unavailable() -> None:
    tts = DeepgramTextToSpeech("key")

    with respx.mock(assert_all_called=True) as router:
        router.post(url__startswith=DEEPGRAM_SPEAK_URL).mock(return_value=httpx.Response(500))
        with pytest.raises(SpeechUnavailableError):
            await tts.synthesize_mp3(voice="aura-2-thalia-en", text="hi")
