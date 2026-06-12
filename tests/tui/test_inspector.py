"""Inspector unit + integration coverage.

Unit tests poke `Inspector.notify_event` directly on a freshly-mounted
widget inside a minimal Textual app harness — fastest feedback when the
event-to-row mapping changes.

Integration tests use the full `TuiApp` and synthesize events via
`AgentEvent` messages posted from the test thread. That path exercises
`on_agent_event` routing and the Ctrl+I toggle binding.
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from veles.core.events import (
    ApprovalRequest,
    ApprovalResult,
    ErrorEvent,
    PermissionDecision,
    ToolCall,
    ToolResult,
    now_iso,
)
from veles.tui.app import TuiApp
from veles.tui.messages import AgentEvent
from veles.tui.state import AppState
from veles.tui.widgets.inspector import Inspector

# ---------------- inspector-only harness ----------------


class _InspectorHost(App):
    """Minimal app that mounts a single Inspector. Used by the unit
    tests so we don't pay for the full TuiApp boot when checking
    `notify_event` mechanics."""

    def __init__(self) -> None:
        super().__init__()
        self.inspector = Inspector()

    def compose(self) -> ComposeResult:
        yield self.inspector


def _tool_call(call_id: str, name: str, args: dict) -> ToolCall:
    return ToolCall(
        ts=now_iso(),
        session_id=None,
        tool_call_id=call_id,
        name=name,
        arguments=args,
    )


def _tool_result(call_id: str, name: str, output: str, error: str | None = None) -> ToolResult:
    return ToolResult(
        ts=now_iso(),
        session_id=None,
        tool_call_id=call_id,
        name=name,
        output=output,
        error=error,
    )


# ---------------- unit tests ----------------


async def test_collapsed_inspector_shows_header_only():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        # Default state is collapsed.
        assert not insp.expanded
        # No rows materialize while collapsed.
        assert insp.activity_log == []


async def test_expand_shows_thinking_placeholder():
    """M115.2: when busy with no tools running, the body shows
    `agent thinking…` (header chip also flips from `idle` → `thinking…`)."""
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.set_busy(True)
        await pilot.pause()
        assert any("thinking" in row for row in insp.activity_log)
        # Header gains the same chip so users see it even when collapsed.
        assert "thinking" in insp.header_text


async def test_busy_with_tool_running_shows_busy_not_thinking():
    """When a tool is running, per-tool rows already explain what the
    agent is doing — the header chip stays `busy`, not `thinking…`."""
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.set_busy(True)
        insp.notify_event(_tool_call("c1", "wiki.search", {"q": "x"}))
        await pilot.pause()
        assert "busy" in insp.header_text
        assert "thinking" not in insp.header_text


async def test_idle_state_shows_idle_chip():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        await pilot.pause()
        # `set_busy(False)` is the implicit default; header has "idle".
        assert "idle" in insp.header_text
        assert "thinking" not in insp.header_text


async def test_tool_call_renders_running_row_then_done():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(_tool_call("c1", "wiki.search", {"query": "veles"}))
        await pilot.pause()
        rows = "\n".join(insp.activity_log)
        assert "▸ wiki.search" in rows
        assert "query='veles'" in rows

        insp.notify_event(_tool_result("c1", "wiki.search", "12 hits"))
        await pilot.pause()
        rows = "\n".join(insp.activity_log)
        assert "✓ wiki.search" in rows
        assert "ms" in rows  # duration suffix


async def test_tool_result_with_error_marks_failed():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(_tool_call("c1", "fs.write", {"path": "x"}))
        insp.notify_event(
            _tool_result("c1", "fs.write", "<refused>", error="refused by trust_ladder")
        )
        await pilot.pause()
        rows = "\n".join(insp.activity_log)
        assert "✗ fs.write" in rows


async def test_orphan_tool_result_synthesizes_row():
    """Vetoes can emit a ToolResult without a matching ToolCall — the
    inspector still surfaces the closing row so the user isn't left
    confused by a silent failure."""
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(_tool_result("c1", "fs.delete", "<vetoed>", error="vetoed"))
        await pilot.pause()
        rows = "\n".join(insp.activity_log)
        assert "✗ fs.delete" in rows


async def test_permission_breadcrumbs_appear_when_expanded():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(
            PermissionDecision(
                ts=now_iso(),
                session_id=None,
                tool_name="fs.write",
                decision="allow",
                rule="trust_ladder",
                reason="user allowed",
            )
        )
        insp.notify_event(
            ApprovalRequest(
                ts=now_iso(), session_id=None, action="dispatch x", target="fs.write", risk="high"
            )
        )
        insp.notify_event(
            ApprovalResult(ts=now_iso(), session_id=None, action="dispatch x", status="approved")
        )
        await pilot.pause()
        rows = "\n".join(insp.activity_log)
        assert "permission fs.write" in rows
        assert "approval requested" in rows
        assert "approval approved" in rows


async def test_only_last_five_tool_rows_render():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        for i in range(7):
            insp.notify_event(_tool_call(f"c{i}", f"tool{i}", {}))
            insp.notify_event(_tool_result(f"c{i}", f"tool{i}", "ok"))
        await pilot.pause()
        tool_rows = [r for r in insp.activity_log if "tool" in r and ("✓" in r or "▸" in r)]
        assert len(tool_rows) == 5
        # The first two should have aged out.
        assert "tool0" not in " ".join(tool_rows)
        assert "tool6" in " ".join(tool_rows)


async def test_reset_for_new_turn_clears_permission_lines_keeps_tools():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(_tool_call("c1", "wiki.search", {"q": "x"}))
        insp.notify_event(_tool_result("c1", "wiki.search", "ok"))
        insp.notify_event(
            PermissionDecision(
                ts=now_iso(),
                session_id=None,
                tool_name="x",
                decision="allow",
                rule="default_allow",
                reason="",
            )
        )
        insp.reset_for_new_turn()
        await pilot.pause()
        rows = "\n".join(insp.activity_log)
        assert "wiki.search" in rows
        assert "permission" not in rows


async def test_toggle_flips_visibility():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        assert not insp.expanded
        insp.toggle()
        assert insp.expanded
        insp.toggle()
        assert not insp.expanded


# ---------------- TuiApp integration ----------------


def _new_app(tmp_project, agent_factory_for, text_response, *, reply: str = "ok"):
    project, store = tmp_project
    return TuiApp(
        state=AppState(session_id=None, provider_name="stub", model="m"),
        agent_factory=agent_factory_for(text_response(reply)),
        project=project,
        store=store,
    )


async def test_ctrl_i_toggles_inspector_and_updates_state(
    tmp_project, agent_factory_for, text_response
):
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        insp = pilot.app.query_one(Inspector)
        assert not insp.expanded
        await pilot.press("ctrl+i")
        await pilot.pause()
        assert insp.expanded
        assert pilot.app.state.inspector_visible
        await pilot.press("ctrl+i")
        await pilot.pause()
        assert not insp.expanded
        assert not pilot.app.state.inspector_visible


async def test_agent_event_message_routes_to_inspector(
    tmp_project, agent_factory_for, text_response
):
    """`AgentEvent` messages posted from the bridge land in the
    inspector verbatim. Skip the real agent path — we post the message
    by hand to keep the assertion focused on the App router."""
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+i")  # expand so rows render
        await pilot.pause()
        ev = _tool_call("c1", "demo.tool", {"k": "v"})
        pilot.app.post_message(AgentEvent(ev))
        await pilot.pause()
        insp = pilot.app.query_one(Inspector)
        assert any("demo.tool" in row for row in insp.activity_log)


# ---------------- M132: error/timeout surfacing ----------------


def _error_event(error_type: str, message: str) -> ErrorEvent:
    return ErrorEvent(
        ts=now_iso(),
        session_id=None,
        where="agent.run",
        error_type=error_type,
        message=message,
    )


async def test_error_event_shows_in_header_and_body():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(_error_event("RuntimeError", "boom happened"))
        await pilot.pause()
        # Header carries the count even when later collapsed.
        assert "1 error" in insp.header_text
        rows = "\n".join(insp.activity_log)
        assert "✗ error: boom happened" in rows


async def test_timeout_event_labelled_distinctly():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(_error_event("ProviderTimeout", "provider stream timed out"))
        await pilot.pause()
        rows = "\n".join(insp.activity_log)
        assert "✗ timeout:" in rows


async def test_seed_errors_survives_restart():
    """Errors loaded from the persisted log appear without a live event."""
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.seed_errors([_error_event("RuntimeError", "from last session")])
        insp.set_expanded(True)
        await pilot.pause()
        assert "1 error" in insp.header_text
        assert any("from last session" in row for row in insp.activity_log)


async def test_errors_persist_across_turn_reset():
    """Unlike permission breadcrumbs, errors stay through reset_for_new_turn."""
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(_error_event("RuntimeError", "sticky"))
        insp.reset_for_new_turn()
        await pilot.pause()
        assert any("sticky" in row for row in insp.activity_log)


async def test_seed_errors_from_events_log_on_mount(tmp_project, agent_factory_for, text_response):
    """M132: the App reads recent ErrorEvents from the persisted
    events.jsonl on mount, so a failure from a previous session is shown
    after a restart. Exercises the real read→reconstruct→seed path in
    `TuiApp._seed_inspector_errors`, not just `Inspector.seed_errors`."""
    from veles.core.events import (
        ErrorEvent as _ErrorEvent,
    )
    from veles.core.events import (
        EventWriter,
        events_path_for_project,
        now_iso,
    )

    project, _store = tmp_project
    writer = EventWriter(events_path_for_project(project.state_dir))
    writer.write(
        _ErrorEvent(
            ts=now_iso(),
            session_id=None,
            where="agent.run",
            error_type="ProviderTimeout",
            message="provider stream timed out",
        )
    )

    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        insp = pilot.app.query_one(Inspector)
        assert "1 error" in insp.header_text
        await pilot.press("ctrl+i")  # expand to render rows
        await pilot.pause()
        assert any("timeout:" in row for row in insp.activity_log)


async def test_seed_skips_stale_errors_from_events_log(
    tmp_project, agent_factory_for, text_response
):
    """M132 follow-up: a days-old error must NOT be resurrected onto a
    fresh session — only recent failures survive a restart."""
    from veles.core.events import ErrorEvent as _ErrorEvent
    from veles.core.events import (
        EventWriter,
        events_path_for_project,
    )

    project, _store = tmp_project
    writer = EventWriter(events_path_for_project(project.state_dir))
    writer.write(
        _ErrorEvent(
            ts="2020-01-01T00:00:00Z",  # ancient, far outside the window
            session_id=None,
            where="agent.run",
            error_type="ProviderError",
            message="stale 404 from an already-fixed bug",
        )
    )

    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        insp = pilot.app.query_one(Inspector)
        assert "error" not in insp.header_text


# ---------------- M133: reasoning display ----------------


def _thinking(text: str):
    from veles.core.events import ThinkingDelta

    return ThinkingDelta(ts=now_iso(), session_id=None, text=text)


async def test_reasoning_shows_in_body_when_expanded():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(_thinking("first thought "))
        insp.notify_event(_thinking("second thought"))
        await pilot.pause()
        rows = "\n".join(insp.activity_log)
        assert "💭" in rows
        assert "second thought" in rows  # accumulated tail


async def test_reasoning_cleared_on_new_turn():
    async with _InspectorHost().run_test() as pilot:
        insp = pilot.app.inspector
        insp.set_expanded(True)
        insp.notify_event(_thinking("ephemeral reasoning"))
        insp.reset_for_new_turn()
        await pilot.pause()
        assert not any("💭" in row for row in insp.activity_log)
        assert not any("ephemeral" in row for row in insp.activity_log)
