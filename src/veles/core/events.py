"""Typed event log (Tier ε, M69) — machine-readable companion to `LOG.md`.

`LOG.md` (managed by `core/wiki.py`) is curated, human-readable, and lives
inside the wiki's append-only journal. It's great for reading at a glance
but bad for replay / eval-grading / regression: timestamps drift, ad-hoc
strings make queries fragile, and the lint-agent rewrites it on demand.

`events.jsonl` is the opposite: one JSON line per event, stable schema,
never rewritten. The two files are not redundant — they answer different
questions. LOG.md answers "what happened, narratively?"; events.jsonl
answers "did the agent call `write_file` in the last 100 turns where the
plan was active?".

Event types follow a typed-event model: user/assistant messages, tool
calls and results,
permission decisions, approval requests/results, plan/goal updates,
compaction boundaries, connector calls, errors. Add new types by
appending a new `@dataclass` here; readers should ignore unknown `type`
values rather than crash (forward-compatibility).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 50 * 1024 * 1024
EVENTS_FILENAME = "events.jsonl"


# Each event dataclass carries:
#   `type` — discriminator string (matches the class' canonical name)
#   `ts`   — ISO-8601 UTC, supplied by emitter
#   `session_id` — optional, pulled from agent context
#   ... plus event-specific fields.
#
# We use slot'd, frozen dataclasses so events are immutable after creation
# and serialize cheaply via `asdict`. Defaults are placed after required
# fields to keep dataclass ordering happy.


@dataclass(slots=True, frozen=True)
class UserMessage:
    ts: str
    session_id: str | None
    text: str
    type: str = "user_message"


@dataclass(slots=True, frozen=True)
class AssistantMessage:
    ts: str
    session_id: str | None
    text: str | None
    tool_call_count: int = 0
    finish_reason: str | None = None
    type: str = "assistant_message"


@dataclass(slots=True, frozen=True)
class ToolCall:
    ts: str
    session_id: str | None
    tool_call_id: str
    name: str
    arguments: dict[str, Any]
    type: str = "tool_call"


@dataclass(slots=True, frozen=True)
class ToolResult:
    ts: str
    session_id: str | None
    tool_call_id: str
    name: str
    output: str
    error: str | None = None
    type: str = "tool_result"


@dataclass(slots=True, frozen=True)
class PermissionDecision:
    """Single decision emitted by the Permission Engine (M64).

    Until M64 lands this event captures the existing trust-ladder outcome
    surfaced through `evaluate_trust`. The schema is forward-compatible
    with the typed `PermissionDecision` dataclass from §15.0.
    """

    ts: str
    session_id: str | None
    tool_name: str
    decision: str  # allow | deny | approval_required | sandbox | draft_only
    rule: str  # which check fired (path_guard | trust_ladder | always_confirm | ...)
    reason: str = ""
    via_autopilot: bool = False
    type: str = "permission_decision"


@dataclass(slots=True, frozen=True)
class ApprovalRequest:
    ts: str
    session_id: str | None
    action: str
    target: str = ""
    risk: str = ""
    preview_ref: str | None = None
    type: str = "approval_request"


@dataclass(slots=True, frozen=True)
class ApprovalResult:
    ts: str
    session_id: str | None
    action: str
    status: str  # approved | denied | expired
    approver: str = ""
    type: str = "approval_result"


@dataclass(slots=True, frozen=True)
class PlanUpdate:
    ts: str
    session_id: str | None
    summary: str
    plan_ref: str | None = None
    type: str = "plan_update"


@dataclass(slots=True, frozen=True)
class Compaction:
    ts: str
    session_id: str | None
    summary: str
    summary_ref: str | None = None
    messages_collapsed: int = 0
    type: str = "compaction"


@dataclass(slots=True, frozen=True)
class ConnectorCall:
    ts: str
    session_id: str | None
    server: str
    tool: str
    duration_ms: int = 0
    success: bool = True
    error: str | None = None
    type: str = "connector_call"


@dataclass(slots=True, frozen=True)
class ErrorEvent:
    ts: str
    session_id: str | None
    where: str  # short tag identifying the call site
    error_type: str
    message: str
    type: str = "error"


@dataclass(slots=True, frozen=True)
class ThinkingDelta:
    """A chunk of the model's reasoning/thinking stream (M133).

    Emitted by the agent loop when the provider yields reasoning tokens
    (Anthropic thinking blocks, OpenAI/OpenRouter `reasoning`). Surfaced
    live in the TUI inspector via the event listener; persisted to the
    typed-event log like any other event so a session's reasoning trail is
    auditable. Distinct from `AssistantMessage` (the answer)."""

    ts: str
    session_id: str | None
    text: str
    type: str = "thinking"


Event = (
    UserMessage
    | AssistantMessage
    | ToolCall
    | ToolResult
    | PermissionDecision
    | ApprovalRequest
    | ApprovalResult
    | PlanUpdate
    | Compaction
    | ConnectorCall
    | ErrorEvent
    | ThinkingDelta
)


# ---- writer (mirrors core/trace.py for consistency) ----


class EventWriter:
    """Append `Event`s to a JSONL file with size-bounded rotation.

    Same rotation strategy as `TraceWriter`: rotate by total file size, keep
    the rotated siblings in place. Failure to write is the caller's problem
    — we don't swallow exceptions here; the agent loop catches them so a
    broken event log never kills a run, but unit tests can still see them.
    """

    def __init__(self, path: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self._path = path
        self._max_bytes = max_bytes
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def write(self, event: Event) -> None:
        line = json.dumps(asdict(event), separators=(",", ":")) + "\n"
        data = line.encode("utf-8")
        if self._path.exists() and self._path.stat().st_size + len(data) > self._max_bytes:
            self._rotate()
        with self._path.open("ab") as f:
            f.write(data)

    def _rotate(self) -> None:
        ts = int(time.time())
        target = self._path.with_name(f"{self._path.name}.{ts}")
        n = 1
        while target.exists():
            target = self._path.with_name(f"{self._path.name}.{ts}.{n}")
            n += 1
        os.replace(self._path, target)


def events_path_for_project(state_dir: Path) -> Path:
    """`<project>/.veles/events.jsonl` — canonical location."""
    return state_dir / EVENTS_FILENAME


def read_events(path: Path) -> list[dict[str, Any]]:
    """Read all events as plain dicts. Skips malformed lines silently.

    Returns dicts (not typed Event objects) so a future schema change
    doesn't trip a reader on legacy files. Callers that want strong typing
    should filter by `type` and cast.
    """
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def filter_events(events: list[dict[str, Any]], *, type_: str) -> list[dict[str, Any]]:
    """Convenience filter for tests + future `veles stats` consumers."""
    return [e for e in events if e.get("type") == type_]


def _parse_event_ts(ts: str) -> float | None:
    """Best-effort parse of an event `ts` to an epoch float.

    Returns None when the value is missing or unrecognisable — callers
    treat an undatable event as "cannot prove it's stale" and keep it.
    """
    if not ts:
        return None
    dt: datetime | None = None
    try:
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (ValueError, TypeError):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def recent_error_events(
    events: list[dict[str, Any]],
    *,
    within_seconds: float,
    limit: int,
    now_epoch: float | None = None,
) -> list[dict[str, Any]]:
    """Up to `limit` most-recent `type="error"` events no older than
    `within_seconds`.

    Seeds the TUI inspector so a *recent* failure survives a restart
    (M132) without resurrecting days-old, already-fixed errors onto a
    fresh session. Events whose `ts` can't be parsed are kept — we can't
    prove they're stale. `now_epoch` defaults to wall-clock time.
    """
    if now_epoch is None:
        now_epoch = time.time()
    cutoff = now_epoch - within_seconds
    fresh: list[dict[str, Any]] = []
    for event in filter_events(events, type_="error"):
        ts_epoch = _parse_event_ts(event.get("ts", ""))
        if ts_epoch is None or ts_epoch >= cutoff:
            fresh.append(event)
    return fresh[-limit:]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
