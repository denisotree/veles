"""M121c part 2: skill suggester surfaces pattern detector clusters
into the `insights` table."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.skill_suggester import (
    SKILL_SUGGESTION_CATEGORY,
    surface_skill_suggestions,
)
from veles.core.tools.persistence import record_use, upsert_tool
from veles.core.tools.registry import ToolEntry
from veles.modules import register_embedding_adapter, reset_embedding_adapter


@pytest.fixture(autouse=True)
def _isolate_embedding_registry():
    reset_embedding_adapter()
    yield
    reset_embedding_adapter()


class _GroupingEmbedding:
    """Bag-of-keywords stub: sessions with overlapping tool names get high
    cosine, so near-duplicate sequences cluster. Mirrors test_pattern_semantic."""

    name = "stub-grouping"
    dim = 4
    _VOCAB = ("wiki", "read", "write", "search")

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            low = text.lower()
            vec = [1.0 if kw in low else 0.0 for kw in self._VOCAB]
            if not any(vec):
                vec[0] = 0.1
            out.append(vec)
        return out


def _entry(name: str) -> ToolEntry:
    return ToolEntry(
        name=name,
        description=f"tool {name}",
        parameter_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda **_kw: "",
        is_async=False,
    )


def _seed_session(conn, session_id: str, sequence: list[str], base_time: float = 100.0) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sessions(id, created_at, last_activity_at) VALUES (?, ?, ?)",
        (session_id, base_time, base_time + len(sequence)),
    )
    for i, tool_name in enumerate(sequence):
        record_use(
            conn,
            tool_name=tool_name,
            ok=True,
            latency_ms=10,
            session_id=session_id,
            now=base_time + i,
        )


@pytest.fixture()
def conn(tmp_path: Path):
    store = SessionStore(tmp_path / "memory.db")
    for name in ("wiki_search", "wiki_read_page", "read_file", "write_file"):
        upsert_tool(store._conn, _entry(name))
    yield store._conn
    store._conn.close()


# ---- nothing to surface ----


def test_no_patterns_returns_empty(conn) -> None:
    assert surface_skill_suggestions(conn) == []


def test_below_threshold_returns_empty(conn) -> None:
    seq = ["wiki_search", "wiki_read_page"]
    _seed_session(conn, "s1", seq, base_time=100.0)
    _seed_session(conn, "s2", seq, base_time=200.0)
    # Only 2 reps; threshold=3 default → nothing
    assert surface_skill_suggestions(conn) == []


# ---- happy path ----


def test_repeated_sequence_surfaced_as_insight(conn) -> None:
    seq = ["wiki_search", "wiki_read_page"]
    for i, sid in enumerate(["s1", "s2", "s3"]):
        _seed_session(conn, sid, seq, base_time=100.0 + i)

    fresh = surface_skill_suggestions(conn, now=500.0)
    assert len(fresh) == 1
    assert fresh[0].tools == ("wiki_search", "wiki_read_page")
    # Insight row landed with the expected category and title pattern
    row = conn.execute(
        "SELECT title, body, category FROM insights WHERE category = ?",
        (SKILL_SUGGESTION_CATEGORY,),
    ).fetchone()
    assert row is not None
    assert "wiki_search" in row["title"]
    assert "wiki_read_page" in row["title"]
    assert row["category"] == SKILL_SUGGESTION_CATEGORY
    # Body has the human-readable rendering
    assert "3 times" in row["body"]
    assert "wiki_search → wiki_read_page" in row["body"]


def test_idempotent_on_repeated_runs(conn) -> None:
    """Running the suggester twice on the same data shouldn't double
    the insight rows — dedup by title."""
    seq = ["wiki_search", "wiki_read_page"]
    for i, sid in enumerate(["s1", "s2", "s3"]):
        _seed_session(conn, sid, seq, base_time=100.0 + i)

    first = surface_skill_suggestions(conn, now=500.0)
    second = surface_skill_suggestions(conn, now=600.0)
    assert len(first) == 1
    assert second == []
    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM insights WHERE category = ?",
        (SKILL_SUGGESTION_CATEGORY,),
    ).fetchone()
    assert rows["n"] == 1


def test_two_distinct_clusters_both_surface(conn) -> None:
    seq_a = ["wiki_search", "wiki_read_page"]
    seq_b = ["read_file", "write_file"]
    for i in range(3):
        _seed_session(conn, f"a{i}", seq_a, base_time=100.0 + i)
    for i in range(3):
        _seed_session(conn, f"b{i}", seq_b, base_time=500.0 + i)

    fresh = surface_skill_suggestions(conn, now=1000.0)
    assert len(fresh) == 2
    titles = [
        r["title"]
        for r in conn.execute(
            "SELECT title FROM insights WHERE category = ?",
            (SKILL_SUGGESTION_CATEGORY,),
        ).fetchall()
    ]
    assert any("wiki_search" in t for t in titles)
    assert any("read_file" in t for t in titles)


def test_new_cluster_surfaces_after_existing(conn) -> None:
    """After surfacing cluster A, when cluster B appears it surfaces
    on the next pass without re-surfacing A."""
    seq_a = ["wiki_search", "wiki_read_page"]
    for i in range(3):
        _seed_session(conn, f"a{i}", seq_a, base_time=100.0 + i)
    first = surface_skill_suggestions(conn, now=500.0)
    assert len(first) == 1

    seq_b = ["read_file", "write_file"]
    for i in range(3):
        _seed_session(conn, f"b{i}", seq_b, base_time=500.0 + i)
    second = surface_skill_suggestions(conn, now=1000.0)
    assert len(second) == 1
    # Only one new insight row was added in the second pass.
    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM insights WHERE category = ?",
        (SKILL_SUGGESTION_CATEGORY,),
    ).fetchone()
    assert rows["n"] == 2


def test_body_includes_sample_sessions(conn) -> None:
    seq = ["wiki_search", "wiki_read_page"]
    for i, sid in enumerate(["sess-A", "sess-B", "sess-C"]):
        _seed_session(conn, sid, seq, base_time=100.0 + i)

    surface_skill_suggestions(conn, now=500.0)
    body = conn.execute(
        "SELECT body FROM insights WHERE category = ?",
        (SKILL_SUGGESTION_CATEGORY,),
    ).fetchone()["body"]
    # Sample sessions listed
    assert "sess-C" in body  # most recent
    assert "sess-B" in body


def test_body_proposes_skill_name(conn) -> None:
    seq = ["wiki_search", "wiki_read_page"]
    for i, sid in enumerate(["s1", "s2", "s3"]):
        _seed_session(conn, sid, seq, base_time=100.0 + i)

    surface_skill_suggestions(conn, now=500.0)
    body = conn.execute(
        "SELECT body FROM insights WHERE category = ?",
        (SKILL_SUGGESTION_CATEGORY,),
    ).fetchone()["body"]
    # `suggest_skill_name` produces a kebab-case name
    assert "wiki-search" in body


# ---- M121b2: embedding-aware path wired into the suggester ----


def test_semantic_path_merges_near_duplicate_sequences(conn) -> None:
    """With an embedding adapter registered, the suggester routes through
    `detect_patterns_semantic`: near-duplicate sequences (same intent, extra
    tool) merge into ONE suggestion that the exact-token detector would have
    split (3 + 2 → dropped) below the threshold."""
    register_embedding_adapter(_GroupingEmbedding())
    seq_a = ["wiki_search", "wiki_read_page"]
    seq_b = ["wiki_search", "read_file", "wiki_read_page"]
    for i, sid in enumerate(["a1", "a2", "a3"]):
        _seed_session(conn, sid, seq_a, base_time=100.0 + i)
    for i, sid in enumerate(["b1", "b2"]):
        _seed_session(conn, sid, seq_b, base_time=200.0 + i)

    # similarity_threshold default (0.85) — the grouping stub gives these
    # overlapping bags high cosine, so they merge into one 5-member cluster.
    fresh = surface_skill_suggestions(conn, now=500.0)
    assert len(fresh) == 1
    assert fresh[0].repetitions == 5
    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM insights WHERE category = ?",
        (SKILL_SUGGESTION_CATEGORY,),
    ).fetchone()
    assert rows["n"] == 1


def test_no_adapter_falls_back_to_token_path(conn) -> None:
    """Without an adapter the suggester still works (semantic detector
    transparently delegates to the exact-token detector)."""
    seq = ["wiki_search", "wiki_read_page"]
    for i, sid in enumerate(["s1", "s2", "s3"]):
        _seed_session(conn, sid, seq, base_time=100.0 + i)
    fresh = surface_skill_suggestions(conn, now=500.0)
    assert len(fresh) == 1
    assert fresh[0].tools == ("wiki_search", "wiki_read_page")
