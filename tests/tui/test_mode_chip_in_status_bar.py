"""Status-bar mode chip — visible at all times, updates on cycle.

The chip is the user's primary visual anchor for "what mode am I in
right now". It must render for every mode value, sit at the front of
the status line, and update after `Shift+Tab`.
"""

from __future__ import annotations

import pytest

from veles.core.session_state import AppState
from veles.tui.widgets.status_bar import StatusBar


def _state(mode: str) -> AppState:
    return AppState(
        session_id=None,
        provider_name="openrouter",
        model="m",
        mode=mode,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("mode", ["auto", "planning", "writing", "goal"])
def test_status_bar_renders_mode_chip(mode: str) -> None:
    bar = StatusBar()
    bar.render_state(_state(mode))
    assert f"[{mode}]" in bar.last_text


def test_status_bar_chip_sits_before_session_marker() -> None:
    """The chip is the first segment so it stays in the user's
    peripheral vision even when long session ids push the rest off
    screen."""
    bar = StatusBar()
    bar.render_state(_state("planning"))
    chip_at = bar.last_text.find("[planning]")
    session_at = bar.last_text.find("session ")
    assert chip_at != -1 and session_at != -1
    assert chip_at < session_at


async def test_status_bar_updates_after_shift_tab(
    tmp_project, agent_factory_for, text_response
) -> None:
    from veles.tui.app import TuiApp

    project, store = tmp_project
    app = TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )
    async with app.run_test() as pilot:
        bar = pilot.app.query_one(StatusBar)
        assert "[auto]" in bar.last_text
        await pilot.press("shift+tab")
        await pilot.pause()
        assert "[planning]" in bar.last_text
