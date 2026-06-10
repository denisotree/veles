"""Tests for core/trace.py — Tier ε M68 observability baseline."""

from __future__ import annotations

import json
from pathlib import Path

from veles.core.trace import (
    DEFAULT_MAX_BYTES,
    TraceRecord,
    TraceWriter,
    cache_fragmentation_alert,
    hash_text,
    hash_tools,
    now_iso,
    read_records,
    trace_path_for_project,
)


# ---------- hashing ----------


def test_hash_text_is_deterministic() -> None:
    assert hash_text("hello") == hash_text("hello")
    assert hash_text("hello") != hash_text("world")
    assert hash_text("").startswith("sha256:")
    assert hash_text(None).startswith("sha256:")
    # empty + None hash to the same thing (both empty bytes)
    assert hash_text(None) == hash_text("")


def test_hash_tools_canonical_ordering() -> None:
    a = [{"name": "b", "x": 1}, {"name": "a", "y": 2}]
    b = [{"name": "a", "y": 2}, {"name": "b", "x": 1}]
    # Order of input list should NOT affect hash.
    assert hash_tools(a) == hash_tools(b)


def test_hash_tools_handles_openai_shape() -> None:
    native = [{"name": "foo", "description": "d"}]
    openai = [{"type": "function", "function": {"name": "foo", "description": "d"}}]
    # Shapes differ, so hashes differ — but each is stable per-shape.
    assert hash_tools(native) == hash_tools(native)
    assert hash_tools(openai) == hash_tools(openai)
    assert hash_tools(native) != hash_tools(openai)


def test_hash_tools_empty() -> None:
    assert hash_tools(None) == hash_tools([])


def test_hash_tools_key_order_insensitive() -> None:
    a = [{"name": "x", "a": 1, "b": 2}]
    b = [{"b": 2, "a": 1, "name": "x"}]
    assert hash_tools(a) == hash_tools(b)


# ---------- TraceWriter ----------


def _make_record(
    *,
    request_id: str = "req-1",
    system_prompt_hash: str | None = None,
    cache_read: int = 0,
    model: str = "anthropic/claude-sonnet-4.6",
) -> TraceRecord:
    return TraceRecord(
        request_id=request_id,
        session_id="sess-1",
        ts=now_iso(),
        provider="openrouter",
        model=model,
        system_prompt_hash=system_prompt_hash or hash_text("sys-prompt-A"),
        tool_bundle_hash=hash_tools([{"name": "read_file"}]),
        input_tokens_new=10,
        cache_read_tokens=cache_read,
        cache_creation_tokens=0,
        output_tokens=5,
        ttft_ms=100,
        total_latency_ms=200,
        est_cost_usd=0.001,
        tool_calls_count=0,
        permission_decisions=[],
        final_status="ok",
    )


def test_trace_writer_appends_lines(tmp_path: Path) -> None:
    p = tmp_path / "traces.jsonl"
    w = TraceWriter(p)
    w.write(_make_record(request_id="req-1"))
    w.write(_make_record(request_id="req-2"))
    records = read_records(p)
    assert [r["request_id"] for r in records] == ["req-1", "req-2"]


def test_trace_writer_creates_parent_dir(tmp_path: Path) -> None:
    p = tmp_path / "nested" / "deeper" / "traces.jsonl"
    w = TraceWriter(p)
    w.write(_make_record())
    assert p.exists()


def test_trace_writer_rotates_by_size(tmp_path: Path) -> None:
    p = tmp_path / "traces.jsonl"
    # Very small budget — every record forces a rotation.
    w = TraceWriter(p, max_bytes=50)
    w.write(_make_record(request_id="req-1"))
    w.write(_make_record(request_id="req-2"))
    w.write(_make_record(request_id="req-3"))
    # Active file should only carry the latest record; rotated siblings exist.
    active = read_records(p)
    rotated = list(tmp_path.glob("traces.jsonl.*"))
    assert len(active) == 1
    assert active[0]["request_id"] == "req-3"
    assert len(rotated) >= 1


def test_trace_writer_default_max_bytes_is_50mb() -> None:
    assert DEFAULT_MAX_BYTES == 50 * 1024 * 1024


def test_read_records_skips_malformed_lines(tmp_path: Path) -> None:
    p = tmp_path / "traces.jsonl"
    p.write_text('{"request_id":"ok"}\nnot json at all\n{"request_id":"also-ok"}\n')
    records = read_records(p)
    assert [r["request_id"] for r in records] == ["ok", "also-ok"]


def test_read_records_missing_file(tmp_path: Path) -> None:
    assert read_records(tmp_path / "missing.jsonl") == []


def test_record_serializes_to_expected_keys(tmp_path: Path) -> None:
    """Schema lock — PLAN.md §19.1 names these fields explicitly. If you
    rename them, downstream `jq` queries / future dashboards break.
    """
    p = tmp_path / "traces.jsonl"
    w = TraceWriter(p)
    w.write(_make_record())
    row = json.loads(p.read_text().splitlines()[0])
    expected = {
        "request_id",
        "session_id",
        "ts",
        "provider",
        "model",
        "system_prompt_hash",
        "tool_bundle_hash",
        "input_tokens_new",
        "cache_read_tokens",
        "cache_creation_tokens",
        "output_tokens",
        "ttft_ms",
        "total_latency_ms",
        "est_cost_usd",
        "tool_calls_count",
        "permission_decisions",
        "final_status",
    }
    assert set(row.keys()) == expected


# ---------- cache fragmentation alert ----------


def test_alert_fires_when_streak_has_zero_cache_reads() -> None:
    h = hash_text("stable-prompt")
    records = [
        {"system_prompt_hash": h, "cache_read_tokens": 0, "model": "m1", "provider": "p1"}
        for _ in range(5)
    ]
    alert = cache_fragmentation_alert(records, min_streak=5)
    assert alert is not None
    assert alert["alert"] == "cache_fragmentation"
    assert alert["streak"] == 5


def test_alert_silent_on_short_history() -> None:
    h = hash_text("stable-prompt")
    records = [{"system_prompt_hash": h, "cache_read_tokens": 0} for _ in range(3)]
    assert cache_fragmentation_alert(records, min_streak=5) is None


def test_alert_silent_on_changing_system_prompt() -> None:
    records = [
        {"system_prompt_hash": hash_text(f"prompt-{i}"), "cache_read_tokens": 0}
        for i in range(5)
    ]
    assert cache_fragmentation_alert(records, min_streak=5) is None


def test_alert_silent_when_any_record_has_cache_reads() -> None:
    h = hash_text("stable-prompt")
    records = [
        {"system_prompt_hash": h, "cache_read_tokens": 0},
        {"system_prompt_hash": h, "cache_read_tokens": 0},
        {"system_prompt_hash": h, "cache_read_tokens": 50},  # cache hit
        {"system_prompt_hash": h, "cache_read_tokens": 0},
        {"system_prompt_hash": h, "cache_read_tokens": 0},
    ]
    assert cache_fragmentation_alert(records, min_streak=5) is None


def test_alert_considers_only_trailing_window() -> None:
    h_old = hash_text("old")
    h_new = hash_text("new")
    # Older mixed history, but the last 5 are uniform-fragmenting.
    records = (
        [{"system_prompt_hash": h_old, "cache_read_tokens": 100}]
        + [{"system_prompt_hash": h_new, "cache_read_tokens": 0} for _ in range(5)]
    )
    alert = cache_fragmentation_alert(records, min_streak=5)
    assert alert is not None
    assert alert["system_prompt_hash"] == h_new


def test_alert_reports_models_and_providers() -> None:
    h = hash_text("stable")
    records = [
        {"system_prompt_hash": h, "cache_read_tokens": 0, "model": "m1", "provider": "p1"},
        {"system_prompt_hash": h, "cache_read_tokens": 0, "model": "m2", "provider": "p1"},
        {"system_prompt_hash": h, "cache_read_tokens": 0, "model": "m1", "provider": "p1"},
        {"system_prompt_hash": h, "cache_read_tokens": 0, "model": "m1", "provider": "p1"},
        {"system_prompt_hash": h, "cache_read_tokens": 0, "model": "m2", "provider": "p1"},
    ]
    alert = cache_fragmentation_alert(records, min_streak=5)
    assert alert is not None
    assert alert["models"] == ["m1", "m2"]
    assert alert["providers"] == ["p1"]


# ---------- project path helper ----------


def test_trace_path_for_project(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    assert trace_path_for_project(state) == state / "traces.jsonl"


# ---------- now_iso shape sanity ----------


def test_now_iso_format() -> None:
    s = now_iso()
    # YYYY-MM-DDTHH:MM:SSZ
    assert len(s) == 20
    assert s.endswith("Z")
    assert s[10] == "T"
