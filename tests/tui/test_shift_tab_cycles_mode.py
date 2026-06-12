"""Shift+Tab cycles the TUI through 4 modes.

The risk being tested: Textual's default `Shift+Tab` binding is
reverse-focus. Our App-level binding uses `priority=True` to claim
the keystroke first. If priority handling regresses, this test goes
red — the mode field won't advance.

We also assert persistence: each cycle writes `tui_state.json` so a
reboot lands on the same mode.
"""

from __future__ import annotations

from veles.core.modes import CYCLE_ORDER
from veles.core.tui_state import load_tui_state
from veles.tui.app import TuiApp
from veles.tui.state import AppState


def _new_app(tmp_project, agent_factory_for, text_response):
    project, store = tmp_project
    return TuiApp(
        state=AppState(
            session_id=None,
            provider_name="openrouter",
            model="m",
        ),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )


async def test_shift_tab_advances_one_step(tmp_project, agent_factory_for, text_response) -> None:
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        assert pilot.app.state.mode == "auto"
        await pilot.press("shift+tab")
        await pilot.pause()
        assert pilot.app.state.mode == "planning"


async def test_shift_tab_cycles_through_all_four_modes(
    tmp_project, agent_factory_for, text_response
) -> None:
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        seen = [pilot.app.state.mode]
        for _ in range(len(CYCLE_ORDER)):
            await pilot.press("shift+tab")
            await pilot.pause()
            seen.append(pilot.app.state.mode)
        # 4 transitions starting from "auto" → planning → writing → goal → auto.
        assert seen == ["auto", "planning", "writing", "goal", "auto"]


async def test_shift_tab_persists_mode_to_disk(
    tmp_project, agent_factory_for, text_response
) -> None:
    project, _ = tmp_project
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        await pilot.press("shift+tab")  # auto → planning
        await pilot.pause()
        await pilot.press("shift+tab")  # planning → writing
        await pilot.pause()
        # In-memory and on-disk must agree after every cycle.
        assert pilot.app.state.mode == "writing"
        assert load_tui_state(project.state_dir).mode == "writing"


async def test_shift_tab_posts_chat_system_line(
    tmp_project, agent_factory_for, text_response
) -> None:
    from veles.tui.widgets.chat_log import ChatLog

    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        await pilot.press("shift+tab")
        await pilot.pause()
        chat = pilot.app.query_one(ChatLog)
        system_lines = [text for role, text in chat.transcript if role == "system"]
        assert any("mode: planning" in line for line in system_lines)


async def test_shift_tab_into_goal_abandons_active_goal(
    tmp_project, agent_factory_for, text_response
) -> None:
    """Per design (interview каждый раз): cycling INTO goal mode when
    an `active_goal_id` is set cancels the stale goal so the FSM
    starts a fresh interview. The cancelled artifact remains on disk
    (`veles goal show <id>` still works); the user just doesn't
    auto-resume it from the TUI."""
    from veles.core.goal import create_goal, read_goal

    project, _ = tmp_project
    stale = create_goal(project.state_dir, objective="old goal", done_condition="")

    app = _new_app(tmp_project, agent_factory_for, text_response)
    app.state.active_goal_id = stale.id
    async with app.run_test() as pilot:
        # auto → planning → writing → goal
        await pilot.press("shift+tab")
        await pilot.pause()
        await pilot.press("shift+tab")
        await pilot.pause()
        await pilot.press("shift+tab")
        await pilot.pause()
        assert pilot.app.state.mode == "goal"
        # Active goal id was cleared so the next turn bootstraps a
        # fresh interview goal.
        assert pilot.app.state.active_goal_id is None
        # The stale goal is now `cancelled` on disk.
        stale_after = read_goal(project.state_dir, stale.id)
        assert stale_after is not None
        assert stale_after.status == "cancelled"
