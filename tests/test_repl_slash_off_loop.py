"""Every REPL slash command runs without tripping the memory loop guard.

Found 2026-09-23 while re-checking for the daemon's M281 bug class: the inline
REPL dispatched slash handlers with prompt_toolkit's `run_in_terminal(func)`,
which runs `func` ON the event loop thread, and M264's memory bridge
(`core/memory/aio.py::submit`) refuses to block a running loop. `/insights` and
`/rules` failed with "memory.aio.submit() called from inside an event loop"
from 0.36.0 to 0.39.0. Slash handlers are synchronous code, so `_slash` now runs
them in an executor, like a turn.

The fake `run_in_terminal` below keeps prompt_toolkit's semantics exactly —
`in_executor=False` calls `func` on the loop, `True` runs it in a thread — so a
dispatch that goes back on the loop fails here for every command at once.
"""

from __future__ import annotations

import argparse
import asyncio

import pytest

from veles.cli.commands.repl import _console, _ReplApp, _resolve_theme
from veles.cli.repl.slash import build_default_registry
from veles.core.session_state import AppState

_LOOP_GUARD = ("inside an event loop", "cannot be called from a running event loop")


@pytest.fixture(autouse=True)
def _isolated_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))


@pytest.fixture
def app(tmp_path, monkeypatch):
    from veles.core.memory import SessionStore
    from veles.core.project import init_project

    async def run_in_terminal(func, render_cli_done=False, in_executor=False):
        return await asyncio.to_thread(func) if in_executor else func()

    monkeypatch.setattr("prompt_toolkit.application.run_in_terminal", run_in_terminal)
    project = init_project(tmp_path / "proj", name="repltest")
    store = SessionStore(project.memory_db_path)
    state = AppState(session_id=store.create_session(), provider_name="openrouter", model="m")
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
    inst.app.exit = lambda *a, **k: None  # /quit must not tear down the test
    yield inst
    store.close()


def _commands(app) -> list[str]:
    names = {n if n.startswith("/") else f"/{n}" for n in app.registry.names()}
    return sorted(names | {"/help", "/errors", "/sessions", "/resume"})


async def test_no_slash_command_runs_on_the_event_loop(app, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(""))  # prompts get EOF
    failures: dict[str, str] = {}
    for cmd in [*_commands(app), "/insights all 5", "/rules do"]:
        try:
            await app._slash(cmd)
        except Exception as exc:
            if any(marker in str(exc) for marker in _LOOP_GUARD):
                failures[cmd] = str(exc)
    assert not failures, f"slash commands ran on the event loop: {failures}"


async def test_insights_answers_in_the_repl(app, capsys) -> None:
    """The user-visible symptom, end to end."""
    await app._slash("/insights")
    assert "no insights yet" in capsys.readouterr().out
