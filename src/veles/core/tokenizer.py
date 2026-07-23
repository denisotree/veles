"""M222: real token counting with a bytes/4 fallback.

`estimate_tokens` used a flat bytes/4 heuristic to size the compression window.
It is deliberately conservative-high (bytes/4 overcounts ASCII, roughly matches
Cyrillic/CJK), which meant compression fired *earlier* than the real threshold —
one extra summariser sub-agent call each time it triggered too soon.

Anthropic (Veles' default via OpenRouter) ships no public exact tokenizer, so we
use tiktoken's `o200k_base` — within ~10-15% of Anthropic's count, versus bytes/4
which can be ~2x off on non-ASCII. Good enough to place a heuristic threshold, and
far closer than before, so compression fires near the real limit instead of
prematurely. Falls back to bytes/4 when tiktoken is unavailable or its encoder
can't load, so counting never raises.

The encoder is loaded once and cached (tiktoken downloads/loads the BPE ranks on
first use). Counting is O(text) either way; tiktoken's constant is higher but it
is Rust-backed and comfortably fast for the compression-window check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_BYTES_PER_TOKEN = 4

# Cached encoder: None = tried and unavailable (use fallback); unset sentinel via
# `_encoder_tried`. `Callable[[str], list]`-ish — tiktoken's Encoding.encode.
_encoder: Callable[[str], list[int]] | None = None
_encoder_tried = False


def _bytes_fallback(text: str) -> int:
    return len(text.encode("utf-8")) // _BYTES_PER_TOKEN


def _get_encoder() -> Callable[[str], list[int]] | None:
    global _encoder, _encoder_tried
    if _encoder_tried:
        return _encoder
    _encoder_tried = True
    try:
        import tiktoken

        enc = tiktoken.get_encoding("o200k_base")
        # Disallow special-token handling so arbitrary user text (which may
        # contain the literal "<|endoftext|>") never raises.
        _encoder = lambda t: enc.encode(t, disallowed_special=())  # noqa: E731
    except Exception:
        _encoder = None
    return _encoder


def count_tokens(text: str) -> int:
    """Token count for `text` via tiktoken `o200k_base`, or bytes/4 on fallback.
    Never raises — a broken encoder degrades to the byte heuristic."""
    if not text:
        return 0
    enc = _get_encoder()
    if enc is None:
        return _bytes_fallback(text)
    try:
        return len(enc(text))
    except Exception:
        return _bytes_fallback(text)


def _reset_encoder_cache() -> None:
    """Test helper — clears the memoised encoder probe."""
    global _encoder, _encoder_tried
    _encoder = None
    _encoder_tried = False


__all__ = ["count_tokens"]
