"""Unit tests for `_tool_namespace.qualify_prompt`."""

from __future__ import annotations

from veles.adapters.cli._tool_namespace import (
    claude_mcp_prefix,
    gemini_mcp_prefix,
    mcp_prefix,
    qualify_prompt,
)


def test_mcp_prefix_format() -> None:
    assert mcp_prefix("wiki_write_page") == "mcp__veles__wiki_write_page"
    assert mcp_prefix("read_file") == "mcp__veles__read_file"


def test_qualify_prompt_rewrites_known_names() -> None:
    prompt = "Call wiki_write_page(category, slug). Then call read_file(path)."
    out = qualify_prompt(prompt, ["wiki_write_page", "read_file"])
    assert "mcp__veles__wiki_write_page(category, slug)" in out
    assert "mcp__veles__read_file(path)" in out
    assert "wiki_write_page(" not in out.replace("mcp__veles__wiki_write_page(", "")


def test_qualify_prompt_idempotent() -> None:
    prompt = "Use wiki_search to find pages."
    once = qualify_prompt(prompt, ["wiki_search"])
    twice = qualify_prompt(once, ["wiki_search"])
    assert once == twice
    assert "mcp__veles__mcp__veles__" not in twice


def test_qualify_prompt_word_boundary_no_substring_match() -> None:
    prompt = "Note: wiki_list_pages_extended is a synthetic name."
    out = qualify_prompt(prompt, ["wiki_list_pages"])
    assert "mcp__veles__wiki_list_pages" not in out
    assert "wiki_list_pages_extended" in out


def test_qualify_prompt_skips_unknown_names() -> None:
    prompt = "Use unknown_tool and wiki_search."
    out = qualify_prompt(prompt, ["wiki_search"])
    assert "unknown_tool" in out
    assert "mcp__veles__unknown_tool" not in out
    assert "mcp__veles__wiki_search" in out


def test_qualify_prompt_overlapping_names_longest_first() -> None:
    prompt = "Try foo and foo_bar in sequence."
    out = qualify_prompt(prompt, ["foo", "foo_bar"])
    assert "mcp__veles__foo_bar" in out
    assert "mcp__veles__foo " in out  # standalone foo also rewritten
    assert "mcp__veles__mcp__veles__" not in out


def test_gemini_mcp_prefix_format() -> None:
    assert gemini_mcp_prefix("wiki_write_page") == "mcp_veles_wiki_write_page"
    assert gemini_mcp_prefix("read_file") == "mcp_veles_read_file"


def test_claude_mcp_prefix_alias_matches_legacy_mcp_prefix() -> None:
    assert claude_mcp_prefix("read_file") == mcp_prefix("read_file")


def test_qualify_prompt_with_gemini_prefix_fn() -> None:
    prompt = "Call wiki_write_page(category, slug)."
    out = qualify_prompt(prompt, ["wiki_write_page"], prefix_fn=gemini_mcp_prefix)
    assert "mcp_veles_wiki_write_page(category, slug)" in out
    assert "mcp__veles__wiki_write_page" not in out
