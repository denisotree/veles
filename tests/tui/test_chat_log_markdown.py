"""ChatLog renders assistant replies as Markdown after seal.

Streaming keeps plain text for cheap per-delta updates; on `seal_assistant`
the accumulated buffer is re-rendered through `rich.markdown.Markdown`
so tables, code blocks, and `diff` chunks land properly formatted.
"""

from __future__ import annotations

from rich.markdown import Markdown
from textual.app import App, ComposeResult

from veles.tui.widgets.chat_log import ChatLog


class _ChatHost(App):
    def __init__(self) -> None:
        super().__init__()
        self._log = ChatLog()

    def compose(self) -> ComposeResult:
        yield self._log


def _content(static):
    """Static stores its renderable on a name-mangled `__content` attr."""
    return static._Static__content


async def _seal_with(text: str):
    app = _ChatHost()
    async with app.run_test() as pilot:
        log = pilot.app.query_one(ChatLog)
        log.start_assistant()
        log.append_assistant_delta(text)
        log.seal_assistant()
        await pilot.pause()
        sealed = log.children[-1]
        return sealed


async def test_sealed_assistant_renders_through_markdown():
    sealed = await _seal_with("# Heading\n\n| col | val |\n|-----|-----|\n| a   | 1   |\n")
    # The Static's renderable is now a Rich Markdown instance, not a string.
    assert isinstance(_content(sealed), Markdown)


async def test_streaming_text_stays_plain_until_seal():
    """Mid-stream the renderable must NOT be a Markdown instance (heavy
    re-layout per delta would stutter)."""
    app = _ChatHost()
    async with app.run_test() as pilot:
        log = pilot.app.query_one(ChatLog)
        log.start_assistant()
        log.append_assistant_delta("# Hello\n\nworld")
        await pilot.pause()
        streaming = log.children[-1]
        # While streaming, the Static carries a plain str renderable.
        assert not isinstance(_content(streaming), Markdown)


async def test_diff_block_uses_markdown_render():
    """Diff fenced code blocks ride through Markdown → Pygments lexer, so
    we just verify the Markdown instance wraps the original text."""
    body = "```diff\n- old\n+ new\n```\n"
    sealed = await _seal_with(body)
    content = _content(sealed)
    assert isinstance(content, Markdown)
    # The source markdown is preserved on the Markdown object.
    assert "diff" in content.markup


async def test_seal_with_empty_buffer_does_not_replace_renderable():
    """If the assistant produced nothing (empty stream + seal), don't try
    to render Markdown(""); the placeholder Static stays as-is."""
    app = _ChatHost()
    async with app.run_test() as pilot:
        log = pilot.app.query_one(ChatLog)
        log.start_assistant()
        log.seal_assistant()
        await pilot.pause()
        last = log.children[-1]
        assert not isinstance(_content(last), Markdown)
