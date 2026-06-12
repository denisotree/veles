"""Collapsible inspector — live view of tool activity and agent state.

What it shows:
  - A one-line header that's always present, with a chevron indicating
    expanded/collapsed and a brief tally ("3 tools · busy" / "idle").
  - When expanded: an "activity" pane listing the most recent tool
    calls with their status (running/done/failed) and duration. Each
    `ToolCall` event opens a row; the matching `ToolResult` event seals
    it with timing.

Why this shape:

  `core/events.py` doesn't ship a `ThinkingDelta` type (Anthropic's
  reasoning blocks, OpenAI's reasoning items are adapter-specific and
  not surfaced as typed events yet). Rather than fake a reasoning
  channel, the inspector exposes what the typed event stream actually
  carries: tool dispatch lifecycle plus permission/approval events.
  When a future event-stream extension lands, the same widget extends
  in place — `_handle_event` is the single switch site.

The widget is dumb: it reacts to `notify_event(ev)` calls from the App
and a `set_busy(flag)` setter from the bridge. It never looks at the
agent loop itself.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass

from textual.containers import Vertical
from textual.widgets import Static

from veles.core.events import (
    ApprovalRequest,
    ApprovalResult,
    ErrorEvent,
    Event,
    PermissionDecision,
    ThinkingDelta,
    ToolCall,
    ToolResult,
)

_MAX_VISIBLE_ROWS = 5
_ARGS_PREVIEW_LIMIT = 40
_ERROR_PREVIEW_LIMIT = 60
_REASONING_TAIL_CHARS = 280


class _SelectableStatic(Static):
    # Mirror of `ChatLog.SelectableStatic` — kept local to avoid a
    # cross-widget import. Lets Textual's selection API target inspector
    # rows just like chat messages (Shift+arrow keyboard selection,
    # in-app copy-on-selection on supported terminals).
    allow_select = True


@dataclass(slots=True)
class _ToolActivity:
    call_id: str
    name: str
    args_preview: str
    status: str  # "running" | "done" | "failed"
    started_at: float
    duration_ms: int | None = None


class Inspector(Vertical):
    """Composite: header line + body Vertical for activity rows.

    Visibility is toggled by collapsing the body — the header always
    stays so the user has a visual reminder of the inspector + hotkey.
    """

    DEFAULT_CSS = """
    Inspector {
        background: $surface;
        border-top: tall $primary 40%;
        padding: 0 1;
        height: auto;
        max-height: 14;
    }
    Inspector > Static.veles-inspector-header {
        color: $text-muted;
        height: 1;
    }
    Inspector > Vertical#veles-inspector-body {
        height: auto;
    }
    Inspector > Vertical#veles-inspector-body > Static {
        color: $text;
        height: 1;
    }
    Inspector > Vertical#veles-inspector-body > Static.veles-tool-running {
        color: $warning;
    }
    Inspector > Vertical#veles-inspector-body > Static.veles-tool-done {
        color: $success;
    }
    Inspector > Vertical#veles-inspector-body > Static.veles-tool-failed {
        color: $error;
    }
    Inspector > Vertical#veles-inspector-body > Static.veles-error {
        color: $error;
        text-style: bold;
    }
    Inspector > Vertical#veles-inspector-body > Static.veles-reasoning {
        color: $text-muted;
        text-style: italic;
    }
    Inspector > Vertical#veles-inspector-body > Static.veles-permission {
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="veles-inspector")
        # Preserve insertion order so the most recent activity is at the
        # bottom of the rendered list. OrderedDict gives O(1) lookup by
        # tool_call_id when a `ToolResult` arrives later.
        self._tools: OrderedDict[str, _ToolActivity] = OrderedDict()
        self._permission_lines: list[str] = []
        # M132: recent errors/timeouts. Persisted across turns (unlike
        # permission breadcrumbs) and seeded from events.jsonl on startup
        # so a failure stays visible after a TUI restart.
        self._error_lines: list[str] = []
        # M133: accumulated reasoning/thinking for the current turn. Cleared
        # on a new turn (ephemeral, unlike errors). Rendered as a single
        # streaming tail line so long chains-of-thought don't flood the body.
        self._reasoning: str = ""
        self._busy: bool = False
        self._expanded: bool = False
        # Plain-text mirror of every body line we last rendered, in
        # display order. Tests read this instead of poking Static
        # internals.
        self.activity_log: list[str] = []
        # Plain-text mirror of the header chip line. Same role as
        # StatusBar.last_text: shields tests from Textual's internal
        # Static representation, which differs across versions.
        self.header_text: str = ""

    # ---- lifecycle ----

    def compose(self):
        self._header = _SelectableStatic("", classes="veles-inspector-header")
        yield self._header
        self._body = Vertical(id="veles-inspector-body")
        yield self._body

    def on_mount(self) -> None:
        self._apply_visibility()
        self._refresh()

    # ---- public API (called by TuiApp / AgentBridge) ----

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, value: bool) -> None:
        self._expanded = value
        self._apply_visibility()
        self._refresh()

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh()

    def notify_event(self, event: Event) -> None:
        """Single fan-in point for every `core.events.Event`. The App
        forwards `AgentEvent` payloads here verbatim; no type-narrowing
        upstream so a future event type doesn't need an App edit."""
        if isinstance(event, ToolCall):
            self._on_tool_call(event)
        elif isinstance(event, ToolResult):
            self._on_tool_result(event)
        elif isinstance(event, (PermissionDecision, ApprovalRequest, ApprovalResult)):
            self._on_permission_event(event)
        elif isinstance(event, ErrorEvent):
            self._on_error(event)
        elif isinstance(event, ThinkingDelta):
            if event.text:
                self._reasoning += event.text
        else:
            return
        self._refresh()

    def seed_errors(self, errors: list[ErrorEvent]) -> None:
        """Load recent errors at startup (from the persisted events.jsonl)
        so failures survive a TUI restart. Called once by the App on mount."""
        for ev in errors:
            self._on_error(ev)
        self._refresh()

    def reset_for_new_turn(self) -> None:
        """Clear permission/approval breadcrumbs at the start of every
        turn so the inspector doesn't keep stale lines from the previous
        run. Tool history is kept — the user usually wants to see what
        ran last."""
        self._permission_lines.clear()
        # Reasoning is per-turn — drop the previous turn's chain-of-thought.
        self._reasoning = ""
        self._refresh()

    # ---- event handling ----

    def _on_tool_call(self, ev: ToolCall) -> None:
        entry = _ToolActivity(
            call_id=ev.tool_call_id or ev.name,
            name=ev.name,
            args_preview=_preview_args(ev.arguments),
            status="running",
            started_at=time.monotonic(),
        )
        self._tools[entry.call_id] = entry

    def _on_tool_result(self, ev: ToolResult) -> None:
        key = ev.tool_call_id or ev.name
        entry = self._tools.get(key)
        if entry is None:
            # Result without a matching call (rare: e.g. veto fires
            # before the call was recorded). Synthesize one so the user
            # at least sees the closing row.
            entry = _ToolActivity(
                call_id=key,
                name=ev.name,
                args_preview="",
                status="running",
                started_at=time.monotonic(),
            )
            self._tools[key] = entry
        entry.status = "failed" if ev.error else "done"
        entry.duration_ms = int((time.monotonic() - entry.started_at) * 1000)

    def _on_permission_event(
        self, ev: PermissionDecision | ApprovalRequest | ApprovalResult
    ) -> None:
        if isinstance(ev, PermissionDecision):
            line = f"  · permission {ev.tool_name} → {ev.decision} ({ev.rule})"
        elif isinstance(ev, ApprovalRequest):
            line = f"  · approval requested for {ev.target} (risk={ev.risk or 'unknown'})"
        else:
            line = f"  · approval {ev.status}: {ev.action}"
        self._permission_lines.append(line)
        # Keep only the most recent breadcrumbs to bound row count.
        self._permission_lines = self._permission_lines[-_MAX_VISIBLE_ROWS:]

    def _on_error(self, ev: ErrorEvent) -> None:
        kind = "timeout" if "Timeout" in ev.error_type else "error"
        msg = ev.message.strip().splitlines()[0] if ev.message.strip() else ev.error_type
        if len(msg) > _ERROR_PREVIEW_LIMIT:
            msg = msg[: _ERROR_PREVIEW_LIMIT - 1] + "…"
        self._error_lines.append(f"  ✗ {kind}: {msg}")
        self._error_lines = self._error_lines[-_MAX_VISIBLE_ROWS:]

    # ---- rendering ----

    def _refresh(self) -> None:
        # Header is always rendered — it shows the toggle hint and a
        # one-glance summary even when the body is collapsed.
        chevron = "▾" if self._expanded else "▸"
        running = sum(1 for e in self._tools.values() if e.status == "running")
        done = sum(1 for e in self._tools.values() if e.status != "running")
        bits: list[str] = [
            f"{chevron} inspector",
            "(Ctrl+I)",
        ]
        # M115.2: explicit "thinking…" indicator when the agent is busy
        # but no tools are running — i.e. the model is producing text or
        # internal reasoning, not invoking anything. When tools *are*
        # running, the per-tool rows already show what the agent is
        # doing, so the header just says "busy". When idle, "idle".
        if self._busy:
            bits.append("thinking…" if running == 0 else "busy")
        else:
            bits.append("idle")
        if running:
            bits.append(f"{running} running")
        if done:
            bits.append(f"{done} done")
        if self._error_lines:
            # Surfaced in the always-visible header so a failure is noticed
            # even when the body is collapsed (M132).
            n = len(self._error_lines)
            bits.append(f"⚠ {n} error{'s' if n != 1 else ''}")
        header_text = " · ".join(bits)
        self.header_text = header_text
        self._header.update(header_text)

        if not self._expanded:
            self.activity_log = []
            return

        rows = self._render_rows()
        self.activity_log = rows
        # Replace body children with the new row set. Rebuilding (rather
        # than diffing) is fine here: at most ~10 rows, and any new tool
        # event reorders the tail anyway.
        for child in list(self._body.children):
            child.remove()
        for line, css_class in self._classified_rows(rows):
            self._body.mount(_SelectableStatic(line, classes=css_class))

    def _reasoning_line(self) -> str:
        """M133: collapse the accumulated reasoning to a single tail line so
        a long chain-of-thought streams in place instead of flooding rows."""
        if not self._reasoning:
            return ""
        tail = " ".join(self._reasoning.split())
        if len(tail) > _REASONING_TAIL_CHARS:
            tail = "…" + tail[-(_REASONING_TAIL_CHARS - 1) :]
        return f"  💭 {tail}"

    def _render_rows(self) -> list[str]:
        rows: list[str] = []
        reasoning = self._reasoning_line()
        if reasoning:
            # Real reasoning supersedes the generic placeholder.
            rows.append(reasoning)
        elif self._busy and not self._tools and not self._permission_lines:
            # M115.2: consistent "thinking…" wording with the header chip.
            rows.append("  agent thinking…")
        # Tools — newest at the bottom.
        recent = list(self._tools.values())[-_MAX_VISIBLE_ROWS:]
        for entry in recent:
            rows.append(_format_tool_row(entry))
        rows.extend(self._permission_lines)
        # Errors last so they sit at the bottom (most-recent, most-relevant).
        rows.extend(self._error_lines)
        return rows

    def _classified_rows(self, rows: list[str]) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for line in rows:
            if line.startswith("  💭 "):
                out.append((line, "veles-reasoning"))
            elif line.startswith("  ✗ error:") or line.startswith("  ✗ timeout:"):
                out.append((line, "veles-error"))
            elif "permission" in line or "approval" in line:
                out.append((line, "veles-permission"))
            elif "✓" in line:
                out.append((line, "veles-tool-done"))
            elif "✗" in line:
                out.append((line, "veles-tool-failed"))
            elif "▸" in line:
                out.append((line, "veles-tool-running"))
            else:
                out.append((line, ""))
        return out

    def _apply_visibility(self) -> None:
        # The body container is mounted in `compose`; collapse the whole
        # inspector vertical to just the header by hiding the body.
        if getattr(self, "_body", None) is None:
            return
        self._body.display = self._expanded


# ---- helpers ----


def _preview_args(args: dict) -> str:
    """Compact key=val pairs for the activity row. Falls back to the
    raw repr (truncated) when the dict is empty or oddly shaped."""
    if not args:
        return ""
    try:
        pieces = [f"{k}={_short_repr(v)}" for k, v in args.items()]
        text = ", ".join(pieces)
    except Exception:
        text = repr(args)
    if len(text) > _ARGS_PREVIEW_LIMIT:
        text = text[: _ARGS_PREVIEW_LIMIT - 1] + "…"
    return text


def _short_repr(value) -> str:
    if isinstance(value, str):
        if len(value) > 18:
            return repr(value[:17] + "…")
        return repr(value)
    return repr(value)


def _format_tool_row(entry: _ToolActivity) -> str:
    bullet = {"running": "▸", "done": "✓", "failed": "✗"}[entry.status]
    args = f"({entry.args_preview})" if entry.args_preview else "()"
    duration = ""
    if entry.duration_ms is not None:
        duration = f" · {entry.duration_ms}ms"
    return f"  {bullet} {entry.name}{args}{duration}"
