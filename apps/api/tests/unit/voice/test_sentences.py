from app.voice.sentences import SentenceSplitter


def _stream(splitter: SentenceSplitter, text: str) -> list[str]:
    chunks: list[str] = []
    for char in text:
        chunks.extend(splitter.push(char))
    return chunks


def test_splits_two_sentences_streamed_char_by_char() -> None:
    splitter = SentenceSplitter()
    chunks = _stream(splitter, "Hello there. How are you?")
    chunks.extend(splitter.flush())
    assert chunks == ["Hello there.", "How are you?"]


def test_does_not_split_mid_abbreviation_eg() -> None:
    splitter = SentenceSplitter()
    chunks = _stream(splitter, "e.g. this")
    assert chunks == []
    assert splitter.flush() == ["e.g. this"]


def test_does_not_split_mid_version_token() -> None:
    splitter = SentenceSplitter()
    chunks = _stream(splitter, "v2.1 is out")
    assert chunks == []
    assert splitter.flush() == ["v2.1 is out"]


def test_long_run_on_text_splits_at_comma_or_space_after_200_chars() -> None:
    splitter = SentenceSplitter()
    # No sentence-ending punctuation at all, just a long run-on clause.
    text = ("this is a very long run on explanation that keeps going and going " * 5).strip()
    assert len(text) > 200
    chunks = splitter.push(text)
    assert chunks, "expected the overflow rule to emit at least one chunk"
    first = chunks[0]
    assert first == first.strip()
    assert len(first) >= 200
    # the split happened at the word boundary right after a comma/space in the source text
    assert text.startswith(first)
    assert text[len(first) : len(first) + 1] in (" ", "")


def test_flush_returns_remaining_tail_stripped() -> None:
    splitter = SentenceSplitter()
    splitter.push("just a fragment, no terminator")
    tail = splitter.flush()
    assert tail == ["just a fragment, no terminator"]


def test_flush_returns_empty_list_when_buffer_empty() -> None:
    splitter = SentenceSplitter()
    assert splitter.flush() == []


def test_flush_returns_empty_list_for_whitespace_only_buffer() -> None:
    splitter = SentenceSplitter()
    splitter.push("   ")
    assert splitter.flush() == []


def test_no_empty_chunks_are_ever_emitted() -> None:
    splitter = SentenceSplitter()
    chunks = _stream(splitter, "Short. Also short. And a third one here.")
    chunks.extend(splitter.flush())
    assert all(chunk.strip() for chunk in chunks)
    assert all(chunk == chunk.strip() for chunk in chunks)
