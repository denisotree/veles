"""M140: the `insights` SQL table becomes a first-class recall source, and
recall hits age the rows via `last_referenced_at`.

Units under test:
  - `SessionStore.search_insights(query, limit)` — FTS5 MATCH over insights.
  - `SessionStore.touch_insights(ids, at)` — bump `last_referenced_at`.
  - `MemoryRouter._collect_insights` + recall fan-out + SQL/wiki de-dup.
"""

from __future__ import annotations

import time
from pathlib import Path

from veles.core.memory import SessionStore
from veles.core.project import init_project


def _insert_insight(
    store: SessionStore, *, title: str, body: str, category: str = "curated-session"
) -> int:
    cur = store._conn.execute(
        "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, ?, ?)",
        (title, body, category, time.time()),
    )
    store._conn.commit()
    return int(cur.lastrowid or 0)


# ---- search_insights ----


def test_search_insights_matches_body(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        _insert_insight(store, title="deploy flow", body="run terraform apply after migration")
        _insert_insight(store, title="lunch", body="unrelated note about sandwiches")
        hits = store.search_insights("terraform", limit=5)
    finally:
        store.close()
    assert [h.title for h in hits] == ["deploy flow"]


def test_search_insights_carries_ts(tmp_path: Path) -> None:
    """ts is coalesce(last_referenced_at, created_at) — created_at until the
    first reference, then the last reference time (M141 recency input)."""
    store = SessionStore(tmp_path / "m.db")
    try:
        iid = _insert_insight(store, title="t", body="recency probe")
        created = store._conn.execute(
            "SELECT created_at FROM insights WHERE id=?", (iid,)
        ).fetchone()[0]
        hit_before = store.search_insights("recency probe", limit=1)[0]
        assert hit_before.ts == created  # no reference yet → created_at
        store.touch_insights([iid], created + 1000.0)
        hit_after = store.search_insights("recency probe", limit=1)[0]
    finally:
        store.close()
    assert hit_after.ts == created + 1000.0  # now → last_referenced_at


def test_search_insights_excludes_superseded(tmp_path: Path) -> None:
    """M142: an insight linked as superseded (a `from_insight_id` in
    `insight_refs`) must not surface in recall — only the canonical does."""
    store = SessionStore(tmp_path / "m.db")
    try:
        canonical = _insert_insight(
            store, title="canonical", body="redis ttl 300 seconds session keys"
        )
        dup = _insert_insight(
            store, title="duplicate", body="redis ttl 300 seconds session keys"
        )
        store._conn.execute(
            "INSERT INTO insight_refs(from_insight_id, to_insight_id) VALUES (?, ?)",
            (dup, canonical),
        )
        store._conn.commit()
        hits = store.search_insights("redis ttl session", limit=5)
    finally:
        store.close()
    ids = [h.id for h in hits]
    assert canonical in ids
    assert dup not in ids


def test_search_insights_empty_query(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        _insert_insight(store, title="x", body="y")
        assert store.search_insights("   ", limit=5) == []
    finally:
        store.close()


# ---- touch_insights ----


def test_touch_insights_sets_last_referenced_at(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        iid = _insert_insight(store, title="t", body="b")
        before = store._conn.execute(
            "SELECT last_referenced_at FROM insights WHERE id=?", (iid,)
        ).fetchone()[0]
        assert before is None
        store.touch_insights([iid], 12345.0)
        after = store._conn.execute(
            "SELECT last_referenced_at FROM insights WHERE id=?", (iid,)
        ).fetchone()[0]
    finally:
        store.close()
    assert after == 12345.0


# ---- router integration ----


def test_recall_surfaces_insight_via_sql_path(tmp_path: Path) -> None:
    """Insight reaches recall through the SQL source even with no wiki pages."""
    from veles.core.memory.router import MemoryRouter

    project = init_project(tmp_path / "p", name="p")
    store = SessionStore(project.memory_db_path)
    try:
        _insert_insight(
            store, title="ratelimit fix", body="bump nginx worker_connections to 4096"
        )
        hits = MemoryRouter(project, store=store).recall("worker_connections nginx", limit=5)
        summaries = " ".join(h.summary for h in hits)
        # last_referenced_at must have advanced as a side effect of recall
        ref = store._conn.execute(
            "SELECT last_referenced_at FROM insights WHERE title='ratelimit fix'"
        ).fetchone()[0]
    finally:
        store.close()
    assert "worker_connections" in summaries
    assert ref is not None


def test_recall_dedupes_sql_and_wiki(tmp_path: Path) -> None:
    """An insight present both as a wiki page and a SQL row appears once."""
    from veles.core.memory.router import MemoryRouter
    from veles.core.wiki import Wiki

    project = init_project(tmp_path / "p", name="p")
    wiki = Wiki(project.wiki_root)
    wiki.write_page(
        category="insights",
        slug="cache-ttl",
        title="cache ttl policy",
        content="# cache ttl policy\n\nset redis ttl to 300 seconds for session keys\n",
    )
    wiki.reindex_if_stale()
    store = SessionStore(project.memory_db_path)
    try:
        _insert_insight(
            store, title="cache ttl policy", body="set redis ttl to 300 seconds for session keys"
        )
        hits = MemoryRouter(project, store=store).recall("redis ttl session", limit=5)
    finally:
        store.close()
    titles = [h.title for h in hits]
    assert titles.count("cache ttl policy") == 1
