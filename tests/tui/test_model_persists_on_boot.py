"""M81: model selection persists across TUI restarts.

After the user picks a model (either via `/model <id>` or the picker)
the choice is written to `<project>/.veles/tui_state.json` and the next
TUI boot honours it unless `--model` is explicitly passed on the
command line.
"""

from __future__ import annotations

from veles.core.tui_state import (
    TuiPersistentState,
    load_tui_state,
    save_tui_state,
)
from veles.tui.app import TuiApp
from veles.tui.state import AppState
from veles.tui.widgets.composer import Composer


def test_persisted_state_includes_model(tmp_project) -> None:
    project, _ = tmp_project
    save_tui_state(
        project.state_dir,
        TuiPersistentState(mode="planning", model="openai/gpt-4o"),
    )
    reloaded = load_tui_state(project.state_dir)
    assert reloaded.model == "openai/gpt-4o"
    assert reloaded.mode == "planning"


def test_load_drops_invalid_model_type(tmp_project) -> None:
    import json

    from veles.core.tui_state import tui_state_path

    project, _ = tmp_project
    tui_state_path(project.state_dir).parent.mkdir(parents=True, exist_ok=True)
    tui_state_path(project.state_dir).write_text(
        json.dumps({"version": 1, "mode": "auto", "model": 42}),
        encoding="utf-8",
    )
    state = load_tui_state(project.state_dir)
    assert state.model is None


async def test_slash_model_set_persists_to_disk(
    tmp_project, agent_factory_for, text_response
) -> None:
    """`/model openai/gpt-4o` typed in the TUI persists the choice so
    the next boot reads it back."""
    project, store = tmp_project
    app = TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "/model openai/gpt-4o"
        await pilot.press("enter")
        await pilot.pause()
    reloaded = load_tui_state(project.state_dir)
    assert reloaded.model == "openai/gpt-4o"


async def test_picker_selection_persists_to_disk(
    tmp_project, agent_factory_for, text_response
) -> None:
    """Choosing a model via the picker (Ctrl+nothing — opened via /model)
    persists the choice. The first item of the openrouter list is taken."""
    from veles.tui.screens.model_picker import known_models

    project, store = tmp_project
    app = TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "/model"
        await pilot.press("enter")
        await pilot.pause()
        # Enter on the picker picks the first highlighted row (M81: cursor
        # starts on row 0 so no extra Down keypress is needed).
        await pilot.press("enter")
        await pilot.pause()
    expected = known_models("openrouter")[0]
    reloaded = load_tui_state(project.state_dir)
    assert reloaded.model == expected


async def test_picker_arrow_keys_work_without_tab(
    tmp_project, agent_factory_for, text_response
) -> None:
    """M81: opening the picker should land focus on the ListView so Up/Down
    work immediately — no extra Tab press. Pressing Down then Enter must
    pick the *second* row."""
    from veles.tui.screens.model_picker import known_models

    project, store = tmp_project
    app = TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "/model"
        await pilot.press("enter")
        await pilot.pause()
        # Down → second row highlighted. Without the M81 fix focus would
        # be on the filter Input and Down would do nothing useful.
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
    expected = known_models("openrouter")[1]
    assert app.state.model == expected


async def test_picker_typing_filters_without_tab(
    tmp_project, agent_factory_for, text_response
) -> None:
    """M81: typing a printable char while ListView has focus should forward
    the keystroke to the hidden filter input — the list shrinks immediately."""
    project, store = tmp_project
    app = TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "/model"
        await pilot.press("enter")
        await pilot.pause()
        # Type "ant" — should filter the list to anthropic/* entries.
        await pilot.press("a", "n", "t")
        await pilot.pause()
        screen = pilot.app.screen
        labels = screen.visible_labels  # type: ignore[attr-defined]
        assert labels, "expected at least one match for 'ant'"
        for label in labels:
            assert "ant" in label.lower(), label


# ---- project-config mirror (resolver-cascade fix) ----
#
# `core.model_resolver.resolve_effective_model` puts
# `<project>/.veles/config.toml [engine] model` ABOVE tui_state.json. If
# the wizard wrote a model there, writing only tui_state.json on `/model X`
# would silently lose the user's pick on next boot. `persist_model_choice`
# mirrors the value into project config so the cascade picks the latest
# interactive choice. These tests pin that behaviour.


def test_persist_model_choice_writes_project_config(tmp_project) -> None:
    from veles.core.project_config import load_project_config
    from veles.core.tui_state import persist_model_choice

    project, _ = tmp_project
    persist_model_choice(project, "openai/gpt-4o")
    cfg = load_project_config(project)
    assert cfg.get("engine", {}).get("model") == "openai/gpt-4o"


def test_persist_model_choice_preserves_other_keys(tmp_project) -> None:
    """Pre-seed config with unrelated sections + a provider default; the
    helper must keep them intact while overwriting only `[engine] model`."""
    from veles.core.project_config import load_project_config, save_project_config
    from veles.core.tui_state import persist_model_choice

    project, _ = tmp_project
    save_project_config(
        project,
        {
            "engine": {"provider": "openrouter", "model": "old-model"},
            "daemon": {"enabled": True, "port": 8765},
        },
    )
    persist_model_choice(project, "anthropic/claude-3.7-sonnet")
    cfg = load_project_config(project)
    assert cfg["engine"]["model"] == "anthropic/claude-3.7-sonnet"
    assert cfg["engine"]["provider"] == "openrouter"
    assert cfg["daemon"] == {"enabled": True, "port": 8765}


def test_persist_model_choice_also_updates_tui_state(tmp_project) -> None:
    """Both surfaces stay in sync — tui_state.json keeps its role as a
    fallback when project config doesn't exist yet."""
    from veles.core.tui_state import (
        TuiPersistentState,
        load_tui_state,
        persist_model_choice,
        save_tui_state,
    )

    project, _ = tmp_project
    save_tui_state(project.state_dir, TuiPersistentState(mode="planning"))
    persist_model_choice(project, "openai/gpt-4o")
    reloaded = load_tui_state(project.state_dir)
    assert reloaded.model == "openai/gpt-4o"
    assert reloaded.mode == "planning"  # untouched


async def test_slash_model_set_persists_to_project_config(
    tmp_project, agent_factory_for, text_response
) -> None:
    """End-to-end: typing `/model X` in the TUI now updates project
    config (not just tui_state.json), so the resolver picks X next boot
    even when config.toml already had a model set by the wizard."""
    from veles.core.project_config import load_project_config, save_project_config

    project, store = tmp_project
    save_project_config(
        project,
        {"engine": {"provider": "openrouter", "model": "anthropic/old"}},
    )
    app = TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "/model openai/gpt-4o"
        await pilot.press("enter")
        await pilot.pause()
    cfg = load_project_config(project)
    assert cfg["engine"]["model"] == "openai/gpt-4o"
    assert cfg["engine"]["provider"] == "openrouter"


async def test_picker_pick_persists_to_project_config(
    tmp_project, agent_factory_for, text_response
) -> None:
    """Same guarantee for the picker path — `_after_model_pick` mirrors
    into project config too."""
    from veles.core.project_config import load_project_config
    from veles.tui.screens.model_picker import known_models

    project, store = tmp_project
    app = TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "/model"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
    expected = known_models("openrouter")[0]
    cfg = load_project_config(project)
    assert cfg.get("engine", {}).get("model") == expected
