"""M121b: pattern detector — token-based clustering of tool-call
sequences across sessions."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.skill_pattern_detector import (
    Pattern,
    detect_patterns,
    suggest_skill_name,
)
from veles.core.tools.persistence import record_use, upsert_tool
from veles.core.tools.registry import ToolEntry


def _entry(name: str) -> ToolEntry:
    return ToolEntry(
        name=name,
        description=f"tool {name}",
        parameter_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda **_kw: "",
        is_async=False,
    )


def _seed_session(conn, session_id: str, sequence: list[tuple[str, bool]],
                  base_time: float = 100.0) -> None:
    """Create a session row + tool_uses rows for the given sequence."""
    conn.execute(
        "INSERT OR IGNORE INTO sessions(id, created_at, last_activity_at) VALUES (?, ?, ?)",
        (session_id, base_time, base_time + len(sequence)),
    )
    for i, (tool_name, ok) in enumerate(sequence):
        record_use(
            conn,
            tool_name=tool_name,
            ok=ok,
            latency_ms=10,
            session_id=session_id,
            now=base_time + i,
        )


@pytest.fixture()
def conn(tmp_path: Path):
    store = SessionStore(tmp_path / "memory.db")
    # Seed a handful of tools used across the tests
    for name in ("wiki_search", "wiki_read_page", "fetch_url", "read_file", "write_file"):
        upsert_tool(store._conn, _entry(name))
    yield store._conn
    store._conn.close()


# ---- empty / threshold edge cases ----


def test_no_tool_uses_returns_empty(conn) -> None:
    assert detect_patterns(conn) == []


def test_single_session_not_enough(conn) -> None:
    _seed_session(conn, "s1", [("wiki_search", True), ("wiki_read_page", True)])
    assert detect_patterns(conn, min_repetitions=3) == []


def test_below_threshold_returns_empty(conn) -> None:
    """Two sessions with the same sequence, min_repetitions=3 → nothing."""
    seq = [("wiki_search", True), ("wiki_read_page", True)]
    _seed_session(conn, "s1", seq, base_time=100.0)
    _seed_session(conn, "s2", seq, base_time=200.0)
    assert detect_patterns(conn, min_repetitions=3) == []


def test_single_call_session_excluded(conn) -> None:
    """Sessions with one tool-call don't form a meaningful process."""
    for sid, t in [("s1", 100.0), ("s2", 200.0), ("s3", 300.0)]:
        _seed_session(conn, sid, [("read_file", True)], base_time=t)
    # min_calls=2 default — these are all single-call sessions
    assert detect_patterns(conn) == []


# ---- happy path ----


def test_three_repetitions_detected(conn) -> None:
    seq = [("wiki_search", True), ("wiki_read_page", True)]
    for sid, t in [("s1", 100.0), ("s2", 200.0), ("s3", 300.0)]:
        _seed_session(conn, sid, seq, base_time=t)
    patterns = detect_patterns(conn, min_repetitions=3)
    assert len(patterns) == 1
    p = patterns[0]
    assert p.tools == ("wiki_search", "wiki_read_page")
    assert p.repetitions == 3


def test_sample_sessions_sorted_recent_first(conn) -> None:
    """The sample carries the most recent session_ids first so the
    suggestion UI can show 'you ran this in session X just now'."""
    seq = [("wiki_search", True), ("wiki_read_page", True)]
    _seed_session(conn, "s_old", seq, base_time=100.0)
    _seed_session(conn, "s_mid", seq, base_time=200.0)
    _seed_session(conn, "s_new", seq, base_time=300.0)
    patterns = detect_patterns(conn, min_repetitions=3, sample_size=2)
    assert patterns[0].sample_sessions == ("s_new", "s_mid")


def test_multiple_clusters_sorted_by_repetition_count(conn) -> None:
    """Two distinct sequences — the more-repeated one first."""
    seq_a = [("wiki_search", True), ("wiki_read_page", True)]
    seq_b = [("read_file", True), ("write_file", True)]
    # cluster A: 4 reps; cluster B: 3 reps
    for i in range(4):
        _seed_session(conn, f"a{i}", seq_a, base_time=100.0 + i)
    for i in range(3):
        _seed_session(conn, f"b{i}", seq_b, base_time=500.0 + i)

    patterns = detect_patterns(conn, min_repetitions=3)
    assert len(patterns) == 2
    assert patterns[0].repetitions == 4
    assert patterns[1].repetitions == 3


def test_ok_flag_does_not_split_clusters(conn) -> None:
    """Whether a call succeeded or failed shouldn't fragment the
    cluster — the recipe is "search then read", regardless of one
    error in the middle."""
    seq_ok = [("wiki_search", True), ("wiki_read_page", True)]
    seq_err = [("wiki_search", False), ("wiki_read_page", True)]
    for i in range(3):
        _seed_session(conn, f"ok{i}", seq_ok, base_time=100.0 + i)
    for i in range(2):
        _seed_session(conn, f"err{i}", seq_err, base_time=500.0 + i)

    patterns = detect_patterns(conn, min_repetitions=3)
    # ok + err share the same tool tuple → merge into 5 reps
    assert len(patterns) == 1
    assert patterns[0].repetitions == 5


# ---- threshold tuning ----


def test_max_calls_excludes_long_sessions(conn) -> None:
    """A 20-call session is exploratory, not a recipe — skip it."""
    long_seq = [("read_file", True)] * 20
    for i in range(3):
        _seed_session(conn, f"long{i}", long_seq, base_time=100.0 + i)
    patterns = detect_patterns(conn, min_repetitions=3, max_calls=12)
    assert patterns == []


def test_min_calls_filter_respected(conn) -> None:
    """With min_calls=3, 2-call sequences shouldn't appear even when
    repeated."""
    seq = [("wiki_search", True), ("wiki_read_page", True)]
    for i in range(3):
        _seed_session(conn, f"s{i}", seq, base_time=100.0 + i)
    assert detect_patterns(conn, min_repetitions=3, min_calls=3) == []


# ---- suggest_skill_name ----


def test_suggest_skill_name_compact() -> None:
    p = Pattern(tools=("wiki_search", "wiki_read_page"), repetitions=3)
    assert suggest_skill_name(p) == "wiki-search-read-page"


def test_suggest_skill_name_handles_unrelated_prefixes() -> None:
    p = Pattern(tools=("fetch_url", "write_file"), repetitions=3)
    name = suggest_skill_name(p)
    assert "fetch-url" in name
    assert "write-file" in name


def test_suggest_skill_name_empty_pattern_safe() -> None:
    """Defensive — `tools` shouldn't be empty in practice, but
    `suggest_skill_name` must return something printable."""
    p = Pattern(tools=(), repetitions=3)
    assert suggest_skill_name(p) == "unnamed-pattern"


def test_suggest_skill_name_truncates_long() -> None:
    """Truncation kicks in around 60 chars — sequence of long names
    doesn't produce a 200-char skill name."""
    tools = tuple(f"verylongtoolname{i}" for i in range(20))
    p = Pattern(tools=tools, repetitions=3)
    name = suggest_skill_name(p)
    assert len(name) <= 60


# ---- latest_at populated ----


def test_latest_at_is_most_recent_invocation(conn) -> None:
    seq = [("wiki_search", True), ("wiki_read_page", True)]
    _seed_session(conn, "s1", seq, base_time=100.0)
    _seed_session(conn, "s2", seq, base_time=500.0)
    _seed_session(conn, "s3", seq, base_time=300.0)
    patterns = detect_patterns(conn, min_repetitions=3)
    # latest_at across the cluster = max invocation time = ~501 (s2 + last index)
    assert patterns[0].latest_at >= 500.0
