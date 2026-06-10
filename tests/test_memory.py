"""Unit tests for veles.core.memory.SessionStore — no LLM required."""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest

from veles.core.memory import SessionStore
from veles.core.provider import Message, ToolCall


@pytest.fixture
def store() -> Iterator[SessionStore]:
    s = SessionStore(":memory:")
    yield s
    s.close()


def test_orphan_session_model_overrides_table_is_dropped(tmp_path) -> None:
    """M127-removal: an old DB carrying the retired `session_model_overrides`
    table has it dropped when SessionStore re-opens the file."""
    import sqlite3

    db = tmp_path / "memory.db"
    SessionStore(db).close()  # create schema
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS session_model_overrides "
        "(session_id TEXT PRIMARY KEY, model TEXT)"
    )
    conn.execute(
        "INSERT INTO session_model_overrides VALUES ('s1', 'anthropic/claude-haiku-4.5')"
    )
    conn.commit()
    conn.close()

    SessionStore(db).close()  # re-open → drop

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='session_model_overrides'"
        ).fetchall()
    finally:
        conn.close()
    assert rows == []


def test_busy_timeout_set_on_disk_store(tmp_path) -> None:
    """M108: file-backed SessionStore configures busy_timeout=5000 so
    concurrent writers (CLI + daemon on the same memory.db) don't
    immediately raise OperationalError on transient lock contention."""
    db_path = tmp_path / "memory.db"
    s = SessionStore(db_path)
    try:
        row = s._conn.execute("PRAGMA busy_timeout").fetchone()
        assert row[0] == 5000
    finally:
        s.close()


def test_create_session_returns_unique_ids(store: SessionStore) -> None:
    a = store.create_session()
    b = store.create_session()
    assert a != b
    assert len(a) == 19  # 10 timestamp + 1 dash + 8 hex


def test_append_turn_assigns_sequential_seq(store: SessionStore) -> None:
    sid = store.create_session()
    s0 = store.append_turn(sid, Message(role="user", content="hi"))
    s1 = store.append_turn(sid, Message(role="assistant", content="hello"))
    s2 = store.append_turn(sid, Message(role="user", content="how are you"))
    assert (s0, s1, s2) == (0, 1, 2)


def test_load_messages_roundtrip(store: SessionStore) -> None:
    sid = store.create_session()
    msgs = [
        Message(role="system", content="be helpful"),
        Message(role="user", content="run ls"),
        Message(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(id="call_1", name="run_shell", arguments={"command": "ls"}),
            ],
        ),
        Message(role="tool", content="file.txt\n", tool_call_id="call_1"),
        Message(role="assistant", content="Found file.txt"),
    ]
    for m in msgs:
        store.append_turn(sid, m)
    loaded = store.load_messages(sid)
    assert len(loaded) == len(msgs)
    for actual, expected in zip(loaded, msgs, strict=True):
        assert actual.role == expected.role
        assert actual.content == expected.content
        assert actual.tool_call_id == expected.tool_call_id
        assert len(actual.tool_calls) == len(expected.tool_calls)
        for ac, ec in zip(actual.tool_calls, expected.tool_calls, strict=True):
            assert ac.id == ec.id
            assert ac.name == ec.name
            assert ac.arguments == ec.arguments


def test_sessions_isolated(store: SessionStore) -> None:
    a = store.create_session()
    b = store.create_session()
    store.append_turn(a, Message(role="user", content="A-msg"))
    store.append_turn(b, Message(role="user", content="B-msg"))
    assert [m.content for m in store.load_messages(a)] == ["A-msg"]
    assert [m.content for m in store.load_messages(b)] == ["B-msg"]


def test_list_sessions_orders_by_last_activity_desc(store: SessionStore) -> None:
    a = store.create_session()
    time.sleep(0.01)
    b = store.create_session()
    time.sleep(0.01)
    store.append_turn(a, Message(role="user", content="updates a"))
    sessions = store.list_sessions()
    assert sessions[0].id == a  # a's last_activity moved to now
    assert sessions[1].id == b


def test_delete_session_cascades_turns(store: SessionStore) -> None:
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="hi"))
    assert store.delete_session(sid) is True
    assert store.get_session(sid) is None
    n = store._conn.execute(
        "SELECT COUNT(*) AS n FROM turns WHERE session_id=?", (sid,)
    ).fetchone()["n"]
    assert n == 0


def test_delete_session_returns_false_when_missing(store: SessionStore) -> None:
    assert store.delete_session("nonexistent") is False


def test_list_sessions_since_filters_and_orders_ascending(store: SessionStore) -> None:
    a = store.create_session()
    time.sleep(0.01)
    b = store.create_session()
    time.sleep(0.01)
    c = store.create_session()
    store.append_turn(a, Message(role="user", content="a"))
    cursor_after_a = store.get_session(a).last_activity_at  # type: ignore[union-attr]
    time.sleep(0.01)
    store.append_turn(b, Message(role="user", content="b"))
    time.sleep(0.01)
    store.append_turn(c, Message(role="user", content="c"))

    fresh = store.list_sessions_since(cursor_after_a)
    assert [s.id for s in fresh] == [b, c]
    assert fresh[0].last_activity_at < fresh[1].last_activity_at
    assert store.list_sessions_since(cursor_after_a, limit=1) == fresh[:1]


def test_parent_session_id_set_null_on_parent_delete(store: SessionStore) -> None:
    parent = store.create_session()
    child = store.create_session(parent_session_id=parent)
    store.delete_session(parent)
    row = store._conn.execute(
        "SELECT parent_session_id FROM sessions WHERE id=?", (child,)
    ).fetchone()
    assert row["parent_session_id"] is None


def test_get_session_returns_none_for_missing(store: SessionStore) -> None:
    assert store.get_session("nonexistent-id") is None


def test_session_exists_true_for_created_false_for_missing(
    store: SessionStore,
) -> None:
    sid = store.create_session()
    assert store.session_exists(sid) is True
    assert store.session_exists("nonexistent-sid") is False
    store.delete_session(sid)
    assert store.session_exists(sid) is False


def test_user_version_matches_schema_version(store: SessionStore) -> None:
    """M58 bumped the schema from v1 to v2 (turns_fts FTS5 + triggers)."""
    from veles.core.memory import _SCHEMA_VERSION

    v = store._conn.execute("PRAGMA user_version").fetchone()[0]
    assert v == _SCHEMA_VERSION


def test_set_title(store: SessionStore) -> None:
    sid = store.create_session()
    store.set_title(sid, "Magic Word Demo")
    info = store.get_session(sid)
    assert info is not None
    assert info.title == "Magic Word Demo"


def test_wal_mode_enabled(tmp_path) -> None:
    s = SessionStore(tmp_path / "test.db")
    try:
        mode = s._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        s.close()


def test_db_path_creates_parent_dirs(tmp_path) -> None:
    db_path = tmp_path / "deep" / "nested" / "memory.db"
    s = SessionStore(db_path)
    try:
        s.create_session()
        assert db_path.exists()
    finally:
        s.close()
