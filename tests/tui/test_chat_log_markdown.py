"""ChatLog seals assistant replies into a selectable Markdown widget.

Streaming keeps a plain-text Static for cheap per-delta updates; on
`seal_assistant` it is replaced by a Textual `Markdown` *widget* so tables,
code blocks, and `diff` chunks render — and, crucially (M183b), the final
reply stays mouse-selectable (a Static carrying a `rich.markdown.Markdown`
renderable rendered fine but Textual's selection could not extract its text).
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static

from veles.tui.widgets.chat_log import AssistantMarkdown, ChatLog


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
        return log.children[-1]


async def test_sealed_assistant_is_a_markdown_widget():
    sealed = await _seal_with("# Heading\n\n| col | val |\n|-----|-----|\n| a   | 1   |\n")
    assert isinstance(sealed, AssistantMarkdown)


async def test_streaming_text_stays_plain_static_until_seal():
    """Mid-stream the last child is a plain-text Static (heavy markdown
    re-layout per delta would stutter), not a Markdown widget."""
    app = _ChatHost()
    async with app.run_test() as pilot:
        log = pilot.app.query_one(ChatLog)
        log.start_assistant()
        log.append_assistant_delta("# Hello\n\nworld")
        await pilot.pause()
        streaming = log.children[-1]
        assert isinstance(streaming, Static)
        assert not isinstance(streaming, AssistantMarkdown)
        assert isinstance(_content(streaming), str)


async def test_sealed_markdown_is_selectable():
    """The regression guard for M183b: the sealed reply's text can be
    extracted by Textual's selection (so drag-select + Ctrl+C can copy it)."""
    app = _ChatHost()
    async with app.run_test(size=(80, 24)) as pilot:
        log = pilot.app.query_one(ChatLog)
        log.start_assistant()
        log.append_assistant_delta("a unique selectable phrase")
        log.seal_assistant()
        await pilot.pause()
        pilot.app.screen.text_select_all()
        await pilot.pause()
        selected = pilot.app.screen.get_selected_text() or ""
        assert "a unique selectable phrase" in selected


async def test_diff_block_rides_through_markdown():
    body = "```diff\n- old\n+ new\n```\n"
    sealed = await _seal_with(body)
    assert isinstance(sealed, AssistantMarkdown)
    # The Markdown widget keeps the original source.
    assert "diff" in sealed.source


async def test_seal_with_empty_buffer_keeps_placeholder_static():
    """If the assistant produced nothing, don't mount a Markdown widget;
    the placeholder streaming Static stays as-is."""
    app = _ChatHost()
    async with app.run_test() as pilot:
        log = pilot.app.query_one(ChatLog)
        log.start_assistant()
        log.seal_assistant()
        await pilot.pause()
        last = log.children[-1]
        assert not isinstance(last, AssistantMarkdown)
        assert isinstance(last, Static)
