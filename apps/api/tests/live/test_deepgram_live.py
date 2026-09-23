"""Real Deepgram calls (ADR-0013). Run with `make test-live` — costs a small amount on the
owner's account. Skipped unless `DEEPGRAM_API_KEY` is configured.

Excluded by default (`addopts = "-m 'not live'"`); never run in CI or `make check`.
"""

import asyncio
import wave
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.voice.base import TranscriptEvent
from app.voice.deepgram_stt import DeepgramSpeechToText
from app.voice.deepgram_tts import DeepgramTextToSpeech

pytestmark = pytest.mark.live

FIXTURE = Path(__file__).parents[1] / "fixtures" / "audio" / "hello_um.wav"
CHUNK_MS = 100


def _configured_api_key() -> str | None:
    settings = get_settings()
    if settings.deepgram_api_key is None:
        return None
    return settings.deepgram_api_key.get_secret_value()


async def _collect_until_end_of_turn(
    session: object, *, timeout_s: float = 20.0
) -> list[TranscriptEvent]:
    events: list[TranscriptEvent] = []

    async def _run() -> None:
        async for event in session.events():  # type: ignore[attr-defined]
            events.append(event)
            if event.kind == "end_of_turn":
                return

    await asyncio.wait_for(_run(), timeout=timeout_s)
    return events


async def test_streaming_stt_returns_at_least_one_final_with_words() -> None:
    api_key = _configured_api_key()
    if api_key is None:
        pytest.skip("no DEEPGRAM_API_KEY configured")

    stt = DeepgramSpeechToText(api_key, "nova-3")
    session = await stt.open_session(keyterms=[])

    with wave.open(str(FIXTURE), "rb") as wf:
        assert wf.getframerate() == 16000, "fixture must be 16kHz mono PCM16"
        frames_per_chunk = int(16000 * CHUNK_MS / 1000)
        while True:
            data = wf.readframes(frames_per_chunk)
            if not data:
                break
            await session.send_audio(data)
            await asyncio.sleep(CHUNK_MS / 1000)

    await session.finalize()
    events = await _collect_until_end_of_turn(session)
    await session.close()

    finals = [event for event in events if event.kind == "final"]
    assert finals, "expected at least one final transcript event"
    assert any(final.words for final in finals), "expected at least one word with timing"


async def test_tts_synthesizes_more_than_zero_bytes() -> None:
    api_key = _configured_api_key()
    if api_key is None:
        pytest.skip("no DEEPGRAM_API_KEY configured")

    tts = DeepgramTextToSpeech(api_key)

    audio = await tts.synthesize_mp3(voice="aura-2-thalia-en", text="This is a live test.")

    assert len(audio) > 0
