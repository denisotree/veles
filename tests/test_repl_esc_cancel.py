"""Esc during a running turn: stop instantly, restore only before first output.

Reported UX: pressing Esc while a request runs didn't feel like it stopped —
it dropped the last request back into the input box while output kept streaming.
Desired: Esc cancels the turn *and instantly stops rendering* further tokens;
the request text is restored for editing ONLY when nothing has been generated
yet (`stream_chars == 0`). Once the answer has started streaming, Esc is a plain
stop with no restore.
"""

from __future__ import annotations

import argparse

import pytest

from veles.cli.commands.repl import (
    _console,
    _make_turn_callbacks,
    _ReplApp,
    _resolve_theme,
)
from veles.cli.repl.slash import build_default_registry
from veles.core.cancel import CancelToken
from veles.core.session_state import AppState


@pytest.fixture(autouse=True)
def _isolated_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    return home


@pytest.fixture
def app(tmp_path):
    from veles.core.memory import SessionStore
    from veles.core.project import init_project

    project = init_project(tmp_path / "proj", name="repltest")
    store = SessionStore(project.memory_db_path)
    state = AppState(session_id=None, provider_name="openrouter", model="m")
    inst = _ReplApp(
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
    inst.busy = True
    inst.cancel_token = CancelToken()
    inst._last_submitted = "my question"
    inst.input.text = ""
    try:
        yield inst
    finally:
        store.close()


def test_esc_before_generation_cancels_and_restores(app) -> None:
    app.stream_chars = 0  # nothing streamed yet
    app._cancel_generation()
    assert app.cancel_token.cancelled is True
    assert app.input.text == "my question"  # restored for editing


def test_ctrl_c_in_busy_escalates_to_force_quit(app, monkeypatch) -> None:
    """First Ctrl+C while busy → cooperative cancel; a second (the turn still
    hasn't stopped) → force-quit, so a wedged turn is never a dead end."""
    import types

    forced = {"n": 0}
    monkeypatch.setattr(app, "_force_quit", lambda: forced.__setitem__("n", forced["n"] + 1))
    monkeypatch.setattr(app, "_spawn", lambda *_a, **_k: None)  # no live loop in the test
    ev = types.SimpleNamespace(app=types.SimpleNamespace(exit=lambda: None))

    app._on_ctrl_c(ev)  # first: cooperative cancel, no force-quit
    assert app.cancel_token.cancelled is True
    assert forced["n"] == 0

    app._on_ctrl_c(ev)  # second: still busy + already cancelled → force-quit
    assert forced["n"] == 1


def test_esc_after_generation_cancels_without_restore(app) -> None:
    app.stream_chars = 42  # the answer already started streaming
    app._cancel_generation()
    assert app.cancel_token.cancelled is True
    assert app.input.text == ""  # just a stop — text NOT dropped back in


def test_esc_clears_the_queue(app) -> None:
    app.stream_chars = 5
    app.queue.append("queued follow-up")
    app._cancel_generation()
    assert len(app.queue) == 0  # a full stop, not just the current turn


def test_on_text_stops_emitting_once_stop_check_trips() -> None:
    """The instant-stop half: after cancel, streamed tokens are suppressed at
    the source so visible output halts immediately (not ~100ms later)."""
    recorded: list[tuple[str, str]] = []
    cancelled = {"v": False}
    state = AppState(session_id=None, provider_name="openrouter", model="m")
    _post, on_text, _on_event, _holder, _flush = _make_turn_callbacks(
        _console(),
        _resolve_theme(state),
        [],
        on_meta=lambda kind, text, **_kw: recorded.append((kind, text)),
        stop_check=lambda: cancelled["v"],
    )
    on_text("before-cancel")
    cancelled["v"] = True
    on_text("after-cancel")
    streamed = [text for kind, text in recorded if kind == "stream"]
    assert "before-cancel" in streamed
    assert "after-cancel" not in streamed  # suppressed once cancelled
