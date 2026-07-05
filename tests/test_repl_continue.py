"""`veles repl -c` / `--continue` — resume this project's most recent session."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pytest

from veles.cli.commands.repl import _build_runtime
from veles.core.context import reset_active_project, set_active_project
from veles.core.layout import clear_engine_cache
from veles.core.memory import SessionStore
from veles.core.project import init_project


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


def _args(**over) -> argparse.Namespace:
    base = dict(
        provider="ollama",  # local, keyless
        model="m",
        resume=None,
        continue_last=False,
        max_iterations=30,
        verbose=False,
        no_agents_md=False,
        no_index=False,
    )
    base.update(over)
    return argparse.Namespace(**base)


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    p = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def _seed_two_sessions(project) -> tuple[str, str]:
    """Return (older_id, newer_id), each with a turn, newer having later activity."""
    from veles.core.provider import Message

    s = SessionStore(project.memory_db_path)
    try:
        old = s.create_session(title="old")
        s.append_turn(old, Message(role="user", content="hi"))
        new = s.create_session(title="new")
        s.append_turn(new, Message(role="user", content="hi"))
        # Make `new` unambiguously the most recent.
        s._conn.execute(
            "UPDATE sessions SET last_activity_at=? WHERE id=?", (time.time() + 100, new)
        )
        s._conn.commit()
    finally:
        s.close()
    return old, new


def test_parser_accepts_c_flag() -> None:
    from veles.cli._parsers import build_parser

    parser = build_parser()  # -c / --continue are top-level (bare `veles`)
    assert parser.parse_args(["-c"]).continue_last is True
    assert parser.parse_args(["--continue"]).continue_last is True
    assert parser.parse_args([]).continue_last is False


def test_bare_veles_and_flags_dispatch_to_repl() -> None:
    """No subcommand → the interactive REPL (command is None). Its flags live on
    the top-level parser so `veles`, `veles -c`, `veles --provider X` all work
    without a subcommand; real subcommands still parse."""
    from veles.cli._parsers import build_parser

    p = build_parser()
    assert p.parse_args([]).command is None
    assert p.parse_args(["-c"]).command is None
    assert p.parse_args(["-c"]).continue_last is True
    assert p.parse_args(["--provider", "ollama"]).command is None
    assert p.parse_args(["run", "q"]).command == "run"


def test_tui_and_repl_subcommands_removed() -> None:
    """`veles tui` and `veles repl` no longer exist — the REPL is bare `veles`."""
    from veles.cli._parsers import build_parser

    p = build_parser()
    for gone in ("tui", "repl"):
        with pytest.raises(SystemExit):
            p.parse_args([gone])


def test_continue_resolves_most_recent_session(project) -> None:
    _old, new = _seed_two_sessions(project)
    state, _factory, store, _subf = _build_runtime(_args(continue_last=True), project)
    try:
        assert state.session_id == new  # the last-active session
    finally:
        store.close()


def test_explicit_resume_wins_over_continue(project) -> None:
    _seed_two_sessions(project)
    state, _factory, store, _subf = _build_runtime(
        _args(continue_last=True, resume="explicit-id"), project
    )
    try:
        assert state.session_id == "explicit-id"
    finally:
        store.close()


def test_continue_with_no_sessions_starts_fresh(project, capsys) -> None:
    state, _factory, store, _subf = _build_runtime(_args(continue_last=True), project)
    try:
        assert state.session_id is None
        assert "starting fresh" in capsys.readouterr().out
    finally:
        store.close()


def test_continue_skips_empty_sessions(project) -> None:
    """An empty session (no turns) from an aborted launch is skipped; the most
    recent session WITH content is resumed."""
    from veles.core.provider import Message

    s = SessionStore(project.memory_db_path)
    try:
        real = s.create_session(title="real")
        s.append_turn(real, Message(role="user", content="did work"))
        empty = s.create_session(title="empty")  # newer, but no turns
        s._conn.execute(
            "UPDATE sessions SET last_activity_at=? WHERE id=?", (time.time() + 100, empty)
        )
        s._conn.commit()
    finally:
        s.close()

    state, _factory, store, _subf = _build_runtime(_args(continue_last=True), project)
    try:
        assert state.session_id == real  # skipped the newer empty one
    finally:
        store.close()


def test_resume_recap_replays_recent_conversation(project, capsys) -> None:
    """Resuming must SHOW the tail of the conversation so it's visibly continued
    (not a blank screen that looks fresh)."""
    from rich.console import Console

    from veles.cli.commands.repl import _print_resume_recap, _resolve_theme
    from veles.core.provider import Message
    from veles.core.session_state import AppState

    store = SessionStore(project.memory_db_path)
    try:
        sid = store.create_session(title="t")
        store.append_turn(sid, Message(role="user", content="what is thompson sampling?"))
        store.append_turn(sid, Message(role="assistant", content="It is a bandit algorithm."))
        theme = _resolve_theme(AppState(session_id=None, provider_name="ollama", model="m"))
        _print_resume_recap(Console(force_terminal=True), theme, store, sid)
    finally:
        store.close()

    out = capsys.readouterr().out
    assert "continuing this conversation" in out
    assert "what is thompson sampling?" in out  # user turn shown
    assert "bandit algorithm" in out  # assistant turn shown


def test_no_continue_starts_fresh(project) -> None:
    _seed_two_sessions(project)  # sessions exist but -c not passed
    state, _factory, store, _subf = _build_runtime(_args(continue_last=False), project)
    try:
        assert state.session_id is None
    finally:
        store.close()
