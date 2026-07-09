"""Live 2026-07-09: after generation finished the REPL froze for several
seconds before showing "done" — `_run_chain` called the M191 post-turn hooks
(insight-extraction LLM call + curator pass) synchronously ON THE EVENT-LOOP
THREAD, so prompt_toolkit couldn't process a single keystroke until they
returned. The hooks are memory upkeep, not part of the answer: they must run
on a background worker after the turn is already marked done, serialized so
a slow curator pass from turn N never stacks under turn N+1's, with a muted
HUD chip while they run and an honest note if the user quits mid-upkeep.
"""

from __future__ import annotations

import argparse
import threading
import time
from types import SimpleNamespace

import pytest

from veles.cli.commands.repl import _console, _ReplApp, _resolve_theme
from veles.cli.repl import turn as turn_mod
from veles.cli.repl.slash import build_default_registry
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

    project = init_project(tmp_path, name="upkeeptest")
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
    try:
        yield inst
    finally:
        store.close()


def _result(**over):
    base = dict(
        stopped_reason="completed",
        session_id="s1",
        text="hi",
        history=[],
        usage=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _wait_upkeep(app, timeout: float = 5.0) -> None:
    """Block until every scheduled upkeep job has finished."""
    deadline = time.monotonic() + timeout
    while app.upkeep_busy:
        assert time.monotonic() < deadline, "upkeep never finished"
        time.sleep(0.01)


# --- the freeze itself: the turn must be done before the hooks are ---


async def test_run_chain_returns_before_hooks_finish(app, monkeypatch):
    hooks_started = threading.Event()
    release = threading.Event()
    hooks_done = threading.Event()

    def slow_hooks(args, project, result):
        hooks_started.set()
        release.wait(timeout=3)
        hooks_done.set()

    monkeypatch.setattr(turn_mod, "_run_repl_post_turn_hooks", slow_hooks)
    monkeypatch.setattr(app, "_blocking_turn", lambda text: _result())

    await app._run_chain("hello")

    # The user's turn is over (busy dropped, prompt back) while the hooks are
    # still in flight — this is exactly what un-freezes the input box.
    assert app.busy is False
    assert not hooks_done.is_set()
    release.set()
    _wait_upkeep(app)
    assert hooks_done.is_set()


async def test_hooks_run_off_the_loop_thread_with_the_turn_result(app, monkeypatch):
    seen: dict = {}
    result = _result()

    def hooks(args, project, res):
        seen["thread"] = threading.current_thread()
        seen["result"] = res
        seen["project"] = project

    monkeypatch.setattr(turn_mod, "_run_repl_post_turn_hooks", hooks)
    monkeypatch.setattr(app, "_blocking_turn", lambda text: result)

    await app._run_chain("hello")
    _wait_upkeep(app)

    assert seen["result"] is result
    assert seen["project"] is app.project
    # Blocking LLM calls must never run on the event-loop thread.
    assert seen["thread"] is not threading.current_thread()


async def test_upkeep_runs_never_overlap(app, monkeypatch):
    """Back-to-back turns each schedule hooks; a slow curator pass from turn N
    must fully finish before turn N+1's hooks start (single upkeep worker)."""
    guard = threading.Lock()
    overlap = {"active": 0, "max": 0}

    def hooks(args, project, res):
        with guard:
            overlap["active"] += 1
            overlap["max"] = max(overlap["max"], overlap["active"])
        time.sleep(0.05)
        with guard:
            overlap["active"] -= 1

    monkeypatch.setattr(turn_mod, "_run_repl_post_turn_hooks", hooks)
    monkeypatch.setattr(app, "_blocking_turn", lambda text: _result())

    await app._run_chain("one")
    await app._run_chain("two")
    _wait_upkeep(app)

    assert overlap["max"] == 1


# --- honesty: the HUD and the quit path must say upkeep is running ---


def _hud_text(app) -> str:
    return "".join(text for _style, text in app._meta_fragments())


def test_hud_shows_upkeep_chip_while_hooks_run(app):
    app.busy = False
    app.last_stopped_reason = "completed"
    app._upkeep_futures.add(object())  # simulate an in-flight upkeep job
    assert "upkeep" in _hud_text(app)
    app._upkeep_futures.clear()
    assert "upkeep" not in _hud_text(app)


def test_hud_hides_upkeep_chip_while_next_turn_is_busy(app):
    """During the next turn the working HUD owns the line — no chip clutter."""
    app.busy = True
    app._upkeep_futures.add(object())
    assert "upkeep" not in _hud_text(app)


def test_note_pending_upkeep_prints_only_when_running(app, capsys):
    """Quitting while upkeep is in flight: the interpreter waits for the
    worker thread at exit, and a silent multi-second pause after Ctrl+D
    reads as a hang — say what's happening."""
    app._upkeep_futures.add(object())
    app._note_pending_upkeep()
    assert "upkeep" in capsys.readouterr().out
    app._upkeep_futures.clear()
    app._note_pending_upkeep()
    assert capsys.readouterr().out == ""
