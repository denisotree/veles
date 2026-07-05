"""M187 Task 5: `/theme` picker for the inline REPL.

Ports the capability the deleted Textual chat UI had (Ctrl+T theme picker,
removed in M187's Textual-chat-UI deletion): `/theme` opens a filterable list
of available themes (from `cli.tui_theme.list_themes`); typing filters,
up/down/digits move the selection, Enter applies + persists, Esc cancels.
`/theme <name>` applies a named theme directly, bypassing the picker.

Covers the pure picker logic (open/filter/move/pick/cancel) headlessly,
mirroring how `test_repl_file_picker.py` tests the `@` file picker and
`test_repl_prototype.py` tests the `/model` picker — no live prompt_toolkit
`Application.run()`. The `/theme` keypress routing itself (through
prompt_toolkit's key processor) is not exercised here — see the report for
the real-TTY smoke-test note.
"""

from __future__ import annotations

import argparse

import pytest

from veles.cli.commands.repl import _console, _ReplApp, _resolve_theme
from veles.cli.repl.slash import build_default_registry
from veles.core.session_state import AppState


def _state() -> AppState:
    return AppState(session_id=None, provider_name="openrouter", model="m")


def _project_and_store(tmp_path):
    from veles.core.memory import SessionStore
    from veles.core.project import init_project

    project = init_project(tmp_path, name="repltest")
    return project, SessionStore(project.memory_db_path)


def _build_app(tmp_path):
    project, store = _project_and_store(tmp_path)
    state = _state()
    app = _ReplApp(
        argparse.Namespace(),
        project,
        state,
        lambda *_a, **_k: None,
        store,
        build_default_registry(project=project),
        _console(),
        _resolve_theme(state),
        [],
    )
    return app, store


@pytest.fixture
def app(tmp_path):
    inst, store = _build_app(tmp_path)
    try:
        yield inst
    finally:
        store.close()


@pytest.fixture(autouse=True)
def _isolated_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    return home


# --- /theme opens the picker, populated from list_themes() ---


def test_dispatch_bare_theme_opens_picker(app, monkeypatch) -> None:
    import asyncio

    from veles.cli import tui_theme as _tui_theme

    monkeypatch.setattr(_tui_theme, "list_themes", lambda: ["everforest", "dracula", "gruvbox"])
    asyncio.run(app._dispatch("/theme"))
    assert app.tp_active is True
    assert app.tp_themes == ["everforest", "dracula", "gruvbox"]
    assert app.tp_sel == 0


def test_open_theme_picker_populates_from_list_themes(app, monkeypatch) -> None:
    from veles.cli import tui_theme as _tui_theme

    monkeypatch.setattr(_tui_theme, "list_themes", lambda: ["everforest", "dracula"])
    app._open_theme_picker()
    assert app.tp_active is True
    assert app.tp_themes == ["everforest", "dracula"]
    assert app.tp_sel == 0


# --- filter narrows theme names (case-insensitive) ---


def test_tp_filtered_narrows_case_insensitive(app) -> None:
    app.tp_active = True
    app.tp_themes = ["everforest", "dracula", "gruvbox", "tokyo-night"]
    app.input.text = "DRAC"
    assert app._tp_filtered() == ["dracula"]


def test_tp_filtered_empty_filter_returns_all(app) -> None:
    app.tp_active = True
    app.tp_themes = ["everforest", "dracula"]
    app.input.text = ""
    assert app._tp_filtered() == ["everforest", "dracula"]


# --- movement ---


def test_tp_move_wraps(app) -> None:
    app.tp_active = True
    app.tp_themes = ["a", "b", "c"]
    app.tp_sel = 0
    app._tp_move(-1)
    assert app.tp_sel == 2  # wraps to the last
    app._tp_move(1)
    assert app.tp_sel == 0  # wraps back to the first


# --- select persists + applies live ---


def test_tp_pick_sets_state_and_persists(app) -> None:
    from veles.core.user_config import load_user_config

    app.tp_active = True
    app.tp_themes = ["everforest", "dracula", "gruvbox"]
    app.input.text = "drac"
    assert app._tp_filtered() == ["dracula"]
    app.tp_sel = 0
    app._tp_pick()
    assert app.state.theme_name == "dracula"
    assert app.tp_active is False  # picker closed
    assert app.input.text == ""  # filter cleared
    assert load_user_config().tui_theme == "dracula"  # persisted to config.toml


def test_tp_pick_restyles_running_app(app) -> None:
    """Applying a theme rebuilds the live theme object + prompt_toolkit Style
    for SUBSEQUENT rendering (already-emitted scrollback can't change — that's
    an immutable terminal buffer, not a bug)."""
    app.tp_active = True
    app.tp_themes = ["dracula"]
    app.tp_sel = 0
    old_style = app.app.style
    app._tp_pick()
    assert app.theme.name == "dracula"
    assert app.app.style is not old_style  # a fresh Style was built + assigned


def test_tp_pick_noop_on_no_matches(app) -> None:
    app.tp_active = True
    app.tp_themes = ["everforest"]
    app.input.text = "zzz"
    app._tp_pick()
    assert app.tp_active is True  # stays open — nothing to pick
    assert app.state.theme_name == "everforest"  # unchanged (default)


# --- /theme <name> applies directly ---


def test_slash_theme_with_name_sets_and_persists(app) -> None:
    import asyncio

    from veles.core.user_config import load_user_config

    asyncio.run(app._dispatch("/theme gruvbox"))
    assert app.state.theme_name == "gruvbox"
    assert app.theme.name == "gruvbox"  # live restyle happened too
    assert load_user_config().tui_theme == "gruvbox"


def test_slash_theme_unknown_name_handled_gracefully(app) -> None:
    import asyncio

    app.state.theme_name = "everforest"
    asyncio.run(app._dispatch("/theme not-a-real-theme"))
    assert app.state.theme_name == "everforest"  # unchanged, no crash


# --- Esc/cancel leaves state unchanged ---


def test_tp_cancel_leaves_theme_unchanged(app) -> None:
    app.state.theme_name = "everforest"
    app.tp_active = True
    app.tp_themes = ["everforest", "dracula"]
    app.tp_sel = 1
    app._tp_cancel()
    assert app.tp_active is False
    assert app.state.theme_name == "everforest"  # unchanged


def test_ctrl_c_cancels_theme_picker(app) -> None:
    class _Event:
        app = None

    app.tp_active = True
    app.tp_themes = ["everforest"]
    app.state.theme_name = "everforest"
    app._on_ctrl_c(_Event())
    assert app.tp_active is False
    assert app.state.theme_name == "everforest"
