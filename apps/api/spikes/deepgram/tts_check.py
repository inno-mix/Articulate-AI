"""Deepgram TTS spike: voice ids, first-byte latency, REST MP3, speed parameter, mip_opt_out.

Throwaway spike code (agent-workflow.md rule A10) — answers the Task 3.1 questions in
docs/tasks/q1-phase-03-voice.md. Every request sets mip_opt_out=True (ADR-0016).

Run:
    cd "apps/api" && uv run python spikes/deepgram/tts_check.py

Requires DEEPGRAM_API_KEY in apps/api/.env.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from pathlib import Path

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import SpeakV1ControlMessage, SpeakV1TextMessage

# SDK v5.3.4 note: see stt_compare.py — send_flush()/send_close() and `deepgram.speak.v1.types`
# don't exist in this installed version either; use send_control(SpeakV1ControlMessage(...)).

sys.path.insert(0, str(Path(__file__).parent))
from ws_client import EventLog  # noqa: E402

# From voice-and-pronunciation.md §7 — to be verified/replaced by this spike.
CURATED_VOICES = [
    "aura-2-thalia-en",
    "aura-2-asteria-en",
    "aura-2-andromeda-en",
    "aura-2-apollo-en",
    "aura-2-arcas-en",
    "aura-2-helena-en",
]
SENTENCE = "Thanks for the update, let's sync again tomorrow morning."


def _client() -> AsyncDeepgramClient:
    return AsyncDeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])


async def check_voice_ws(voice: str) -> dict:
    """Q5: open one speak.v1 WS per voice; measure first-byte latency and total bytes."""
    log = EventLog()
    first_byte_delay: float | None = None
    total_bytes = 0
    flushed = False
    errors: list[str] = []
    print(f"\n=== Speak WS · {voice} ===")
    try:
        async with _client().speak.v1.connect(
            model=voice, encoding="linear16", sample_rate=24000, mip_opt_out=True
        ) as connection:

            def on_message(message: object) -> None:
                nonlocal first_byte_delay, total_bytes, flushed
                if isinstance(message, bytes | bytearray):
                    if first_byte_delay is None:
                        first_byte_delay = log.mark("first_audio_byte", f"{len(message)}B")
                    total_bytes += len(message)
                else:
                    msg_type = getattr(message, "type", type(message).__name__)
                    log.mark(str(msg_type))
                    if msg_type == "Flushed":
                        flushed = True

            connection.on(EventType.OPEN, lambda _: log.mark("OPEN"))
            connection.on(EventType.MESSAGE, on_message)
            connection.on(EventType.CLOSE, lambda _: log.mark("CLOSE"))
            connection.on(EventType.ERROR, lambda e: (errors.append(str(e)), log.mark("ERROR", str(e))))

            # start_listening() blocks until close (see stt_compare.py) — run concurrently.
            listen_task = asyncio.create_task(connection.start_listening())
            log.reset()
            await connection.send_text(SpeakV1TextMessage(type="Speak", text=SENTENCE))
            await connection.send_control(SpeakV1ControlMessage(type="Flush"))
            log.mark("send_flush_called")

            for _ in range(50):
                if flushed:
                    break
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.3)
            await connection.send_control(SpeakV1ControlMessage(type="Close"))
            with contextlib.suppress(Exception):
                await asyncio.wait_for(listen_task, timeout=2.0)
    except Exception as exc:  # noqa: BLE001 — spike: record and keep going
        errors.append(repr(exc))
        log.mark("EXCEPTION", repr(exc))

    exists = total_bytes > 0 and not errors
    return {
        "voice": voice,
        "exists": exists,
        "first_byte_delay_s": first_byte_delay,
        "total_bytes": total_bytes,
        "errors": errors,
    }


async def check_rest_mp3(voice: str = "aura-2-thalia-en") -> dict:
    """Q6: SDK v5 method for REST TTS (MP3).

    NOTE: the SDK v5.3.4 docs (Context7) show `response.stream.getvalue()`, but
    inspect.signature shows generate() -> typing.AsyncIterator[bytes] in this version — it's an
    async generator of chunks, not an object with a `.stream` attribute.
    """
    print(f"\n=== REST speak (MP3) · {voice} ===")
    client = _client()
    chunks = [chunk async for chunk in client.speak.v1.audio.generate(text=SENTENCE, model=voice, mip_opt_out=True)]
    data = b"".join(chunks)
    print(f"  bytes={len(data)}")
    return {"voice": voice, "bytes": len(data)}


async def check_speed(voice: str = "aura-2-thalia-en") -> dict:
    """Q5: is there a speed parameter for Aura-2? Compare byte length at 0.7x vs 1.5x."""
    print(f"\n=== REST speak speed probe · {voice} ===")
    client = _client()
    results = {}
    for speed in (0.7, 1.0, 1.5):
        try:
            # SDK v5.3.4's typed generate() has no `speed` kwarg (checked via inspect.signature)
            # even though the REST /v1/speak query param is documented — inject it directly.
            chunks = [
                chunk
                async for chunk in client.speak.v1.audio.generate(
                    text=SENTENCE,
                    model=voice,
                    mip_opt_out=True,
                    request_options={"additional_query_parameters": {"speed": speed}},
                )
            ]
            data = b"".join(chunks)
            print(f"  speed={speed}: bytes={len(data)}")
            results[str(speed)] = {"bytes": len(data), "error": None}
        except Exception as exc:  # noqa: BLE001 — spike: record and keep going
            print(f"  speed={speed}: ERROR {exc!r}")
            results[str(speed)] = {"bytes": None, "error": repr(exc)}
    return results


async def main() -> None:
    voice_results = []
    for voice in CURATED_VOICES:
        voice_results.append(await check_voice_ws(voice))

    print("\n\n=== Voice summary ===")
    header = f"{'voice':22} {'exists':>7} {'first-byte(s)':>14} {'bytes':>8} {'errors'}"
    print(header)
    print("-" * len(header))
    for r in voice_results:
        fb = f"{r['first_byte_delay_s']:.3f}" if r["first_byte_delay_s"] is not None else "—"
        print(
            f"{r['voice']:22} {str(r['exists']):>7} {fb:>14} {r['total_bytes']:>8} "
            f"{r['errors'] or ''}"
        )

    await check_rest_mp3()
    speed_results = await check_speed()

    print("\n=== Speed probe summary ===")
    for speed, info in speed_results.items():
        print(f"  speed={speed}: {info}")


if __name__ == "__main__":
    asyncio.run(main())
