"""Shared timing/logging helpers for the Deepgram spike scripts.

Throwaway spike code (agent-workflow.md rule A10) — never imported by the app.
"""

from __future__ import annotations

import asyncio
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
