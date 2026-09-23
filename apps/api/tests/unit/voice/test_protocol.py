"""Structural conformance: adapters and fakes satisfy the Protocols in app/voice/base.py."""

from app.voice.base import SpeechToText, SpeechToTextSession, TextToSpeech
from app.voice.deepgram_stt import DeepgramSpeechToText
from app.voice.deepgram_tts import DeepgramTextToSpeech
from app.voice.fake import FakeSpeechToText, FakeTextToSpeech


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
