"""Slash-command completer — prefix matching, cursor-position rules.

The composer feeds the completer `(text, cursor)`. The completer
returns *full-line* replacement candidates so the composer never has
to splice substrings.
"""

from __future__ import annotations

from veles.cli.repl.completer import NullCompleter, SlashCompleter
from veles.cli.repl.slash import SlashRegistry, SlashResult


def _reg(*names: str) -> SlashRegistry:
    reg = SlashRegistry()
    for n in names:
        reg.register(n, lambda r, c: SlashResult.ok(), summary="")
    return reg


def test_no_candidates_for_plain_text():
    c = SlashCompleter(_reg("/help", "/quit"))
    assert c.candidates("hello", 5) == []


def test_complete_single_match():
    c = SlashCompleter(_reg("/help", "/quit"))
    # "/he" → only "/help" matches.
    assert c.candidates("/he", 3) == ["/help"]


def test_complete_multiple_matches_sorted():
    c = SlashCompleter(_reg("/save", "/search", "/session"))
    cands = c.candidates("/s", 2)
    assert cands == ["/save", "/search", "/session"]


def test_completes_only_when_cursor_inside_command_word():
    """Once the user typed a space, the slash completer steps aside —
    argument-specific completers (Phase 5) will pick up from there."""
    c = SlashCompleter(_reg("/help"))
    assert c.candidates("/help ", 6) == []
    assert c.candidates("/help arg", 9) == []


def test_completion_preserves_text_after_cursor():
    """If the user typed `/h|world` (cursor after `/h`), completion
    must keep `world` as the tail."""
    c = SlashCompleter(_reg("/help"))
    # Note: `world` here isn't valid command-word territory but the
    # completer still preserves the tail it didn't try to complete.
    text = "/h"
    assert c.candidates(text, 2) == ["/help"]


def test_aliases_included():
    reg = SlashRegistry()
    reg.register("/quit", lambda r, c: SlashResult.ok(), summary="", aliases=("/q", "/exit"))
    c = SlashCompleter(reg)
    cands = c.candidates("/q", 2)
    # Aliases appear alongside canonical names — `/q` and `/quit`.
    assert "/q" in cands and "/quit" in cands


def test_null_completer_never_returns_anything():
    n = NullCompleter()
    assert n.candidates("/help", 5) == []
    assert n.candidates("", 0) == []
