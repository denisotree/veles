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

    parser = build_parser()
    assert parser.parse_args(["repl", "-c"]).continue_last is True
    assert parser.parse_args(["repl", "--continue"]).continue_last is True
    assert parser.parse_args(["repl"]).continue_last is False


def test_bare_veles_and_flag_first_route_to_repl() -> None:
    """`veles`, `veles -c`, `veles --provider X` all resolve to the repl surface;
    top-level globals are left alone."""
    from veles.cli import _normalize_argv

    assert _normalize_argv([]) == ["repl"]
    assert _normalize_argv(["-c"]) == ["repl", "-c"]
    assert _normalize_argv(["--provider", "openrouter"]) == ["repl", "--provider", "openrouter"]
    assert _normalize_argv(["repl", "-c"]) == ["repl", "-c"]  # explicit subcommand kept
    assert _normalize_argv(["init"]) == ["init"]  # other subcommand kept
    assert _normalize_argv(["--version"]) == ["--version"]  # global left alone
    assert _normalize_argv(["-h"]) == ["-h"]


def test_veles_dash_c_parses_as_repl_continue() -> None:
    from veles.cli import _normalize_argv
    from veles.cli._parsers import build_parser

    ns = build_parser().parse_args(_normalize_argv(["-c"]))
    assert ns.command == "repl" and ns.continue_last is True


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


def test_no_continue_starts_fresh(project) -> None:
    _seed_two_sessions(project)  # sessions exist but -c not passed
    state, _factory, store, _subf = _build_runtime(_args(continue_last=False), project)
    try:
        assert state.session_id is None
    finally:
        store.close()
