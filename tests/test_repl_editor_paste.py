"""M187 Task 7: `$EDITOR` compose + Ctrl+V image paste for the inline REPL.

Ports two capabilities the deleted Textual chat UI had:

- Ctrl+G opened the draft in `$EDITOR` (Textual's `Composer.action_launch_editor`).
  prompt_toolkit's `Buffer.open_in_editor()` already does the write-temp-file /
  spawn-editor / reload-on-return dance — we just need to wire a key to it.
- Ctrl+V pasted a clipboard image to `<project>/.veles/tmp/paste/<name>.png` and
  inserted an `@<relative-path>` reference (`AppMixin.action_paste_clipboard`).

CRITICAL LESSON (M187 Task 6, `ffc92c0`): `Keys.ControlI IS Keys.Tab` in
prompt_toolkit, and `Application` merges its OWN key_bindings ABOVE
prompt_toolkit's defaults — an unguarded `@kb.add(...)` can silently shadow a
default binding the isolated `_make_keys()` object never surfaces. Before
picking a key here we verified (see `docs`/report, and the source read in this
session):

- `c-x c-e` (emacs "open in editor"): prompt_toolkit ships this via
  `key_binding.bindings.open_in_editor.load_emacs_open_in_editor_bindings()`,
  but `Application._default_bindings` is `key_binding.defaults.load_key_bindings()`,
  which does NOT merge that helper in — so `c-x c-e` is a no-op here by
  default. We bind it ourselves; no existing `c-x` second-key ("c-u", "r y",
  "(", ")", "e", "c-x" — see `key_binding/bindings/emacs.py`) collides with a
  second key of "c-e".
- `c-g`: prompt_toolkit's DEFAULT abort/keyboard-quit (`basic.py` + `emacs.py`
  both bind `c-g`). Deliberately left UNBOUND here (unlike the old Textual
  Ctrl+G) so the default still fires.
- `c-v`: `basic.py`'s `c-v` is a no-op placeholder (`_ignore`); the emacs
  `c-v` -> scroll-page-down binding only activates under
  `enable_page_navigation_bindings`, which defaults to `Condition(lambda:
  self.full_screen)` — this Application passes `full_screen=False`, so it's
  disabled. Safe to bind.

Tests below use BOTH the isolated `_make_keys()` object (fast, precise handler
identity — mirrors `_kb_handler` in `test_repl_prototype.py`) AND the real
merged `Application` driven through piped input (the seam that caught the
Task 6 Tab/Ctrl+I bug, since a shadowing default only shows up once merged).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

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


def _kb_handler_seq(kb, *key_names: str):
    """Look up the real handler bound to a key SEQUENCE (e.g. `("c-x",
    "c-e")`) in a `KeyBindings` object built by `_ReplApp._make_keys()`. `None`
    when no binding matches — used to assert a key was deliberately left
    unbound (e.g. Ctrl+G)."""
    from prompt_toolkit.keys import Keys

    name_map = {"c-v": "ControlV", "c-g": "ControlG", "c-x": "ControlX", "c-e": "ControlE"}
    resolved = tuple(getattr(Keys, name_map[k]) for k in key_names)
    matches = kb.get_bindings_for_keys(resolved)
    return matches[0].handler if matches else None


# --- collision analysis: isolated _make_keys() object ---


def test_ctrl_g_left_unbound_default_abort_still_reachable(app) -> None:
    """We deliberately do NOT bind Ctrl+G (the old Textual composer's
    "open $EDITOR" key) — Ctrl+G is prompt_toolkit's DEFAULT abort/
    keyboard-quit (bound in both `basic.py` and `emacs.py`). Asserting no
    binding exists for it here documents that the default keeps firing
    instead of being shadowed."""
    kb = app._make_keys()
    assert _kb_handler_seq(kb, "c-g") is None


def test_ctrl_x_ctrl_e_bound_to_our_handler(app) -> None:
    kb = app._make_keys()
    handler = _kb_handler_seq(kb, "c-x", "c-e")
    assert handler is not None


def test_ctrl_v_bound_to_our_handler(app) -> None:
    kb = app._make_keys()
    handler = _kb_handler_seq(kb, "c-v")
    assert handler is not None


# --- $EDITOR compose: wiring + no-TTY guard ---


def test_ctrl_x_ctrl_e_opens_editor_on_input_buffer_when_tty(app, monkeypatch) -> None:
    """Can't run a real $EDITOR headlessly — assert the handler is wired to
    `self.input.buffer.open_in_editor` specifically, not a live editor run."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    called = []
    monkeypatch.setattr(app.input.buffer, "open_in_editor", lambda: called.append(True))
    kb = app._make_keys()
    handler = _kb_handler_seq(kb, "c-x", "c-e")
    handler(None)
    assert called == [True]


def test_ctrl_x_ctrl_e_noop_without_tty(app, monkeypatch) -> None:
    """Headless run (no TTY) degrades to a no-op instead of hanging on a
    subprocess spawn — same guard shape as `_ask`/`_confirm_critical`."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    called = []
    monkeypatch.setattr(app.input.buffer, "open_in_editor", lambda: called.append(True))
    kb = app._make_keys()
    handler = _kb_handler_seq(kb, "c-x", "c-e")
    handler(None)
    assert called == []


# --- image paste logic (direct calls — no live Application needed) ---


def test_paste_clipboard_inserts_at_ref_when_image_saved(app, monkeypatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("veles.cli.repl.clipboard.paste_image", lambda target: True)
    monkeypatch.setattr(
        "veles.cli.repl.clipboard.paste_text", lambda: (_ for _ in ()).throw(AssertionError)
    )
    app.input.text = "look at "
    app.input.buffer.cursor_position = len(app.input.text)
    app._paste_clipboard()
    assert app.input.text.startswith("look at @.veles/tmp/paste/")
    assert app.input.text.endswith(".png ")


def test_paste_clipboard_falls_back_to_text_when_no_image(app, monkeypatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("veles.cli.repl.clipboard.paste_image", lambda target: False)
    monkeypatch.setattr("veles.cli.repl.clipboard.paste_text", lambda: "hello clipboard")
    app.input.text = ""
    app._paste_clipboard()
    assert app.input.buffer.text == "hello clipboard"


def test_paste_clipboard_graceful_noop_when_clipboard_empty(app, monkeypatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("veles.cli.repl.clipboard.paste_image", lambda target: False)
    monkeypatch.setattr("veles.cli.repl.clipboard.paste_text", lambda: None)
    app.input.text = "unchanged"
    app._paste_clipboard()
    assert app.input.text == "unchanged"


def test_paste_clipboard_noop_without_tty(app, monkeypatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    calls = []
    monkeypatch.setattr(
        "veles.cli.repl.clipboard.paste_image", lambda target: calls.append(target) or True
    )
    app.input.text = "unchanged"
    app._paste_clipboard()
    assert calls == []
    assert app.input.text == "unchanged"


# --- collision regression: the real MERGED Application, not the isolated kb ---
# (mirrors `test_tab_still_cycles_completion_with_inspector_binding` in
# test_repl_prototype.py, the test shape that caught the Task 6 Ctrl+I/Tab bug)


async def test_ctrl_v_merged_app_reaches_our_handler(tmp_path, monkeypatch) -> None:
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    with (
        create_pipe_input() as pipe_input,
        create_app_session(input=pipe_input, output=DummyOutput()),
    ):
        app, store = _build_app(tmp_path)
        called = []
        monkeypatch.setattr(app, "_paste_clipboard", lambda: called.append(True))
        try:
            task = asyncio.ensure_future(app.app.run_async())
            await asyncio.sleep(0.05)

            pipe_input.send_text("\x16")  # Ctrl+V
            await asyncio.sleep(0.05)
            assert called == [True]
        finally:
            app.app.exit()
            await task
            store.close()


async def test_ctrl_x_ctrl_e_merged_app_reaches_our_handler(tmp_path, monkeypatch) -> None:
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    with (
        create_pipe_input() as pipe_input,
        create_app_session(input=pipe_input, output=DummyOutput()),
    ):
        app, store = _build_app(tmp_path)
        called = []
        monkeypatch.setattr(app.input.buffer, "open_in_editor", lambda: called.append(True))
        try:
            task = asyncio.ensure_future(app.app.run_async())
            await asyncio.sleep(0.05)

            pipe_input.send_text("\x18\x05")  # Ctrl+X, Ctrl+E
            await asyncio.sleep(0.05)
            assert called == [True]
        finally:
            app.app.exit()
            await task
            store.close()


async def test_ctrl_g_merged_app_does_not_reach_our_code_default_abort_intact(
    tmp_path, monkeypatch
) -> None:
    """Ctrl+G must NOT be captured by our bindings — pressing it must not
    invoke `_paste_clipboard`, `open_in_editor`, or toggle any of our picker
    state, leaving prompt_toolkit's own default abort handling in charge."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with (
        create_pipe_input() as pipe_input,
        create_app_session(input=pipe_input, output=DummyOutput()),
    ):
        app, store = _build_app(tmp_path)
        paste_calls = []
        editor_calls = []
        monkeypatch.setattr(app, "_paste_clipboard", lambda: paste_calls.append(True))
        monkeypatch.setattr(app.input.buffer, "open_in_editor", lambda: editor_calls.append(True))
        try:
            task = asyncio.ensure_future(app.app.run_async())
            await asyncio.sleep(0.05)

            pipe_input.send_text("\x07")  # Ctrl+G
            await asyncio.sleep(0.05)
            assert paste_calls == []
            assert editor_calls == []
        finally:
            app.app.exit()
            await task
            store.close()
