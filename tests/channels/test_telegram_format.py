"""Markdown → Telegram-HTML conversion."""

from __future__ import annotations

from veles.channels.telegram_format import (
    escape_html,
    markdown_to_telegram_html,
    split_telegram_html,
)


def _entities_intact(chunk: str) -> bool:
    """Every `&` in the chunk begins a complete `&...;` entity."""
    i = 0
    while True:
        i = chunk.find("&", i)
        if i < 0:
            return True
        semi = chunk.find(";", i, i + 12)
        if semi < 0:
            return False
        i = semi + 1


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


def test_md_strikethrough() -> None:
    """`~~x~~` must reach Telegram as <s> — the commonmark preset leaves
    the rule off, so it's enabled explicitly on the parser."""
    out = markdown_to_telegram_html("this is ~~gone~~ now")
    assert "<s>gone</s>" in out


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


# ---- split_telegram_html ----


def test_split_noop_below_limit() -> None:
    s = "short enough to send in one message"
    assert split_telegram_html(s, limit=4096) == [s]


def test_split_each_chunk_within_limit() -> None:
    s = "word " * 2000  # 10000 chars of plain text
    chunks = split_telegram_html(s, limit=4000)
    assert len(chunks) >= 3
    assert all(len(c) <= 4000 for c in chunks)


def test_split_preserves_all_text() -> None:
    """No characters lost across the split (plain text, no tags)."""
    s = "".join(f"line{i} " for i in range(2000))
    chunks = split_telegram_html(s, limit=4000)
    assert "".join(chunks).replace(" ", "") == s.replace(" ", "")


def test_split_closes_and_reopens_tags() -> None:
    """A `<b>` spanning the boundary is closed at the end of one chunk
    and reopened at the start of the next, so each chunk is valid on its
    own and the bold formatting continues visually."""
    s = "<b>" + "x" * 6000 + "</b>"
    chunks = split_telegram_html(s, limit=4000)
    assert len(chunks) >= 2
    assert all(len(c) <= 4000 for c in chunks)
    assert chunks[0].startswith("<b>") and chunks[0].endswith("</b>")
    assert chunks[1].startswith("<b>")
    total_x = sum(c.count("x") for c in chunks)
    assert total_x == 6000


def test_split_never_breaks_entity() -> None:
    s = "&amp; " * 1200  # ~7200 chars, entities dense near boundaries
    chunks = split_telegram_html(s, limit=4000)
    assert len(chunks) >= 2
    assert all(_entities_intact(c) for c in chunks)


def test_split_nested_tags_reopen_in_order() -> None:
    s = "<b><i>" + "z" * 6000 + "</i></b>"
    chunks = split_telegram_html(s, limit=4000)
    assert chunks[0].endswith("</i></b>")
    assert chunks[1].startswith("<b><i>")
