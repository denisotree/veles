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
    """Return (older_id, newer_id) with the newer having later activity."""
    s = SessionStore(project.memory_db_path)
    try:
        old = s.create_session(title="old")
        new = s.create_session(title="new")
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


def test_no_continue_starts_fresh(project) -> None:
    _seed_two_sessions(project)  # sessions exist but -c not passed
    state, _factory, store, _subf = _build_runtime(_args(continue_last=False), project)
    try:
        assert state.session_id is None
    finally:
        store.close()
