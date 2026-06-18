"""M125: Telegram `/insights` and `/rules` text-listing commands."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.channels._telegram_commands import (
    all_command_names,
    dispatch,
    menu_descriptors,
)
from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway
from veles.core.memory import SessionStore
from veles.core.project import init_project


@pytest.fixture()
def project(tmp_path: Path):
    return init_project(tmp_path / "proj", name="proj")


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    return SessionMap.load(tmp_path / "telegram-sessions.json")


def _make_gateway(session_map: SessionMap, project_root: Path) -> TelegramGateway:
    class _NullClient:
        async def submit_run(self, prompt: str, *, session_id=None, origin=None):
            return {"run_id": "x", "session_id": session_id, "state": "running"}

        async def stream_events(self, run_id):
            if False:
                yield

    return TelegramGateway(
        bot_token="X",
        daemon_client=_NullClient(),  # type: ignore[arg-type]
        session_map=session_map,
        project_root=project_root,
    )


def _seed_insight(project, *, title: str, category: str, ts: float) -> None:
    store = SessionStore(project.memory_db_path)
    store._conn.execute(
        "INSERT INTO insights(title, body, category, created_at) VALUES (?,?,?,?)",
        (title, "x", category, ts),
    )
    store._conn.commit()
    store._conn.close()


def _seed_rule(project, *, kind: str, body: str, ts: float) -> None:
    store = SessionStore(project.memory_db_path)
    store._conn.execute(
        "INSERT INTO rules(kind, body, source, created_at) VALUES (?,?,?,?)",
        (kind, body, "test", ts),
    )
    store._conn.commit()
    store._conn.close()


# ---- /insights ----


async def test_insights_lists_rows(session_map, project) -> None:
    gateway = _make_gateway(session_map, project.root)
    _seed_insight(project, title="Auth decision", category="curated-session", ts=time.time())
    reply = await dispatch(gateway, "42", "insights", "")
    assert reply is not None
    assert "Auth decision" in reply
    assert "curated-session" in reply


async def test_insights_empty_friendly_message(session_map, project) -> None:
    gateway = _make_gateway(session_map, project.root)
    reply = await dispatch(gateway, "42", "insights", "")
    assert reply is not None
    assert "no insights" in reply.lower()


async def test_insights_filtered_by_category(session_map, project) -> None:
    now = time.time()
    _seed_insight(project, title="A", category="curated-session", ts=now - 5)
    _seed_insight(project, title="B", category="skill-suggestion", ts=now)
    gateway = _make_gateway(session_map, project.root)
    reply = await dispatch(gateway, "42", "insights", "curated-session")
    assert reply is not None
    assert "A" in reply
    assert "B" not in reply


async def test_insights_in_menu_and_commands(session_map) -> None:
    del session_map
    cmds = {d["command"] for d in menu_descriptors()}
    assert "insights" in cmds
    assert "insights" in all_command_names()


# ---- /rules ----


async def test_rules_lists_rows(session_map, project) -> None:
    gateway = _make_gateway(session_map, project.root)
    _seed_rule(project, kind="preference", body="user prefers terse responses", ts=time.time())
    reply = await dispatch(gateway, "42", "rules", "")
    assert reply is not None
    assert "terse" in reply
    assert "preference" in reply


async def test_rules_empty_friendly_message(session_map, project) -> None:
    gateway = _make_gateway(session_map, project.root)
    reply = await dispatch(gateway, "42", "rules", "")
    assert reply is not None
    assert "no rules" in reply.lower()


async def test_rules_filtered_by_kind(session_map, project) -> None:
    now = time.time()
    _seed_rule(project, kind="do", body="DO_RULE_TEXT", ts=now - 5)
    _seed_rule(project, kind="preference", body="PREF_RULE_TEXT", ts=now)
    gateway = _make_gateway(session_map, project.root)
    reply = await dispatch(gateway, "42", "rules", "do")
    assert reply is not None
    assert "DO_RULE_TEXT" in reply
    assert "PREF_RULE_TEXT" not in reply


async def test_rules_in_menu_and_commands(session_map) -> None:
    del session_map
    cmds = {d["command"] for d in menu_descriptors()}
    assert "rules" in cmds
    assert "rules" in all_command_names()


async def test_help_lists_insights_and_rules(session_map, project) -> None:
    gateway = _make_gateway(session_map, project.root)
    reply = await dispatch(gateway, "42", "help", "")
    assert reply is not None
    assert "/insights" in reply
    assert "/rules" in reply


async def test_rules_no_project_friendly_message(session_map) -> None:
    """Gateway without project_root configured surfaces friendly message
    instead of crashing — guards against unconfigured deployments."""
    gateway = _make_gateway(session_map, Path("/nonexistent/path/12345"))
    reply = await dispatch(gateway, "42", "rules", "")
    assert reply is not None
    # Either "no active project" or a db-open error — both are honest
    assert "no active project" in reply or "could not open" in reply
