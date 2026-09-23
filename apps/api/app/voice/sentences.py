"""Buffers streamed LLM text into TTS-ready chunks (voice-and-pronunciation.md §2.5 step 4)."""

import re

MIN_CHUNK_CHARS = 20
MAX_CHUNK_CHARS = 200

_SENTENCE_END_RE = re.compile(r"[.?!](?=\s|$)")
_OVERFLOW_SPLIT_RE = re.compile(r"[, ]")


class SentenceSplitter:
    """Buffers text deltas and emits complete chunks ready for TTS."""

    def __init__(self) -> None:
        self._buffer = ""

    def push(self, delta: str) -> list[str]:
        """Append `delta` to the buffer; return any chunks now ready to speak."""
        self._buffer += delta
        chunks: list[str] = []
        while (chunk := self._extract_chunk()) is not None:
            chunks.append(chunk)
        return chunks

    def flush(self) -> list[str]:
        """Return the remaining buffered text (stripped), if any, and clear the buffer."""
        tail = self._buffer.strip()
        self._buffer = ""
        return [tail] if tail else []

    def _extract_chunk(self) -> str | None:
        if len(self._buffer) >= MIN_CHUNK_CHARS:
            match = _SENTENCE_END_RE.search(self._buffer)
            if match:
                return self._split_at(match.end())

        if len(self._buffer) > MAX_CHUNK_CHARS:
            match = _OVERFLOW_SPLIT_RE.search(self._buffer, MAX_CHUNK_CHARS)
            if match:
                return self._split_at(match.end())

        return None

    def _split_at(self, index: int) -> str:
        chunk = self._buffer[:index].strip()
        self._buffer = self._buffer[index:].lstrip()
        return chunk
