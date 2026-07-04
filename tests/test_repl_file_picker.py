"""M187 Task 4: `@` file picker for the inline REPL.

Ports the capability the deleted Textual `FilePickerScreen` had (M78,
removed in M187's Textual-chat-UI deletion): typing `@` at a word boundary
opens a filterable list of project files (via
`cli.repl.file_index.iter_project_files`); arrows/digits move the
selection; Enter inserts the chosen POSIX-relative path after the `@`;
Escape cancels, leaving the input untouched.

Covers the pure picker logic (filter / select / open / boundary-check)
headlessly, mirroring how test_repl_prototype.py tests the `/model`
picker (`_filter_models`, `_mp_move`, `_mp_pick`, ...) without driving a
live prompt_toolkit Application. The `@` keypress itself (routed through
prompt_toolkit's key processor) is not exercised here — see the report for
the real-TTY smoke-test note.
"""

from __future__ import annotations

import argparse
from pathlib import Path

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


# --- filtering ---


def test_filter_files_substring_case_insensitive() -> None:
    from veles.cli.commands.repl import _filter_files

    files = ["README.md", "src/main.py", "src/alpha.py", "docs/README.md"]
    assert _filter_files(files, "") == files  # empty → all
    assert _filter_files(files, "ALPHA") == ["src/alpha.py"]
    assert _filter_files(files, "readme") == ["README.md", "docs/README.md"]
    assert _filter_files(files, "zzz") == []


def test_fp_filter_text_reads_after_last_at_sign(app) -> None:
    app.input.text = "@alp"
    assert app._fp_filter_text() == "alp"
    app.input.text = "look at @src/al"
    assert app._fp_filter_text() == "src/al"
    app.input.text = "no at sign here"
    assert app._fp_filter_text() == ""


# --- word-boundary trigger check ---


def test_at_trigger_boundary() -> None:
    from veles.cli.commands.repl import _at_trigger_boundary

    assert _at_trigger_boundary("") is True  # start of input
    assert _at_trigger_boundary("hello ") is True  # after whitespace
    assert _at_trigger_boundary("hello\n") is True  # after a newline
    assert _at_trigger_boundary("foo") is False  # mid-word (foo@bar.com)


# --- open trigger populates from iter_project_files ---


def test_open_file_picker_populates_from_iter_project_files(app, monkeypatch) -> None:
    from veles.cli.repl import file_index as _file_index

    monkeypatch.setattr(
        _file_index,
        "iter_project_files",
        lambda *_a, **_k: [Path("README.md"), Path("src/main.py")],
    )
    app._open_file_picker()
    assert app.fp_active is True
    assert app.fp_files == ["README.md", "src/main.py"]  # posix strings
    assert app.fp_sel == 0


def test_open_file_picker_empty_project_no_crash(app, monkeypatch) -> None:
    from veles.cli.repl import file_index as _file_index

    monkeypatch.setattr(_file_index, "iter_project_files", lambda *_a, **_k: [])
    app._open_file_picker()
    assert app.fp_active is True
    assert app.fp_files == []
    assert app._fp_filtered() == []
    frags = app._fp_fragments()  # must render without raising
    assert frags is not None


# --- selection -> insert ---


def test_fp_pick_inserts_posix_path_after_at(app) -> None:
    app.fp_active = True
    app.fp_files = ["README.md", "src/alpha.py"]
    app.input.text = "@alpha"
    app.fp_sel = 0
    app._fp_pick()
    assert app.input.text == "@src/alpha.py"
    assert app.fp_active is False  # picker closes after picking


def test_fp_pick_preserves_text_before_the_at_sign(app) -> None:
    app.fp_active = True
    app.fp_files = ["README.md"]
    app.input.text = "please check @read"
    app.fp_sel = 0
    app._fp_pick()
    assert app.input.text == "please check @README.md"


def test_fp_pick_noop_on_no_matches(app) -> None:
    app.fp_active = True
    app.fp_files = ["README.md"]
    app.input.text = "@zzz"
    app._fp_pick()
    assert app.input.text == "@zzz"  # unchanged
    assert app.fp_active is True  # stays open — nothing to pick


# --- movement / cancel ---


def test_fp_move_wraps(app) -> None:
    app.fp_active = True
    app.fp_files = ["a.py", "b.py", "c.py"]
    app.input.text = "@"
    app.fp_sel = 0
    app._fp_move(-1)
    assert app.fp_sel == 2  # wraps to the last
    app._fp_move(1)
    assert app.fp_sel == 0  # wraps back to the first


def test_fp_cancel_closes_without_touching_input(app) -> None:
    app.fp_active = True
    app.fp_files = ["a.py"]
    app.input.text = "@a"
    app._fp_cancel()
    assert app.fp_active is False
    assert app.fp_files == []
    assert app.input.text == "@a"  # left as-is (matches the old Textual screen)


def test_fp_select_row_uses_visible_window_offset(app) -> None:
    app.fp_active = True
    app.fp_files = [f"file{i}.py" for i in range(20)]
    app.input.text = "@"
    app.fp_sel = 15  # scrolls the window away from the top
    start_before = app._fp_window_start(len(app._fp_filtered()))
    app._fp_select_row(0)  # pick the first row of the CURRENTLY shown window
    assert app.fp_sel == start_before


# --- on_input_changed wiring (typing while the picker is open) ---


def test_on_input_changed_closes_picker_when_at_sign_deleted(app) -> None:
    app.fp_active = True
    app.fp_files = ["a.py"]
    app.input.text = "hello"  # backspaced past the `@`
    app._on_input_changed(app.input.buffer)
    assert app.fp_active is False


def test_on_input_changed_resets_selection_while_filtering(app) -> None:
    app.fp_active = True
    app.fp_files = ["a.py", "b.py"]
    app.fp_sel = 1
    app.input.text = "@a"
    app._on_input_changed(app.input.buffer)
    assert app.fp_sel == 0
    assert app.fp_active is True


# --- ctrl-c cancels the picker like the /model picker ---


def test_ctrl_c_cancels_file_picker(app) -> None:
    class _Event:
        app = None

    app.fp_active = True
    app.fp_files = ["a.py"]
    app.input.text = "@a"
    app._on_ctrl_c(_Event())
    assert app.fp_active is False
