"""M176 — ChatLog follow-mode: auto-scroll only when at the bottom.

Streaming deltas must not yank the viewport down while the user is scrolled
up reading earlier output; a new user turn (and End) re-arm following.
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from veles.tui.widgets.chat_log import ChatLog


class _ChatHost(App):
    def __init__(self) -> None:
        super().__init__()
        self._log = ChatLog()

    def compose(self) -> ComposeResult:
        yield self._log


async def _fill(log: ChatLog, n: int) -> None:
    """Mount enough messages to overflow a short viewport so it can scroll."""
    for i in range(n):
        log.append_system(f"line {i} — some filler text to take vertical space")


async def test_follow_when_at_bottom():
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        await _fill(log, 30)
        log.scroll_end(animate=False)
        await pilot.pause()
        assert log.max_scroll_y > 0  # content overflows → scrollable
        # A new streamed delta while pinned to the bottom keeps us at bottom.
        log.start_assistant()
        log.append_assistant_delta("fresh assistant output line")
        await pilot.pause()
        assert log.scroll_offset.y >= log.max_scroll_y - 1


async def test_no_follow_when_scrolled_up():
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        await _fill(log, 30)
        log.scroll_home(animate=False)  # user scrolls up to the very top
        await pilot.pause()
        assert log.scroll_offset.y == 0
        # New output must NOT drag the viewport down — stays at the top.
        log.append_system("a late system message")
        log.start_assistant()
        log.append_assistant_delta("late assistant delta")
        await pilot.pause()
        assert log.scroll_offset.y == 0


async def test_new_user_turn_rearms_follow():
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        await _fill(log, 30)
        log.scroll_home(animate=False)
        await pilot.pause()
        assert log.scroll_offset.y == 0
        # Sending a new prompt jumps back to the bottom to watch the reply.
        log.append_user("what's next?")
        await pilot.pause()
        assert log.scroll_offset.y >= log.max_scroll_y - 1


async def test_scroll_to_bottom_rearms_follow():
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        await _fill(log, 30)
        log.scroll_home(animate=False)
        await pilot.pause()
        assert log.scroll_offset.y == 0
        log.scroll_to_bottom()
        await pilot.pause()
        # Re-armed: viewport is pinned to the bottom and `_at_bottom()` (the
        # follow predicate) reports True, so subsequent deltas will follow.
        assert log.scroll_offset.y >= log.max_scroll_y - 1
        assert log._at_bottom()
