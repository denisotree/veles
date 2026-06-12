"""Tests for core/events.py — Tier ε M69 typed event log."""

from __future__ import annotations

import json
import time as _time
from pathlib import Path

from veles.core.events import (
    DEFAULT_MAX_BYTES,
    ApprovalRequest,
    ApprovalResult,
    AssistantMessage,
    Compaction,
    ConnectorCall,
    ErrorEvent,
    EventWriter,
    PermissionDecision,
    PlanUpdate,
    ToolCall,
    ToolResult,
    UserMessage,
    events_path_for_project,
    filter_events,
    now_iso,
    read_events,
    recent_error_events,
)

# ---------- type discriminators ----------


def test_event_types_are_canonical_strings() -> None:
    """The `type` field is the only thing replayers key on. Lock it down."""
    assert UserMessage(ts="t", session_id=None, text="").type == "user_message"
    assert AssistantMessage(ts="t", session_id=None, text=None).type == "assistant_message"
    assert (
        ToolCall(ts="t", session_id=None, tool_call_id="c", name="x", arguments={}).type
        == "tool_call"
    )
    assert (
        ToolResult(ts="t", session_id=None, tool_call_id="c", name="x", output="").type
        == "tool_result"
    )
    assert (
        PermissionDecision(ts="t", session_id=None, tool_name="x", decision="allow", rule="r").type
        == "permission_decision"
    )
    assert ApprovalRequest(ts="t", session_id=None, action="x").type == "approval_request"
    assert (
        ApprovalResult(ts="t", session_id=None, action="x", status="approved").type
        == "approval_result"
    )
    assert PlanUpdate(ts="t", session_id=None, summary="x").type == "plan_update"
    assert Compaction(ts="t", session_id=None, summary="x").type == "compaction"
    assert ConnectorCall(ts="t", session_id=None, server="s", tool="t").type == "connector_call"
    assert (
        ErrorEvent(ts="t", session_id=None, where="x", error_type="E", message="m").type == "error"
    )


def test_events_are_frozen() -> None:
    ev = UserMessage(ts="t", session_id=None, text="hi")
    try:
        ev.text = "mutated"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("UserMessage should be frozen")


# ---------- EventWriter ----------


def test_writer_appends_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "events.jsonl"
    w = EventWriter(p)
    w.write(UserMessage(ts=now_iso(), session_id="s", text="hello"))
    w.write(
        AssistantMessage(
            ts=now_iso(), session_id="s", text="hi", tool_call_count=0, finish_reason="stop"
        )
    )
    events = read_events(p)
    assert [e["type"] for e in events] == ["user_message", "assistant_message"]
    assert events[0]["text"] == "hello"


def test_writer_creates_parent_dir(tmp_path: Path) -> None:
    p = tmp_path / "deep" / "deeper" / "events.jsonl"
    w = EventWriter(p)
    w.write(UserMessage(ts=now_iso(), session_id=None, text=""))
    assert p.exists()


def test_writer_rotates_by_size(tmp_path: Path) -> None:
    p = tmp_path / "events.jsonl"
    w = EventWriter(p, max_bytes=60)
    for i in range(4):
        w.write(UserMessage(ts=now_iso(), session_id="s", text=f"msg {i}"))
    rotated = list(tmp_path.glob("events.jsonl.*"))
    active = read_events(p)
    # Active file holds the most recent event; rotations exist.
    assert len(rotated) >= 1
    assert len(active) >= 1
    assert active[-1]["text"].startswith("msg")


def test_default_max_bytes_is_50mb() -> None:
    assert DEFAULT_MAX_BYTES == 50 * 1024 * 1024


def test_read_events_skips_malformed(tmp_path: Path) -> None:
    p = tmp_path / "events.jsonl"
    p.write_text('{"type":"x"}\nbroken\n{"type":"y"}\n')
    assert [e["type"] for e in read_events(p)] == ["x", "y"]


def test_filter_events_by_type(tmp_path: Path) -> None:
    p = tmp_path / "events.jsonl"
    w = EventWriter(p)
    w.write(UserMessage(ts=now_iso(), session_id="s", text="u1"))
    w.write(AssistantMessage(ts=now_iso(), session_id="s", text="a1", tool_call_count=0))
    w.write(UserMessage(ts=now_iso(), session_id="s", text="u2"))
    events = read_events(p)
    user_events = filter_events(events, type_="user_message")
    assert [e["text"] for e in user_events] == ["u1", "u2"]


def test_jsonl_round_trip_preserves_all_fields(tmp_path: Path) -> None:
    """Schema-lock: every field declared on an event must survive a round
    trip through JSONL. Catches accidental `repr=False` or missing slots."""
    p = tmp_path / "events.jsonl"
    w = EventWriter(p)
    w.write(
        PermissionDecision(
            ts="2026-05-15T00:00:00Z",
            session_id="sess-1",
            tool_name="run_shell",
            decision="approval_required",
            rule="trust_ladder",
            reason="never approved",
            via_autopilot=False,
        )
    )
    row = json.loads(p.read_text().splitlines()[0])
    expected = {
        "ts",
        "session_id",
        "tool_name",
        "decision",
        "rule",
        "reason",
        "via_autopilot",
        "type",
    }
    assert set(row.keys()) == expected


def test_events_path_for_project(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    assert events_path_for_project(state) == state / "events.jsonl"


# ---------- recent_error_events (M132 follow-up: recency cutoff) ----------

_NOW = 1_700_000_000.0
_DAY = 86_400.0


def _err_at(epoch: float, message: str = "boom") -> dict:
    return {
        "type": "error",
        "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(epoch)),
        "session_id": None,
        "where": "agent.run",
        "error_type": "ProviderError",
        "message": message,
    }


def test_recent_error_events_drops_stale() -> None:
    events = [_err_at(_NOW - 2 * _DAY, "stale"), _err_at(_NOW - 1000, "fresh")]
    got = recent_error_events(events, within_seconds=_DAY, limit=5, now_epoch=_NOW)
    assert [e["message"] for e in got] == ["fresh"]


def test_recent_error_events_keeps_within_window() -> None:
    events = [_err_at(_NOW - 100), _err_at(_NOW - 200)]
    got = recent_error_events(events, within_seconds=_DAY, limit=5, now_epoch=_NOW)
    assert len(got) == 2


def test_recent_error_events_respects_limit_keeping_newest() -> None:
    events = [_err_at(_NOW - i, f"e{i}") for i in (300, 200, 100)]
    got = recent_error_events(events, within_seconds=_DAY, limit=2, now_epoch=_NOW)
    # Last `limit` in log order → the two most recently appended.
    assert [e["message"] for e in got] == ["e200", "e100"]


def test_recent_error_events_keeps_undatable_events() -> None:
    """A missing/unparseable ts can't be proven stale → keep it."""
    events = [
        {"type": "error", "ts": "", "message": "no-ts"},
        {"type": "error", "message": "absent"},
    ]
    got = recent_error_events(events, within_seconds=_DAY, limit=5, now_epoch=_NOW)
    assert {e["message"] for e in got} == {"no-ts", "absent"}


def test_recent_error_events_ignores_non_error_types() -> None:
    events = [_err_at(_NOW - 100), {"type": "user_message", "ts": _err_at(_NOW)["ts"]}]
    got = recent_error_events(events, within_seconds=_DAY, limit=5, now_epoch=_NOW)
    assert len(got) == 1 and got[0]["type"] == "error"
