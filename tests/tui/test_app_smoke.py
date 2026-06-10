"""Phase 1 smoke: a TuiApp boots, a turn streams text into ChatLog, the
status bar reflects busy/idle transitions, and the app exits cleanly.

Coverage limited on purpose — slash commands, themes, pickers, inspector
all live in later phases. The intent here is to nail down the contract
between bridge, app, and widgets so future phases plug in without
rewiring the foundation.

Both ChatLog and StatusBar expose plain-text mirrors of what they
rendered (`transcript`, `last_text`) so assertions don't depend on
Textual's internal renderable shape, which churns across releases.
"""

from __future__ import annotations

import pytest

from veles.tui.app import TuiApp
from veles.tui.state import AppState
from veles.tui.widgets.chat_log import ChatLog
from veles.tui.widgets.composer import Composer
from veles.tui.widgets.status_bar import StatusBar


def _state() -> AppState:
    return AppState(session_id=None, provider_name="stub", model="m")


async def _settle(pilot, *, predicate, ticks: int = 80) -> None:
    """Pump the event loop until `predicate(pilot)` holds or `ticks`
    elapse. Centralized so individual tests don't grow ad-hoc loops."""
    for _ in range(ticks):
        await pilot.pause()
        if predicate(pilot):
            return
    pytest.fail("timed out waiting for predicate")


async def test_app_boots_and_mounts_widgets(agent_factory_for, text_response):
    app = TuiApp(state=_state(), agent_factory=agent_factory_for(text_response("hi")))
    async with app.run_test() as pilot:
        assert pilot.app.query_one(ChatLog) is not None
        assert pilot.app.query_one(Composer) is not None
        status = pilot.app.query_one(StatusBar)
        assert "session new" in status.last_text
        assert "stub/m" in status.last_text


async def test_user_prompt_streams_to_chat_log(agent_factory_for, text_response):
    app = TuiApp(state=_state(), agent_factory=agent_factory_for(text_response("hello world")))
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.text = "ping"
        await pilot.press("enter")
        await _settle(pilot, predicate=lambda p: not p.app.state.busy)

        chat = pilot.app.query_one(ChatLog)
        assert ("user", "ping") in chat.transcript
        assistants = [text for role, text in chat.transcript if role == "assistant"]
        assert assistants and assistants[-1] == "hello world"


async def test_status_bar_reflects_idle_after_turn(agent_factory_for, text_response):
    """After a turn settles, status bar must not advertise busy and the
    state machine must be idle. The intermediate `busy=True` window is
    covered by `test_second_prompt_while_busy_queues` — queueing is only
    possible when busy is set, so the queue test exercises that state."""
    app = TuiApp(state=_state(), agent_factory=agent_factory_for(text_response("ok")))
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.text = "go"
        await pilot.press("enter")
        await _settle(pilot, predicate=lambda p: not p.app.state.busy)
        status = pilot.app.query_one(StatusBar)
        assert "busy" not in status.last_text
        assert not pilot.app.state.busy
        assert not pilot.app.state.queue


async def test_quit_slash_exits_cleanly(agent_factory_for, text_response):
    app = TuiApp(state=_state(), agent_factory=agent_factory_for(text_response("unused")))
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.text = "/quit"
        await pilot.press("enter")
        await pilot.pause()
    assert app.return_value == 0


async def test_second_prompt_while_busy_queues(agent_factory_for, text_response):
    app = TuiApp(
        state=_state(),
        agent_factory=agent_factory_for(text_response("first"), text_response("second")),
    )
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.text = "a"
        await pilot.press("enter")
        composer.text = "b"
        await pilot.press("enter")
        await _settle(
            pilot,
            predicate=lambda p: not p.app.state.busy and not p.app.state.queue,
            ticks=160,
        )

        chat = pilot.app.query_one(ChatLog)
        # Two user prompts, two assistant replies, in order.
        roles = [role for role, _ in chat.transcript]
        assert roles == ["user", "assistant", "user", "assistant"]
        texts = [text for _, text in chat.transcript]
        assert texts == ["a", "first", "b", "second"]
