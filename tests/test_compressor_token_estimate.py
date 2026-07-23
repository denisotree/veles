"""M222: token estimation uses a real tokenizer (tiktoken o200k_base) with a
bytes/4 fallback, replacing the old bytes/4-only heuristic.

The old heuristic counted UTF-8 bytes/4, which was conservative-high — it fired
compression before the real threshold (an extra summariser call) and, on
Cyrillic, over-counted ~2x. The real tokenizer counts accurately, so the
compression window tracks the model's actual limit.
"""

from __future__ import annotations

import pytest

from veles.core.context_compressor import estimate_tokens
from veles.core.provider import Message
from veles.core.tokenizer import _reset_encoder_cache, count_tokens


@pytest.fixture(autouse=True)
def _fresh_encoder():
    _reset_encoder_cache()
    yield
    _reset_encoder_cache()


def test_count_tokens_english_below_bytes_over_4() -> None:
    # A real tokenizer merges common words, so a natural sentence counts well
    # under its bytes/4 upper bound — the old heuristic over-counted.
    text = "The quick brown fox jumps over the lazy dog every single morning."
    n = count_tokens(text)
    assert 0 < n < len(text.encode("utf-8")) // 4


def test_count_tokens_cyrillic_not_double_counted() -> None:
    # bytes/4 counted Cyrillic at ~2 bytes/char → ~2x the real token count.
    text = "Привет, как дела сегодня утром на работе и дома?"
    assert count_tokens(text) < len(text.encode("utf-8")) // 4


def test_count_tokens_empty_is_zero() -> None:
    assert count_tokens("") == 0


def test_estimate_tokens_sums_message_contents() -> None:
    h = [Message(role="user", content="hello world"), Message(role="assistant", content="hi there")]
    assert estimate_tokens(h) == count_tokens("hello world") + count_tokens("hi there")


def test_fallback_to_bytes_over_4_when_encoder_unavailable(monkeypatch) -> None:
    import veles.core.tokenizer as tk

    monkeypatch.setattr(tk, "_get_encoder", lambda: None)
    text = "abcd" * 10  # 40 UTF-8 bytes
    assert tk.count_tokens(text) == 40 // 4
