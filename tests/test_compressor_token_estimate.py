"""Token estimation must count UTF-8 bytes, not characters.

Cyrillic (and other non-ASCII) text is ~2 UTF-8 bytes per character and
tokenises to roughly that many tokens — but `len(str)` counts one per char, so a
chars/4 estimate undercounts it ~2x. That let the compressor hand the summariser
a "150k-token" middle that was really ~267k tokens, overflowing the model's 262k
window with a 400 (the reported "compressor summariser-failed").
"""

from __future__ import annotations

from veles.core.context_compressor import estimate_tokens
from veles.core.provider import Message


def test_ascii_estimate_is_bytes_over_4() -> None:
    # 400 ASCII bytes → 100 tokens (unchanged from the char heuristic).
    assert estimate_tokens([Message(role="user", content="a" * 400)]) == 100


def test_cyrillic_counts_two_bytes_per_char() -> None:
    # 400 Cyrillic chars = 800 UTF-8 bytes → 200 tokens, NOT 100. Undercounting
    # this is what overflowed the summariser.
    assert estimate_tokens([Message(role="user", content="я" * 400)]) == 200
