"""M176 — ChatLog follow-mode: auto-scroll only while following is armed.

Follow-mode is a boolean flag (deterministic), not a geometry check: the
user turns it off by scrolling up and back on via End / a new turn. Tests
assert the flag transitions and whether `scroll_end` is invoked, rather than
exact scroll offsets (which lag content growth by a few lines mid-stream and
flake across machines).
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


def _spy_scroll_end(log: ChatLog) -> list[int]:
    calls: list[int] = []
    orig = log.scroll_end

    def wrapper(*args, **kwargs):
        calls.append(1)
        return orig(*args, **kwargs)

    log.scroll_end = wrapper  # type: ignore[method-assign]
    return calls


async def test_delta_follows_when_armed():
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        assert log.following  # armed by default
        calls = _spy_scroll_end(log)
        log.start_assistant()
        log.append_assistant_delta("fresh output")
        await pilot.pause()
        assert calls  # followed → scroll_end invoked


async def test_delta_does_not_follow_when_paused():
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        log.pause_follow()
        assert not log.following
        calls = _spy_scroll_end(log)
        log.start_assistant()
        log.append_assistant_delta("late output")
        log.append_system("a system line")
        await pilot.pause()
        assert not calls  # paused → no auto-scroll


async def test_new_user_turn_rearms_follow():
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        log.pause_follow()
        assert not log.following
        log.append_user("what's next?")
        await pilot.pause()
        assert log.following  # a new turn re-arms following


async def test_scroll_to_bottom_rearms_follow():
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        log.pause_follow()
        assert not log.following
        log.scroll_to_bottom()
        await pilot.pause()
        assert log.following


async def test_mouse_wheel_up_pauses_follow():
    """Wheel-up (mouse-reporting is on by default since M182) stops
    auto-following so streaming doesn't drag the view while reading."""
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        assert log.following
        log.on_mouse_scroll_up(object())  # handler ignores the event payload
        assert not log.following


async def test_mouse_wheel_down_at_bottom_rearms_follow():
    """M182: with keyboard scrolling gone, wheel-down back to the bottom is
    how the user resumes auto-follow. `_rearm_if_at_bottom` re-arms once the
    view is at (within one row of) the bottom."""
    app = _ChatHost()
    async with app.run_test(size=(40, 6)) as pilot:
        log = pilot.app.query_one(ChatLog)
        log.pause_follow()
        assert not log.following
        # No scrollback content → already at the bottom → re-arm fires.
        log._rearm_if_at_bottom()
        assert log.following
