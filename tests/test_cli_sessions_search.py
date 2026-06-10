"""M58 — `veles sessions search` CLI verb tests."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.cli.commands import sessions as sessions_cmd
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.provider import Message


@pytest.fixture()
def project_with_turns(tmp_path: Path):
    project = init_project(tmp_path / "demo", name="demo")
    store = SessionStore(project.memory_db_path)
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="please grep cosine similarity"))
    store.append_turn(sid, Message(role="assistant", content="here is the grep output"))
    store.append_turn(sid, Message(role="tool", content="tool noise output"))
    store.close()
    return project, sid


def _ns(**fields):
    return type("A", (), fields)()


def test_search_basic_hit(project_with_turns, capsys) -> None:
    project, sid = project_with_turns
    args = _ns(
        sessions_command="search",
        query="cosine",
        limit=5,
        role="both",
        since=None,
    )
    rc = sessions_cmd.cmd_sessions(args, project)
    assert rc == 0
    out = capsys.readouterr().out
    assert sid in out
    assert "cosine" in out
    assert "user" in out


def test_search_no_match_reports_none(project_with_turns, capsys) -> None:
    project, _ = project_with_turns
    args = _ns(
        sessions_command="search",
        query="absolutelynothingmatches",
        limit=5,
        role="both",
        since=None,
    )
    rc = sessions_cmd.cmd_sessions(args, project)
    assert rc == 0
    assert "no matches" in capsys.readouterr().out


def test_search_role_user_excludes_assistant(project_with_turns, capsys) -> None:
    project, _ = project_with_turns
    args = _ns(
        sessions_command="search",
        query="grep",
        limit=5,
        role="user",
        since=None,
    )
    rc = sessions_cmd.cmd_sessions(args, project)
    out = capsys.readouterr().out
    assert rc == 0
    # The user message and the assistant message both contain "grep"; only user should appear.
    user_lines = [line for line in out.splitlines() if " user " in f" {line} "]
    assistant_lines = [line for line in out.splitlines() if " assistant " in f" {line} "]
    assert user_lines
    assert not assistant_lines


def test_search_role_all_includes_tool(project_with_turns, capsys) -> None:
    project, _ = project_with_turns
    args = _ns(
        sessions_command="search",
        query="noise",
        limit=5,
        role="all",
        since=None,
    )
    rc = sessions_cmd.cmd_sessions(args, project)
    assert rc == 0
    assert "tool" in capsys.readouterr().out


def test_search_since_excludes_old(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "demo2", name="demo2")
    store = SessionStore(project.memory_db_path)
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="oldhit chitchat"))
    # Backdate by 30 days.
    old = time.time() - 30 * 86400
    store._conn.execute("UPDATE turns SET created_at = ?", (old,))
    store.close()
    args = _ns(
        sessions_command="search",
        query="oldhit",
        limit=5,
        role="both",
        since="7d",
    )
    rc = sessions_cmd.cmd_sessions(args, project)
    assert rc == 0
    assert "no matches" in capsys.readouterr().out


def test_search_limit_respected(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "demo3", name="demo3")
    store = SessionStore(project.memory_db_path)
    sid = store.create_session()
    for _ in range(8):
        store.append_turn(sid, Message(role="user", content="repeatedhit token"))
    store.close()
    args = _ns(
        sessions_command="search",
        query="repeatedhit",
        limit=2,
        role="both",
        since=None,
    )
    rc = sessions_cmd.cmd_sessions(args, project)
    out = capsys.readouterr().out
    assert rc == 0
    # 2 data lines + 1 header line = 3
    data_lines = [line for line in out.splitlines() if sid in line]
    assert len(data_lines) == 2
