"""Deepgram STT spike: compares Nova-3 (listen.v1) and Flux (listen.v2) on real clips.

Throwaway spike code (agent-workflow.md rule A10) — answers the Task 3.1 questions in
docs/tasks/q1-phase-03-voice.md. Every request sets mip_opt_out=True (ADR-0016).

Run:
    cd "apps/api" && uv run python spikes/deepgram/stt_compare.py

Requires DEEPGRAM_API_KEY in apps/api/.env and the two clips from subtask 3.1.1 at
spikes/deepgram/audio/{clip-a,clip-b}.wav (16 kHz mono PCM16 WAV).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from pathlib import Path

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import ListenV1ControlMessage, ListenV2ControlMessage

# SDK v5.3.4 note: docs (Context7) describe convenience methods send_finalize()/
# send_close_stream() and a `deepgram.listen.v1.types` module — neither exists in this
# installed version. The real API is send_control(ListenV1ControlMessage(type=...)) with
# messages imported from deepgram.extensions.types.sockets (confirmed by reading the SDK
# source in .venv, not by guessing).

sys.path.insert(0, str(Path(__file__).parent))
from ws_client import EventLog, dump, stream_wav_pcm  # noqa: E402

AUDIO_DIR = Path(__file__).parent / "audio"
CLIP_A = AUDIO_DIR / "clip-a.wav"  # ~15s, um/uh, "Kubernetes", "PostgreSQL"
CLIP_B = AUDIO_DIR / "clip-b.wav"  # ~10s, ends with a clear 2s silence
KEYTERMS = ["Kubernetes", "PostgreSQL", "idempotent"]


def _client() -> AsyncDeepgramClient:
    return AsyncDeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])


async def run_nova3(
    clip: Path,
    *,
    label: str,
    keyterm: list[str] | None = None,
    finalize_immediately: bool = False,
) -> dict:
    """Stream `clip` to Nova-3 (listen.v1); log every event; return a summary dict."""
    log = EventLog()
    transcripts: list[str] = []
    words_seen: list[dict] = []
    speech_final_delay: float | None = None
    utterance_end_delay: float | None = None
    finalize_ack_delay: float | None = None
    errors: list[str] = []

    kwargs: dict = dict(
        model="nova-3",
        language="en-US",
        encoding="linear16",
        sample_rate=16000,
        channels=1,
        interim_results=True,
        punctuate=True,
        smart_format=True,
        endpointing=300,
        utterance_end_ms=1000,
        vad_events=True,
        mip_opt_out=True,
        # NOTE: SDK v5.3.4's typed listen.v1.connect() has no `filler_words` kwarg, and
        # request_options["additional_query_parameters"] is silently ignored for WS connects
        # (confirmed by reading listen/v1/client.py — only additional_headers is applied to the
        # query string). filler_words=true genuinely works at the protocol level (confirmed via
        # a raw `websockets.connect()` with the query string built by hand: "um"/"uh" appear in
        # the transcript) but is unreachable through this SDK version's typed connect(). This run
        # therefore reflects the SDK's actual (filler-stripped) default — see ADR-0013 for the
        # raw-websocket evidence and the Task 3.3 workaround this implies.
    )
    if keyterm:
        kwargs["keyterm"] = keyterm

    print(f"\n=== Nova-3 · {label} ({clip.name}, keyterm={keyterm}) ===")
    async with _client().listen.v1.connect(**kwargs) as connection:

        def on_message(message: object) -> None:
            nonlocal speech_final_delay, utterance_end_delay, finalize_ack_delay
            msg_type = getattr(message, "type", type(message).__name__)
            if msg_type == "Results":
                alt = message.channel.alternatives[0]  # type: ignore[attr-defined]
                if alt.transcript:
                    transcripts.append(alt.transcript)
                    words_seen.extend(dump(w) for w in (alt.words or []))
                is_final = getattr(message, "is_final", None)
                speech_final = getattr(message, "speech_final", None)
                from_finalize = getattr(message, "from_finalize", None)
                t = log.mark(
                    "Results",
                    f"transcript={alt.transcript!r} is_final={is_final} "
                    f"speech_final={speech_final} from_finalize={from_finalize}",
                )
                if speech_final and speech_final_delay is None:
                    speech_final_delay = t
                if from_finalize and finalize_ack_delay is None:
                    finalize_ack_delay = t
            elif msg_type == "UtteranceEnd":
                t = log.mark("UtteranceEnd")
                if utterance_end_delay is None:
                    utterance_end_delay = t
            else:
                log.mark(str(msg_type))

        connection.on(EventType.OPEN, lambda _: log.mark("OPEN"))
        connection.on(EventType.MESSAGE, on_message)
        connection.on(EventType.CLOSE, lambda _: log.mark("CLOSE"))
        connection.on(EventType.ERROR, lambda e: (errors.append(str(e)), log.mark("ERROR", str(e))))

        # start_listening() is a blocking receive loop (async for message in websocket) that
        # only returns on close — it must run concurrently with sending audio, not be awaited
        # inline (confirmed by reading socket_client.py; the SDK's own async example is
        # misleading here since it only ever sends one chunk after awaiting it).
        listen_task = asyncio.create_task(connection.start_listening())

        async for chunk in stream_wav_pcm(clip):
            await connection.send_media(chunk)

        log.reset()  # everything below is timed relative to the last audio chunk sent
        log.mark("last_audio_chunk_sent")

        if finalize_immediately:
            await connection.send_control(ListenV1ControlMessage(type="Finalize"))
            log.mark("send_finalize_called")

        await asyncio.sleep(3.0)  # let trailing events (UtteranceEnd, final Results) arrive
        await connection.send_control(ListenV1ControlMessage(type="CloseStream"))
        with contextlib.suppress(Exception):
            await asyncio.wait_for(listen_task, timeout=2.0)

    return {
        "model": "nova-3",
        "label": label,
        "clip": clip.name,
        "keyterm": keyterm,
        "finalize_immediately": finalize_immediately,
        "transcript": " ".join(transcripts),
        "word_count": len(words_seen),
        "sample_words": words_seen[:8],
        "speech_final_delay_s": speech_final_delay,
        "utterance_end_delay_s": utterance_end_delay,
        "finalize_ack_delay_s": finalize_ack_delay,
        "errors": errors,
    }


async def run_flux(clip: Path, *, label: str) -> dict:
    """Stream `clip` to Flux (listen.v2); log every TurnInfo event; return a summary dict."""
    log = EventLog()
    final_transcript = ""
    words_seen: list[dict] = []
    end_of_turn_delay: float | None = None
    end_of_turn_trigger: str | None = None
    eager_end_of_turn_delay: float | None = None
    events_seen: set[str] = set()
    errors: list[str] = []

    print(f"\n=== Flux · {label} ({clip.name}) ===")
    # v2 has no typed filler_words kwarg either, and (like v1) additional_query_parameters is
    # dropped for WS connects — see run_nova3's note. Flux's own event schema never shows a
    # filler flag either way (checked via Context7 docs), so this isn't expected to change.
    async with _client().listen.v2.connect(
        model="flux-general-en",
        encoding="linear16",
        sample_rate=16000,
        mip_opt_out=True,
    ) as connection:

        def on_message(message: object) -> None:
            nonlocal final_transcript, end_of_turn_delay, end_of_turn_trigger, eager_end_of_turn_delay
            msg_type = getattr(message, "type", type(message).__name__)
            event = getattr(message, "event", None)
            if event:
                events_seen.add(event)
                transcript = getattr(message, "transcript", "") or ""
                words = getattr(message, "words", None) or []
                t = log.mark(event, f"transcript={transcript!r} words={len(words)}")
                if event == "EndOfTurn":
                    final_transcript = transcript
                    words_seen.extend(dump(w) for w in words)
                    if end_of_turn_delay is None:
                        end_of_turn_delay = t
                        end_of_turn_trigger = getattr(message, "trigger", None)
                elif event == "EagerEndOfTurn" and eager_end_of_turn_delay is None:
                    eager_end_of_turn_delay = t
            else:
                log.mark(str(msg_type))

        connection.on(EventType.OPEN, lambda _: log.mark("OPEN"))
        connection.on(EventType.MESSAGE, on_message)
        connection.on(EventType.CLOSE, lambda _: log.mark("CLOSE"))
        connection.on(EventType.ERROR, lambda e: (errors.append(str(e)), log.mark("ERROR", str(e))))

        listen_task = asyncio.create_task(connection.start_listening())

        async for chunk in stream_wav_pcm(clip):
            await connection.send_media(chunk)

        log.reset()
        log.mark("last_audio_chunk_sent")

        await asyncio.sleep(3.0)
        await connection.send_control(ListenV2ControlMessage(type="CloseStream"))
        with contextlib.suppress(Exception):
            await asyncio.wait_for(listen_task, timeout=2.0)

    return {
        "model": "flux-general-en",
        "label": label,
        "clip": clip.name,
        "transcript": final_transcript,
        "word_count": len(words_seen),
        "sample_words": words_seen[:8],
        "events_seen": sorted(events_seen),
        "end_of_turn_delay_s": end_of_turn_delay,
        "end_of_turn_trigger": end_of_turn_trigger,
        "eager_end_of_turn_delay_s": eager_end_of_turn_delay,
        "errors": errors,
    }


async def run_prerecorded(clip: Path) -> dict:
    """Q6/Q7: SDK v5 pre-recorded transcription method name + mip_opt_out acceptance."""
    print(f"\n=== Pre-recorded (listen.v1.media.transcribe_file) · {clip.name} ===")
    client = _client()
    with open(clip, "rb") as f:
        response = await client.listen.v1.media.transcribe_file(
            request=f.read(),
            model="nova-3",
            punctuate=True,
            smart_format=True,
            filler_words=True,
            mip_opt_out=True,
        )
    alt = response.results.channels[0].alternatives[0]
    print(f"  transcript={alt.transcript!r}")
    return {"transcript": alt.transcript, "word_count": len(alt.words or [])}


def _print_summary(results: list[dict]) -> None:
    print("\n\n=== Summary ===")
    header = f"{'label':28} {'model':16} {'words':>6} {'key delay(s)':>14} {'errors':>7}"
    print(header)
    print("-" * len(header))
    for r in results:
        if "model" not in r:
            continue
        delay = (
            r.get("finalize_ack_delay_s")
            or r.get("speech_final_delay_s")
            or r.get("utterance_end_delay_s")
            or r.get("end_of_turn_delay_s")
        )
        delay_str = f"{delay:.3f}" if delay is not None else "—"
        print(
            f"{r['label']:28} {r['model']:16} {r['word_count']:>6} {delay_str:>14} "
            f"{len(r.get('errors', [])):>7}"
        )


async def main() -> None:
    if not CLIP_A.exists() or not CLIP_B.exists():
        raise SystemExit(
            f"Missing spike audio. Expected {CLIP_A} and {CLIP_B} — see subtask 3.1.1."
        )

    results = []
    # Q1 + Q4: fillers + keyterm effect on Nova-3
    results.append(await run_nova3(CLIP_A, label="nova3-clip-a-no-keyterm"))
    results.append(await run_nova3(CLIP_A, label="nova3-clip-a-with-keyterm", keyterm=KEYTERMS))
    # Q3: natural endpointing/UtteranceEnd delay vs. send_finalize() (push-to-talk) delay
    results.append(await run_nova3(CLIP_B, label="nova3-clip-b-natural-endpointing"))
    results.append(
        await run_nova3(CLIP_B, label="nova3-clip-b-send-finalize", finalize_immediately=True)
    )
    # Q2: Flux fillers, word timings/confidence, end-of-turn events + delay
    results.append(await run_flux(CLIP_A, label="flux-clip-a"))
    results.append(await run_flux(CLIP_B, label="flux-clip-b"))

    _print_summary(results)

    # Q6 + Q7: pre-recorded transcription method + mip_opt_out
    await run_prerecorded(CLIP_A)

    print("\nFull per-run detail (transcripts, sample words):")
    for r in results:
        print(f"\n--- {r['label']} ---")
        for k, v in r.items():
            if k == "sample_words":
                continue
            print(f"  {k}: {v}")
        if r["sample_words"]:
            print(f"  sample_words[0]: {r['sample_words'][0]}")


if __name__ == "__main__":
    asyncio.run(main())
