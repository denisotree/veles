"""Markdown → Telegram-HTML conversion."""

from __future__ import annotations

from veles.channels.telegram_format import (
    escape_html,
    html_safe_truncate,
    markdown_to_telegram_html,
)

# ---- escape_html ----


def test_escape_html_replaces_three_special_chars() -> None:
    assert escape_html("a < b & c > d") == "a &lt; b &amp; c &gt; d"


def test_escape_html_preserves_plain_text() -> None:
    assert escape_html("hello world") == "hello world"
    assert escape_html("") == ""


def test_escape_html_ampersand_first() -> None:
    """Naïve order (`<` before `&`) double-encodes the entities the lt
    rule emits. We escape `&` first; the resulting entity stays intact."""
    assert escape_html("<&>") == "&lt;&amp;&gt;"


# ---- markdown_to_telegram_html ----


def test_md_bold_and_italic() -> None:
    out = markdown_to_telegram_html("This **bold** and *italic*.")
    assert "<b>bold</b>" in out
    assert "<i>italic</i>" in out


def test_md_inline_code() -> None:
    out = markdown_to_telegram_html("call `foo()` to start")
    assert "<code>foo()</code>" in out


def test_md_headings_become_bold() -> None:
    """Telegram has no <h1>/<h2>; collapse to bold so the section
    label stays visible without showing a literal `#`."""
    out = markdown_to_telegram_html("# Title\n## Section\n### Sub")
    assert "<b>Title</b>" in out
    assert "<b>Section</b>" in out
    assert "<b>Sub</b>" in out
    assert "#" not in out


def test_md_fenced_code_with_language() -> None:
    out = markdown_to_telegram_html("```python\nprint(1)\n```")
    assert '<pre><code class="language-python">print(1)</code></pre>' in out


def test_md_fenced_code_without_language() -> None:
    out = markdown_to_telegram_html("```\nplain\n```")
    assert "<pre>plain</pre>" in out


def test_md_unordered_list() -> None:
    out = markdown_to_telegram_html("- one\n- two\n- three")
    assert "• one" in out
    assert "• two" in out
    assert "• three" in out


def test_md_ordered_list() -> None:
    out = markdown_to_telegram_html("1. first\n2. second\n3. third")
    assert "1. first" in out
    assert "2. second" in out
    assert "3. third" in out


def test_md_link_http_renders_anchor() -> None:
    out = markdown_to_telegram_html("see [docs](https://example.com)")
    assert '<a href="https://example.com">docs</a>' in out


def test_md_link_unsafe_scheme_stripped_keeps_text() -> None:
    """`javascript:` and friends must never leave the converter as a
    live link; the text content survives, the href is dropped."""
    out = markdown_to_telegram_html("[evil](javascript:alert(1))")
    assert "<a " not in out
    assert "evil" in out


def test_md_blockquote() -> None:
    out = markdown_to_telegram_html("> quoted line")
    assert "<blockquote>" in out
    assert "quoted line" in out
    assert "</blockquote>" in out


def test_md_table_collapses_to_pre_block() -> None:
    md = "| a | b |\n|---|---|\n| 1 | 2 |"
    out = markdown_to_telegram_html(md)
    assert "<pre>" in out and "</pre>" in out
    # Cell values present in the pre-block.
    assert "a" in out and "b" in out and "1" in out and "2" in out


def test_md_text_with_angle_brackets_is_escaped() -> None:
    """User-supplied `<script>` mustn't become a tag — Telegram would
    reject it AND it's the textbook XSS vector."""
    out = markdown_to_telegram_html("plain <script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_md_unclosed_bold_does_not_crash() -> None:
    """LLM sometimes emits half-formatted Markdown. The converter must
    survive and render something sensible (treats as plain text)."""
    out = markdown_to_telegram_html("**oh no I forgot to close")
    assert "oh no I forgot to close" in out
    assert "<b>" not in out  # CommonMark refuses to open a span


def test_md_empty_input() -> None:
    assert markdown_to_telegram_html("") == ""


def test_md_hr_renders_visible_separator() -> None:
    out = markdown_to_telegram_html("above\n\n---\n\nbelow")
    assert "──────────" in out


# ---- html_safe_truncate ----


def test_truncate_noop_below_limit() -> None:
    s = "short"
    assert html_safe_truncate(s, limit=100) == s


def test_truncate_closes_open_bold() -> None:
    """Cut inside `<b>...</b>` must close the tag — leaving it open
    breaks the entire message in Telegram's parser."""
    s = "prefix <b>" + "x" * 100 + "</b> tail"
    out = html_safe_truncate(s, limit=30)
    assert out.endswith("</b>")
    assert out.startswith("prefix <b>")
    assert len(out) <= 30


def test_truncate_drops_partial_entity() -> None:
    """When the cut lands inside an entity (`&am|p;`), we want to drop
    the unfinished `&am` rather than emit it as literal characters."""
    s = "abcde&amp;extra-tail-to-overflow-the-limit"
    out = html_safe_truncate(s, limit=8)
    # The `&am` at the cut boundary is dropped before truncation runs.
    assert "&am" not in out
    assert out.startswith("abcde")


def test_truncate_handles_nested_tags() -> None:
    s = "<b><i>" + "y" * 100 + "</i></b>"
    out = html_safe_truncate(s, limit=20)
    # Close in reverse order: …</i></b>
    assert out.endswith("</i></b>")
