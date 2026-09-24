"""Shared text shaping (`core/text.py`)."""

from __future__ import annotations

from veles.core.text import (
    cut_with_note,
    ellipsize,
    first_heading,
    strip_code_fence,
    title_and_summary,
)


def test_ellipsize_flattens_and_caps() -> None:
    assert ellipsize("  a\nb  ", 10) == "a b"
    assert ellipsize("abcdefghij", 5) == "abcd…"


def test_cut_with_note_keeps_the_total_within_the_cap() -> None:
    assert cut_with_note("short", 10, "!") == "short"
    out = cut_with_note("x" * 50, 20, "<cut>")
    assert out.endswith("<cut>") and len(out) == 20


def test_strip_code_fence_variants() -> None:
    assert strip_code_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_code_fence('```json {"a": 1}```') == '{"a": 1}'
    assert strip_code_fence('{"a": 1}') == '{"a": 1}'


def test_first_heading_and_title_summary() -> None:
    assert first_heading("\n## Two\nbody") == "Two"
    assert first_heading("plain line") == "plain line"
    title, summary = title_and_summary("# T\n\nfirst para\nsecond line\n\n## H\nx", "fb")
    assert (title, summary) == ("T", "first para second line")
    assert title_and_summary("no heading", "fb")[0] == "fb"
