"""M140: the `insights` SQL table becomes a first-class recall source, and
recall hits age the rows via `last_referenced_at`. (M161 made the SQL row
the *sole* insight store — the old wiki↔SQL title de-dup is gone.)

Units under test:
  - `SessionStore.search_insights(query, limit)` — FTS5 MATCH over insights.
  - `SessionStore.touch_insights(ids, at)` — bump `last_referenced_at`.
  - `MemoryRouter._collect_insights` + recall fan-out.
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
        dup = _insert_insight(store, title="duplicate", body="redis ttl 300 seconds session keys")
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


# ---- M218: confidence / provenance ----


def _insert_with_confidence(
    store: SessionStore, *, title: str, body: str, confidence: float
) -> int:
    cur = store._conn.execute(
        "INSERT INTO insights(title, body, category, created_at, confidence) "
        "VALUES (?, ?, ?, ?, ?)",
        (title, body, "recovery-trigger", time.time(), confidence),
    )
    store._conn.commit()
    return int(cur.lastrowid or 0)


def test_search_insights_carries_confidence(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        _insert_with_confidence(
            store, title="hedge", body="speculative caching guess", confidence=0.2
        )
        hit = store.search_insights("speculative caching", limit=1)[0]
    finally:
        store.close()
    assert hit.confidence == 0.2


def test_existing_insights_default_to_full_confidence(tmp_path: Path) -> None:
    """The additive column defaults to 1.0 so pre-M218 rows are never pruned."""
    store = SessionStore(tmp_path / "m.db")
    try:
        _insert_insight(store, title="legacy", body="pre-confidence insight row")
        hit = store.search_insights("pre-confidence", limit=1)[0]
    finally:
        store.close()
    assert hit.confidence == 1.0


def test_save_insight_row_persists_confidence(tmp_path: Path) -> None:
    from veles.core.tools.builtin.memory_save import save_insight_row

    project = init_project(tmp_path / "p", name="p")
    rid = save_insight_row(
        title="inferred",
        body="tentative recovery note",
        category="recovery-trigger",
        project=project,
        confidence=0.6,
    )
    store = SessionStore(project.memory_db_path)
    try:
        got = store._conn.execute("SELECT confidence FROM insights WHERE id=?", (rid,)).fetchone()[
            0
        ]
    finally:
        store.close()
    assert got == 0.6


def test_recall_filters_low_confidence_insight(tmp_path: Path) -> None:
    """A sub-floor insight is pruned from recall before it reaches the prompt;
    a trusted one still surfaces."""
    from veles.core.memory.router import MemoryRouter

    project = init_project(tmp_path / "p", name="p")
    store = SessionStore(project.memory_db_path)
    try:
        _insert_with_confidence(
            store, title="trusted", body="nginx worker_connections 4096 solid fix", confidence=1.0
        )
        _insert_with_confidence(
            store, title="shaky", body="nginx worker_connections 8192 wild guess", confidence=0.1
        )
        hits = MemoryRouter(project, store=store).recall("nginx worker_connections", limit=5)
    finally:
        store.close()
    titles = [h.title for h in hits]
    assert "trusted" in titles
    assert "shaky" not in titles


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
        _insert_insight(store, title="ratelimit fix", body="bump nginx worker_connections to 4096")
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


def test_recall_returns_insight_alongside_wiki_pages(tmp_path: Path) -> None:
    """M161: insights live only in SQL; wiki pages and insight rows are
    distinct sources that both surface without any title de-dup pass."""
    from veles.core.memory.router import MemoryRouter
    from veles.modules.wiki.wiki import Wiki

    project = init_project(tmp_path / "p", name="p")
    wiki = Wiki(project.wiki_root)
    wiki.write_page(
        category="concepts",
        slug="cache-design",
        title="cache design",
        content="# cache design\n\nsession keys live in redis with a ttl\n",
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
    assert "cache ttl policy" in titles
    assert "cache design" in titles
