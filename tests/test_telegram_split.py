"""Unit tests for nerve.channels.telegram._smart_split."""

from nerve.channels.telegram import _smart_split, MAX_MSG_LEN


def test_short_text_returns_single_chunk_unchanged():
    text = "hello world"
    assert _smart_split(text, limit=4096) == ["hello world"]


def test_text_at_exact_limit_is_single_chunk():
    text = "x" * 4096
    chunks = _smart_split(text, limit=4096)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_text_one_over_limit_splits_into_two():
    text = "x" * 4097
    chunks = _smart_split(text, limit=4096)
    assert len(chunks) == 2
    # No data lost
    assert sum(len(c) - len(_continuation_prefix(c)) for c in chunks) == 4097


def test_paragraph_boundary_used_when_possible():
    para_a = "a" * 2000
    para_b = "b" * 2000
    para_c = "c" * 2000
    text = f"{para_a}\n\n{para_b}\n\n{para_c}"
    chunks = _smart_split(text, limit=4096)
    # Two of three paragraphs fit in first chunk; third in second
    assert len(chunks) == 2
    # Each chunk respects the limit
    assert all(len(c) <= 4096 for c in chunks)
    # Joined data round-trips (modulo continuation markers and spacing)
    rebuilt = "\n\n".join(_strip_continuation_prefix(c) for c in chunks)
    assert para_a in rebuilt
    assert para_b in rebuilt
    assert para_c in rebuilt


def _continuation_prefix(chunk: str) -> str:
    """Helper for tests — extract `(N/M)\\n` prefix if present."""
    import re
    m = re.match(r"^\(\d+/\d+\)\n", chunk)
    return m.group(0) if m else ""


def _strip_continuation_prefix(chunk: str) -> str:
    return chunk[len(_continuation_prefix(chunk)):]
