"""M58 — SessionStore.search_turns + FTS5 trigger sync + v1→v2 migration."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.provider import Message


@pytest.fixture()
def store() -> SessionStore:
    return SessionStore(":memory:")


def _seed(
    store: SessionStore,
    *,
    role: str,
    content: str,
    session: str | None = None,
) -> tuple[str, int]:
    sid = session or store.create_session()
    seq = store.append_turn(sid, Message(role=role, content=content))
    return sid, seq


# ---- triggers + basic insert ----


def test_insert_propagates_to_fts(store: SessionStore) -> None:
    _seed(store, role="user", content="please grep for cosine similarity")
    hits = store.search_turns("cosine")
    assert len(hits) == 1
    assert "cosine" in hits[0].content


def test_delete_session_propagates_through_cascade_and_triggers(
    store: SessionStore,
) -> None:
    sid, _ = _seed(store, role="user", content="quaternion algebra notes")
    assert store.search_turns("quaternion")
    assert store.delete_session(sid) is True
    assert store.search_turns("quaternion") == []


def test_update_propagates_to_fts() -> None:
    store = SessionStore(":memory:")
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="old payload alpha"))
    assert store.search_turns("alpha")
    # In-place rewrite using the underlying connection — exercises the
    # `turns_au` trigger that the public API doesn't normally trip.
    store._conn.execute(
        "UPDATE turns SET content = ? WHERE session_id = ?",
        ("new payload beta", sid),
    )
    assert store.search_turns("alpha") == []
    assert store.search_turns("beta")


# ---- role_filter ----


def test_default_role_filter_excludes_tool(store: SessionStore) -> None:
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="please dump the magic config"))
    store.append_turn(sid, Message(role="tool", content="magic config payload secret"))
    hits = store.search_turns("magic")
    assert [h.role for h in hits] == ["user"]


def test_role_filter_user_only(store: SessionStore) -> None:
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="frobulate"))
    store.append_turn(sid, Message(role="assistant", content="frobulating now"))
    hits = store.search_turns("frobulate", role_filter=("user",))
    assert [h.role for h in hits] == ["user"]


def test_role_filter_none_includes_every_role(store: SessionStore) -> None:
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="grommit"))
    store.append_turn(sid, Message(role="tool", content="grommit-tool-output"))
    hits = store.search_turns("grommit", role_filter=None)
    roles = {h.role for h in hits}
    assert "user" in roles
    assert "tool" in roles


# ---- since filter ----


def test_since_filter_drops_old_turns() -> None:
    store = SessionStore(":memory:")
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="ancient unique-token-xyz"))
    # Backdate the row by 30 days via direct SQL — public API only writes now().
    old_ts = time.time() - 30 * 86400
    store._conn.execute(
        "UPDATE turns SET created_at = ? WHERE session_id = ?", (old_ts, sid)
    )
    # since=7d ago → should miss it.
    cutoff = time.time() - 7 * 86400
    hits = store.search_turns("unique-token-xyz", since=cutoff)
    assert hits == []
    # No since → still hits.
    assert store.search_turns("unique-token-xyz")


# ---- edge cases ----


def test_empty_query_returns_empty(store: SessionStore) -> None:
    assert store.search_turns("") == []
    assert store.search_turns("   ") == []


def test_search_turns_preserves_bm25_ordering(store: SessionStore) -> None:
    sid = store.create_session()
    # Higher term frequency should rank first.
    store.append_turn(
        sid, Message(role="user", content="alpha alpha alpha sometext")
    )
    store.append_turn(sid, Message(role="user", content="alpha one mention"))
    hits = store.search_turns("alpha")
    assert len(hits) == 2
    # The dense match should rank first (lower BM25 rank value).
    assert hits[0].rank <= hits[1].rank
    assert "alpha alpha alpha" in hits[0].content


def test_search_turns_handles_quotes_in_query(store: SessionStore) -> None:
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content='said "hello" to the tool'))
    hits = store.search_turns('"hello"')
    assert len(hits) == 1


def test_search_turns_limit(store: SessionStore) -> None:
    sid = store.create_session()
    for _ in range(15):
        store.append_turn(sid, Message(role="user", content="repeatedword"))
    hits = store.search_turns("repeatedword", limit=3)
    assert len(hits) == 3


# ---- migration ----


def test_migration_from_v1_backfills_existing_rows(tmp_path: Path) -> None:
    """Open a fresh DB, downgrade user_version to 1, add raw turns without FTS, reopen."""
    db = tmp_path / "memory.db"
    # Step 1: create a v2-shaped DB so all tables/triggers exist.
    s = SessionStore(db)
    sid = s.create_session()
    s.close()

    # Step 2: simulate a "legacy" v1 DB — drop FTS + triggers + downgrade pragma.
    raw = sqlite3.connect(str(db), isolation_level=None)
    raw.executescript(
        "DROP TRIGGER IF EXISTS turns_ai;"
        "DROP TRIGGER IF EXISTS turns_ad;"
        "DROP TRIGGER IF EXISTS turns_au;"
        "DROP TABLE IF EXISTS turns_fts;"
        "PRAGMA user_version = 1;"
    )
    raw.execute(
        "INSERT INTO turns (session_id, seq, role, content, created_at)"
        " VALUES (?, 0, 'user', 'legacy-needle in v1 DB', ?)",
        (sid, time.time()),
    )
    raw.close()

    # Step 3: reopen with the M58 store — migration should backfill the row.
    s2 = SessionStore(db)
    user_version = s2._conn.execute("PRAGMA user_version").fetchone()[0]
    # M119 bumped schema to 3; the v1 → v2 FTS backfill still runs first
    # as part of the chained migration, this test verifies both steps land.
    assert user_version == 3
    hits = s2.search_turns("legacy-needle")
    assert len(hits) == 1
    s2.close()


def test_idempotent_reopen_does_not_double_index(tmp_path: Path) -> None:
    db = tmp_path / "memory.db"
    s = SessionStore(db)
    sid = s.create_session()
    s.append_turn(sid, Message(role="user", content="single occurrence please"))
    s.close()

    # Reopen — migration should no-op since user_version is already 2.
    s2 = SessionStore(db)
    hits = s2.search_turns("single")
    assert len(hits) == 1
    s2.close()
