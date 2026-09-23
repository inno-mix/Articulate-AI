"""Structural conformance: adapters and fakes satisfy the Protocols in app/voice/base.py.

Also covers the WS message protocol in app/voice/protocol.py (Task 3.4) — same test file per
the phase plan's file map.
"""

import json

import pytest

from app.voice.base import SpeechToText, SpeechToTextSession, TextToSpeech
from app.voice.deepgram_stt import DeepgramSpeechToText
from app.voice.deepgram_tts import DeepgramTextToSpeech
from app.voice.fake import FakeSpeechToText, FakeTextToSpeech
from app.voice.protocol import (
    CancelTurn,
    EndSession,
    Error,
    Paused,
    Ping,
    Pong,
    ProtocolError,
    PttDown,
    PttUp,
    Ready,
    Resume,
    Start,
    parse_client_message,
)


def test_fake_speech_to_text_matches_protocol() -> None:
    assert isinstance(FakeSpeechToText(), SpeechToText)


def test_deepgram_speech_to_text_matches_protocol() -> None:
    assert isinstance(DeepgramSpeechToText("key", "nova-3"), SpeechToText)


def test_fake_text_to_speech_matches_protocol() -> None:
    assert isinstance(FakeTextToSpeech(), TextToSpeech)


def test_deepgram_text_to_speech_matches_protocol() -> None:
    assert isinstance(DeepgramTextToSpeech("key"), TextToSpeech)


async def test_fake_session_matches_protocol() -> None:
    stt = FakeSpeechToText(silent=True)
    session = await stt.open_session(keyterms=[])
    assert isinstance(session, SpeechToTextSession)


@pytest.mark.parametrize(
    ("raw", "expected_type"),
    [
        ('{"type":"start","input_mode":"push_to_talk"}', Start),
        ('{"type":"ptt_down"}', PttDown),
        ('{"type":"ptt_up"}', PttUp),
        ('{"type":"cancel_turn"}', CancelTurn),
        ('{"type":"resume"}', Resume),
        ('{"type":"end_session"}', EndSession),
        ('{"type":"ping"}', Ping),
    ],
)
def test_parse_client_message_parses_every_known_type(raw: str, expected_type: type) -> None:
    message = parse_client_message(raw)
    assert isinstance(message, expected_type)


def test_parse_start_message_keeps_input_mode() -> None:
    message = parse_client_message('{"type":"start","input_mode":"hands_free"}')
    assert isinstance(message, Start)
    assert message.input_mode == "hands_free"


def test_parse_client_message_rejects_unknown_type() -> None:
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"not_a_real_type"}')


def test_parse_client_message_rejects_invalid_json() -> None:
    with pytest.raises(ProtocolError):
        parse_client_message("{not json")


def test_parse_client_message_rejects_unknown_fields() -> None:
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"ping","extra":"field"}')


def test_server_events_serialise_with_type_field() -> None:
    events = [
        Ready(state="idle", stt_model="nova-3"),
        Pong(),
        Paused(),
        Error(code="speech_unavailable", message="oops", fatal=False),
    ]
    for event in events:
        payload = json.loads(event.model_dump_json())
        assert payload["type"] == event.type
