"""M179 — read mode: focus toggle between the Composer and the ChatLog.

PageUp moves keyboard focus into the output pane (so the arrow keys navigate
it); Escape / Ctrl+End hand focus back to the input.
"""

from __future__ import annotations

from veles.tui.app import TuiApp
from veles.tui.state import AppState


def _new_app(tmp_project, agent_factory_for, text_response):
    project, store = tmp_project
    return TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )


async def test_ctrl_o_toggles_focus_between_panes(
    tmp_project, agent_factory_for, text_response
) -> None:
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        # Boot: input focused.
        assert pilot.app._composer.has_focus
        await pilot.press("ctrl+o")
        await pilot.pause()
        # Into read mode: output pane focused, follow paused.
        assert pilot.app._chat.has_focus
        assert not pilot.app._chat.following
        await pilot.press("ctrl+o")
        await pilot.pause()
        # Back to the input.
        assert pilot.app._composer.has_focus
        assert not pilot.app._chat.has_focus


async def test_pageup_focuses_chat_and_pauses_follow(
    tmp_project, agent_factory_for, text_response
) -> None:
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        # Composer holds focus at boot; the chat is following.
        assert not pilot.app._chat.has_focus
        assert pilot.app._chat.following
        await pilot.press("pageup")
        await pilot.pause()
        # Read mode: chat pane focused, auto-follow paused.
        assert pilot.app._chat.has_focus
        assert not pilot.app._chat.following


async def test_escape_returns_focus_to_composer(
    tmp_project, agent_factory_for, text_response
) -> None:
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        await pilot.press("pageup")
        await pilot.pause()
        assert pilot.app._chat.has_focus
        await pilot.press("escape")
        await pilot.pause()
        assert pilot.app._composer.has_focus
        assert not pilot.app._chat.has_focus


async def test_ctrl_end_returns_to_composer_and_rearms_follow(
    tmp_project, agent_factory_for, text_response
) -> None:
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        await pilot.press("pageup")
        await pilot.pause()
        assert not pilot.app._chat.following  # paused on enter
        await pilot.press("ctrl+end")
        await pilot.pause()
        assert pilot.app._composer.has_focus
        assert pilot.app._chat.following  # re-armed at the bottom
