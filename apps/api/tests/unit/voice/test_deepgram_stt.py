import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.core.errors import SpeechUnavailableError
from app.voice.base import TranscriptEvent
from app.voice.deepgram_stt import DeepgramSpeechToText, _build_listen_url

FIXTURES = Path(__file__).parents[2] / "fixtures" / "deepgram"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeWebsocket:
    def __init__(self, messages: list[str] | None = None) -> None:
        self._messages = messages or []
        self.sent: list[bytes | str] = []

    async def send(self, message: bytes | str) -> None:
        self.sent.append(message)

    def __aiter__(self) -> AsyncIterator[str]:
        return self._aiter()

    async def _aiter(self) -> AsyncIterator[str]:
        for message in self._messages:
            yield message


class FakeConnectionContext:
    def __init__(self, ws: FakeWebsocket | None = None, *, error: Exception | None = None) -> None:
        self._ws = ws
        self._error = error

    async def __aenter__(self) -> FakeWebsocket:
        if self._error is not None:
            raise self._error
        assert self._ws is not None
        return self._ws

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def make_connector(
    messages: list[str] | None = None,
) -> tuple[object, FakeWebsocket, dict[str, str]]:
    ws = FakeWebsocket(messages)
    captured: dict[str, str] = {}

    def connector(url: str, headers: dict[str, str]) -> FakeConnectionContext:
        captured["url"] = url
        captured["headers"] = str(headers)
        return FakeConnectionContext(ws)

    return connector, ws, captured


async def _collect(events: AsyncIterator[TranscriptEvent]) -> list[TranscriptEvent]:
    return [event async for event in events]


def test_build_listen_url_includes_filler_words_and_model() -> None:
    url = _build_listen_url("nova-3", [])
    assert "model=nova-3" in url
    assert "filler_words=true" in url
    assert "mip_opt_out=true" in url


def test_build_listen_url_caps_keyterms_at_20() -> None:
    url = _build_listen_url("nova-3", [f"term{i}" for i in range(30)])
    assert url.count("keyterm=") == 20


async def test_interim_result_maps_to_interim_event() -> None:
    connector, _ws, _ = make_connector([_load("results_interim.json")])
    stt = DeepgramSpeechToText("key", "nova-3", connector=connector)

    session = await stt.open_session(keyterms=[])
    events = await _collect(session.events())

    assert len(events) == 1
    assert events[0].kind == "interim"
    assert events[0].text == "hello there"
    assert events[0].words == []


async def test_final_result_maps_to_final_then_end_of_turn_with_filler_flags_set() -> None:
    connector, _ws, _ = make_connector([_load("results_final.json")])
    stt = DeepgramSpeechToText("key", "nova-3", connector=connector)

    session = await stt.open_session(keyterms=[])
    events = await _collect(session.events())

    assert [e.kind for e in events] == ["final", "end_of_turn"]
    final = events[0]
    assert final.text == "hello um there"
    assert [w.word for w in final.words] == ["hello", "um", "there"]
    assert [w.is_filler for w in final.words] == [False, True, False]
    assert final.words[2].confidence == 0.55


async def test_empty_speech_final_message_maps_to_end_of_turn_only() -> None:
    connector, _ws, _ = make_connector([_load("results_end_of_turn.json")])
    stt = DeepgramSpeechToText("key", "nova-3", connector=connector)

    session = await stt.open_session(keyterms=[])
    events = await _collect(session.events())

    assert len(events) == 1
    assert events[0].kind == "end_of_turn"


async def test_send_audio_sends_raw_bytes() -> None:
    connector, ws, _ = make_connector()
    stt = DeepgramSpeechToText("key", "nova-3", connector=connector)
    session = await stt.open_session(keyterms=[])

    await session.send_audio(b"\x01\x02\x03")

    assert ws.sent == [b"\x01\x02\x03"]
    await session.close()


async def test_finalize_sends_finalize_control_message() -> None:
    connector, ws, _ = make_connector()
    stt = DeepgramSpeechToText("key", "nova-3", connector=connector)
    session = await stt.open_session(keyterms=[])

    await session.finalize()

    assert json.loads(ws.sent[-1]) == {"type": "Finalize"}
    await session.close()


async def test_close_sends_close_stream_control_message() -> None:
    connector, ws, _ = make_connector()
    stt = DeepgramSpeechToText("key", "nova-3", connector=connector)
    session = await stt.open_session(keyterms=[])

    await session.close()

    assert json.loads(ws.sent[-1]) == {"type": "CloseStream"}


async def test_connection_error_raises_speech_unavailable() -> None:
    def connector(url: str, headers: dict[str, str]) -> FakeConnectionContext:
        return FakeConnectionContext(error=OSError("boom"))

    stt = DeepgramSpeechToText("key", "nova-3", connector=connector)

    with pytest.raises(SpeechUnavailableError):
        await stt.open_session(keyterms=[])


async def test_keyterms_are_passed_through_and_capped_at_20() -> None:
    connector, _ws, captured = make_connector()
    stt = DeepgramSpeechToText("key", "nova-3", connector=connector)

    session = await stt.open_session(keyterms=[f"term{i}" for i in range(25)])
    await session.close()

    assert captured["url"].count("keyterm=") == 20
    assert "term0" in captured["url"]


async def test_connection_opts_out_of_model_improvement() -> None:
    connector, _ws, captured = make_connector()
    stt = DeepgramSpeechToText("key", "nova-3", connector=connector)

    session = await stt.open_session(keyterms=[])
    await session.close()

    assert "mip_opt_out=true" in captured["url"]
