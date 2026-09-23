"""Shared timing/logging helpers for the Deepgram spike scripts, plus (run as `__main__`) the
Task 3.4.4 manual check: streams `tests/fixtures/audio/hello_um.wav` over our own voice
WebSocket (`WS /api/v1/sessions/{id}/voice`) — not directly to Deepgram — using a real push-to-talk
turn, and saves the assistant's spoken reply to a WAV file to listen to.

Throwaway spike code (agent-workflow.md rule A10) — never imported by the app.

Run (owner must first start the api+worker dev servers against real Ollama + Deepgram, and pass a
real voice-mode session id — see docs/tasks/q1-phase-03-voice.md Task 3.4.4):
    cd "apps/api" && uv run python spikes/deepgram/ws_client.py <session_id> [ws_url]
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EventLog:
    """Records events with a timestamp relative to a reference point set by `reset()`."""

    _t0: float = field(default_factory=time.monotonic)
    events: list[tuple[float, str, str]] = field(default_factory=list)

    def reset(self) -> None:
        self._t0 = time.monotonic()

    def mark(self, kind: str, detail: str = "") -> float:
        elapsed = time.monotonic() - self._t0
        self.events.append((elapsed, kind, detail))
        suffix = f": {detail}" if detail else ""
        print(f"  [{elapsed:7.3f}s] {kind}{suffix}")
        return elapsed


async def stream_wav_pcm(path: Path, chunk_ms: int = 100) -> AsyncIterator[bytes]:
    """Yield 16 kHz mono PCM16 chunks from `path`, paced by `asyncio.sleep` like a live mic."""
    with wave.open(str(path), "rb") as wf:
        if wf.getframerate() != 16000:
            raise ValueError(f"{path} is not 16 kHz (got {wf.getframerate()})")
        if wf.getnchannels() != 1:
            raise ValueError(f"{path} is not mono (got {wf.getnchannels()} channels)")
        if wf.getsampwidth() != 2:
            raise ValueError(f"{path} is not 16-bit PCM (got {wf.getsampwidth() * 8}-bit)")
        frames_per_chunk = int(16000 * chunk_ms / 1000)
        while True:
            data = wf.readframes(frames_per_chunk)
            if not data:
                break
            yield data
            await asyncio.sleep(chunk_ms / 1000)


def dump(obj: object) -> dict:
    """Best-effort dict view of an SDK response object, for printing/summaries."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    return {"value": repr(obj)}


HELLO_UM_WAV = Path(__file__).parents[2] / "tests" / "fixtures" / "audio" / "hello_um.wav"
OUTPUT_WAV = Path(__file__).parent / "voice_ws_reply.wav"


def _write_wav(path: Path, pcm16_chunks: list[bytes], *, sample_rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(pcm16_chunks))


async def _run_voice_turn(session_id: str, ws_url: str) -> None:
    import websockets

    log = EventLog()
    audio_chunks: list[bytes] = []

    async with websockets.connect(f"{ws_url}/api/v1/sessions/{session_id}/voice") as ws:
        await ws.send(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        log.mark("sent start")

        async def send_audio() -> None:
            async for chunk in stream_wav_pcm(HELLO_UM_WAV):
                await ws.send(chunk)
            await ws.send(json.dumps({"type": "ptt_up"}))
            log.mark("sent ptt_up")

        audio_task: asyncio.Task[None] | None = None
        while True:
            message = await ws.recv()
            if isinstance(message, bytes):
                audio_chunks.append(message)
                log.mark("audio chunk", f"{len(message)}B")
                continue
            event = json.loads(message)
            log.mark("event", json.dumps(event))
            if event["type"] == "ready":
                await ws.send(json.dumps({"type": "ptt_down"}))
                log.mark("sent ptt_down")
                audio_task = asyncio.create_task(send_audio())
            elif event["type"] == "assistant_turn":
                break
            elif event["type"] == "error" and event.get("fatal"):
                raise RuntimeError(f"fatal error from relay: {event}")

        if audio_task is not None:
            await audio_task

    print(f"\nReceived {len(audio_chunks)} audio chunks, "
          f"{sum(len(c) for c in audio_chunks)} bytes total")
    if audio_chunks:
        _write_wav(OUTPUT_WAV, audio_chunks)
        print(f"Wrote {OUTPUT_WAV} — play it to confirm the assistant's reply sounds right.")
    else:
        print("No audio received — nothing written.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(f"usage: {sys.argv[0]} <session_id> [ws_url=ws://localhost:8000]")
    session_id_arg = sys.argv[1]
    ws_url_arg = sys.argv[2] if len(sys.argv) > 2 else "ws://localhost:8000"
    asyncio.run(_run_voice_turn(session_id_arg, ws_url_arg))
