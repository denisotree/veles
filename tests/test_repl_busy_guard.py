"""M187 final review, fix 1 & 2: foreground pickers must not open while a
turn is running (`busy`), and `/daemon` must point at the standalone
`veles daemon` surface instead of the generic (nonsensical, for `/daemon`)
"set directly" hint.

Fix 1 rationale: a mid-turn `_ask`/`_permission_prompt`/`_confirm_critical`
(raised from the executor thread running the turn) sets `q_active = True`.
If a foreground picker (`@` file / `/model` / `/theme`) is already open
(`fp_active`/`mp_active`/`tp_active`), two mutually-exclusive filter states
(e.g. `filing` + `choosing`) are active at once and Enter/digits match two
bindings. Since `q_active` only arises during `busy`, forbidding foreground
pickers while `busy` closes the window entirely — the three OPEN paths
(the `@` keybinding, and the `/model`/`/theme` branches in `_dispatch`) are
gated on `not self.busy`.

`/model`/`/theme` do NOT get queued like a plain chat prompt: the queue
drain in `_run_chain` feeds straight into `_blocking_turn` with no
re-dispatch step, so a queued "/model" would be submitted to the LLM as a
chat message once the turn ends. Instead they fall through to the existing
`_slash` path — the same immediate-execution route every other slash
command already takes during `busy` (here, printing the static model/theme
list instead of opening the interactive picker).
"""

from __future__ import annotations

import argparse
import asyncio

import pytest

from veles.cli.commands.repl import _console, _handle_slash, _ReplApp, _resolve_theme
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


def _at_handler(app):
    """Look up the real handler bound to the plain `@` char in a
    `KeyBindings` object built by `_ReplApp._make_keys()`, mirroring the
    `_kb_handler`/`_kb_handler_seq` helpers in test_repl_prototype.py /
    test_repl_editor_paste.py — the key was registered with the literal
    string "@" (not a `Keys` enum member), so look it up the same way."""
    kb = app._make_keys()
    matches = kb.get_bindings_for_keys(("@",))
    assert matches, "no binding for '@'"
    return matches[0].handler


# --- Fix 1a: `@` file picker forbidden while busy ---


async def test_at_does_not_open_file_picker_while_busy(app) -> None:
    # async: `buffer.insert_text` schedules a background completer task via
    # `get_app().create_background_task`, which needs a running event loop.
    handler = _at_handler(app)
    app.busy = True
    app.input.text = ""
    handler(None)
    assert app.fp_active is False
    assert app.input.text == "@"  # literal char still inserted, not swallowed


async def test_at_opens_file_picker_when_not_busy(app, monkeypatch) -> None:
    from veles.cli.repl import file_index

    monkeypatch.setattr(file_index, "iter_project_files", lambda _root: [])
    handler = _at_handler(app)
    app.busy = False
    app.input.text = ""
    handler(None)
    assert app.fp_active is True


# --- Fix 1b: bare `/model` and `/theme` forbidden while busy ---


def test_slash_model_no_picker_while_busy(app, monkeypatch) -> None:
    from veles.cli.repl import model_fetcher

    monkeypatch.setattr(
        model_fetcher, "fetch_models", lambda *_a, **_k: model_fetcher.ModelList([], "curated")
    )
    app.busy = True
    asyncio.run(app._dispatch("/model"))
    # Falls through to the immediate `_slash` path (same as every other slash
    # command during busy) instead of opening the picker or queuing — queuing
    # would feed the literal "/model" text to the LLM once the turn drains
    # (`_run_chain`'s queue-pop has no re-dispatch step).
    assert app.mp_active is False
    assert list(app.queue) == []


def test_slash_model_opens_picker_when_not_busy(app, monkeypatch) -> None:
    from veles.cli.repl import model_fetcher

    monkeypatch.setattr(
        model_fetcher, "fetch_models", lambda *_a, **_k: model_fetcher.ModelList([], "curated")
    )
    app.busy = False
    asyncio.run(app._dispatch("/model"))
    assert app.mp_active is True


def test_slash_theme_no_picker_while_busy(app, monkeypatch) -> None:
    from veles.cli import tui_theme as _tui_theme

    monkeypatch.setattr(_tui_theme, "list_themes", lambda: ["everforest", "dracula"])
    app.busy = True
    asyncio.run(app._dispatch("/theme"))
    assert app.tp_active is False
    assert list(app.queue) == []


def test_slash_theme_opens_picker_when_not_busy(app, monkeypatch) -> None:
    from veles.cli import tui_theme as _tui_theme

    monkeypatch.setattr(_tui_theme, "list_themes", lambda: ["everforest", "dracula"])
    app.busy = False
    asyncio.run(app._dispatch("/theme"))
    assert app.tp_active is True


# --- Fix 2: `/daemon` points at the standalone surface, not a generic hint ---


def test_daemon_slash_prints_pointer_not_picker(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    project, store = _project_and_store(tmp_path)
    console = _console()
    errors: list[str] = []
    try:
        registry = build_default_registry(project=project)
        state = _state()

        quit_, submit = _handle_slash("/daemon", registry, state, project, store, console, errors)
        assert quit_ is False and submit is None
        out = capsys.readouterr().out
        assert "veles daemon" in out
        assert "set directly" not in out
    finally:
        store.close()
