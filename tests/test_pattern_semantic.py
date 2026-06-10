"""detect_patterns_semantic — embedding-aware variant with
token-based fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.skill_pattern_detector import (
    detect_patterns,
    detect_patterns_semantic,
)
from veles.core.tools.persistence import record_use, upsert_tool
from veles.core.tools.registry import ToolEntry
from veles.modules import (
    register_embedding_adapter,
    reset_embedding_adapter,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    reset_embedding_adapter()
    yield
    reset_embedding_adapter()


@pytest.fixture()
def conn(tmp_path: Path):
    store = SessionStore(tmp_path / "memory.db")
    for name in ("wiki_search", "wiki_read_page", "read_file", "write_file"):
        upsert_tool(store._conn, _entry(name))
    yield store._conn
    store._conn.close()


def _entry(name: str) -> ToolEntry:
    return ToolEntry(
        name=name,
        description=f"tool {name}",
        parameter_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda **_kw: "",
        is_async=False,
    )


def _seed_session(conn, sid: str, seq: list[str], base_time: float = 100.0) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sessions(id, created_at, last_activity_at) VALUES (?, ?, ?)",
        (sid, base_time, base_time + len(seq)),
    )
    for i, name in enumerate(seq):
        record_use(
            conn,
            tool_name=name,
            ok=True,
            latency_ms=10,
            session_id=sid,
            now=base_time + i,
        )


class _GroupingEmbedding:
    """Stub: vectors derived from sequence-token bag of words.
    Sessions with overlapping tool sets get high cosine; disjoint
    sets get low cosine. Lets us assert clustering behaviour."""

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


# ---- fallback path ----


def test_no_adapter_delegates_to_token_detector(conn) -> None:
    seq = ["wiki_search", "wiki_read_page"]
    for i in range(3):
        _seed_session(conn, f"s{i}", seq, base_time=100.0 + i)

    sem = detect_patterns_semantic(conn, min_repetitions=3)
    tok = detect_patterns(conn, min_repetitions=3)
    # Same result when fallback path is hit
    assert len(sem) == len(tok)
    if sem:
        assert sem[0].tools == tok[0].tools
        assert sem[0].repetitions == tok[0].repetitions


def test_empty_tool_uses_returns_empty(conn) -> None:
    register_embedding_adapter(_GroupingEmbedding())
    assert detect_patterns_semantic(conn) == []


# ---- semantic clustering ----


def test_near_duplicate_sequences_cluster_together(conn) -> None:
    """Token-based detector misses `(wiki_search, wiki_read_page)` vs
    `(wiki_search, read_file, wiki_read_page)` — different tuples.
    Semantic clusters them because their tool-name bag overlaps."""
    register_embedding_adapter(_GroupingEmbedding())
    seq_a = ["wiki_search", "wiki_read_page"]
    seq_b = ["wiki_search", "read_file", "wiki_read_page"]

    # 3 sessions of A + 2 sessions of B → 5-member cluster with
    # similarity threshold low enough to merge them
    for i, sid in enumerate(["a1", "a2", "a3"]):
        _seed_session(conn, sid, seq_a, base_time=100.0 + i)
    for i, sid in enumerate(["b1", "b2"]):
        _seed_session(conn, sid, seq_b, base_time=200.0 + i)

    patterns = detect_patterns_semantic(
        conn, min_repetitions=3, similarity_threshold=0.5
    )
    # The cluster has 5 members total — would be invisible to the
    # token detector at min_repetitions=3 if treated as separate
    # clusters (a-cluster=3, b-cluster=2, b would be dropped).
    # Semantic merges → one cluster with 5 reps.
    assert len(patterns) == 1
    assert patterns[0].repetitions == 5


def test_strict_threshold_keeps_clusters_separate(conn) -> None:
    """High threshold (0.99) means even small variant differences
    keep clusters apart — behaviour close to token-based detector."""
    register_embedding_adapter(_GroupingEmbedding())
    seq_a = ["wiki_search", "wiki_read_page"]
    seq_b = ["read_file", "write_file"]
    for i, sid in enumerate(["a1", "a2", "a3"]):
        _seed_session(conn, sid, seq_a, base_time=100.0 + i)
    for i, sid in enumerate(["b1", "b2", "b3"]):
        _seed_session(conn, sid, seq_b, base_time=200.0 + i)
    patterns = detect_patterns_semantic(
        conn, min_repetitions=3, similarity_threshold=0.99
    )
    # Two distinct clusters
    assert len(patterns) == 2


def test_canonical_tools_is_most_frequent_sequence(conn) -> None:
    """When a cluster contains variants `(a,b)` ×3 and `(a,b,c)` ×1,
    the surfaced Pattern.tools is the more common one."""
    register_embedding_adapter(_GroupingEmbedding())
    short = ["wiki_search", "wiki_read_page"]
    long = ["wiki_search", "read_file", "wiki_read_page"]
    for i, sid in enumerate(["s1", "s2", "s3", "s4"]):
        _seed_session(conn, sid, short, base_time=100.0 + i)
    _seed_session(conn, "long1", long, base_time=200.0)

    patterns = detect_patterns_semantic(
        conn, min_repetitions=3, similarity_threshold=0.5
    )
    assert len(patterns) == 1
    # Most-frequent variant wins as the canonical tuple
    assert patterns[0].tools == tuple(short)


# ---- error handling ----


def test_adapter_failure_falls_back(conn) -> None:
    from veles.modules import EmbeddingError

    class _Flaky:
        name = "flaky"
        dim = 4

        def embed(self, texts):
            raise EmbeddingError("boom")

    register_embedding_adapter(_Flaky())
    seq = ["wiki_search", "wiki_read_page"]
    for i in range(3):
        _seed_session(conn, f"s{i}", seq, base_time=100.0 + i)
    # Should not raise; falls back to token-based
    patterns = detect_patterns_semantic(conn, min_repetitions=3)
    assert len(patterns) == 1
    assert patterns[0].repetitions == 3
