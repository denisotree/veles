"""Tool dispatch + permission/approval pipeline, extracted from agent.py in M156.

Module-level functions only — the Agent turn loop calls `_dispatch` per tool
call; everything else here is the refusal / approval / audit machinery that
keeps the side-effects identical regardless of why a call did or didn't run.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
from collections.abc import Callable

from veles.core.agent_state import record_invocation
from veles.core.approval import record_approval
from veles.core.context import current_project
from veles.core.events import (
    ApprovalRequest,
    ApprovalResult,
    Event,
    EventWriter,
    PermissionDecision,
)
from veles.core.events import (
    ToolCall as ToolCallEvent,
)
from veles.core.events import (
    ToolResult as ToolResultEvent,
)
from veles.core.modules import VetoResult, fire_hook
from veles.core.permission import evaluate as evaluate_permission
from veles.core.provider import Message, ToolCall
from veles.core.tools.registry import Registry
from veles.core.trace import now_iso


def _emit_tool_refusal(
    call: ToolCall,
    *,
    refusal_text: str,
    error_msg: str,
    event_writer: EventWriter | None,
    event_listener: Callable[[Event], None] | None,
    session_id: str | None,
) -> Message:
    """Fan out the standard 'tool refused' aftermath: post_tool_call hook,
    `ToolResult` event, and a tool-role Message the agent can append to history.

    Used by every refusal path (module veto, permission deny, approval deny)
    so the side-effects stay identical regardless of *why* the call didn't run.
    """
    fire_hook(
        "post_tool_call",
        name=call.name,
        arguments=call.arguments,
        output=refusal_text,
        error=error_msg,
    )
    _emit(
        event_writer,
        ToolResultEvent(
            ts=now_iso(),
            session_id=session_id,
            tool_call_id=call.id,
            name=call.name,
            output=refusal_text,
            error=error_msg,
        ),
        event_listener,
    )
    return Message(role="tool", content=refusal_text, tool_call_id=call.id)


def _run_approval_prompt(
    call: ToolCall,
    decision,
    entry,
    *,
    event_writer: EventWriter | None,
    event_listener: Callable[[Event], None] | None,
    session_id: str | None,
):
    """Pause the loop, ask the user, return an upgraded `Decision`.

    M71 follow-up: `approval_required` is interactive — flip state to
    `APPROVAL_PENDING`, run the prompter (default reads y/N on stdin; daemon
    / TUI install their own), then convert the answer into a `Decision`
    using the standard `approval_prompt` rule so downstream code (event log,
    record_approval, refusal path) stays uniform.
    """
    from veles.core.agent_state import (
        AgentState as _AgentState,
    )
    from veles.core.agent_state import (
        reset_state as _reset_state,
    )
    from veles.core.agent_state import (
        set_state as _set_state,
    )
    from veles.core.approval_prompter import ask_for_approval
    from veles.core.permission import Decision as _Decision

    _emit(
        event_writer,
        ApprovalRequest(
            ts=now_iso(),
            session_id=session_id,
            action=f"dispatch {call.name}",
            target=call.name,
            risk=entry.risk_class.value if entry.risk_class else "",
        ),
        event_listener,
    )
    pause_token = _set_state(_AgentState.APPROVAL_PENDING)
    try:
        answer = ask_for_approval(call.name, call.arguments, decision.reason)
    finally:
        _reset_state(pause_token)
    _emit(
        event_writer,
        ApprovalResult(
            ts=now_iso(),
            session_id=session_id,
            action=f"dispatch {call.name}",
            status="approved" if answer.approved else "denied",
        ),
        event_listener,
    )
    return _Decision(
        kind="allow" if answer.approved else "deny",
        rule="approval_prompt",
        reason=(
            "user approved interactively"
            if answer.approved
            else f"user denied: {answer.reason}"
        ),
    )


def _invoke_tool_safely(
    registry: Registry,
    call: ToolCall,
    *,
    artifact_dir,
) -> tuple[str, str | None]:
    """Run the tool, stamping the per-session invocation set first.

    M72: the stamp happens *before* dispatch so an inline draft → commit
    chain (model emits both in one response) still satisfies the engine's
    pairing check. Errors are converted to `<error: TYPE: msg>` strings —
    the agent must always have a tool-role message to feed back.
    """
    record_invocation(call.name)
    try:
        return registry.dispatch(call.name, call.arguments, artifact_dir=artifact_dir), None
    except Exception as exc:
        return f"<error: {type(exc).__name__}: {exc}>", f"{type(exc).__name__}: {exc}"


def _persist_approval_if_grant(
    decision,
    call: ToolCall,
    *,
    approval_dir,
    session_id: str | None,
) -> None:
    """M73: durable approval record for user-facing grants only.

    `trust_ladder` / `always_confirm` / `approval_prompt` are real grants
    worth auditing. `planning_mode` / `risk_default` / `default_allow` aren't
    — recording them would flood the log. Disk failures are swallowed: the
    audit trail is best-effort, never blocks dispatch.
    """
    if approval_dir is None or not decision.allowed:
        return
    if decision.rule not in ("trust_ladder", "always_confirm", "approval_prompt"):
        return
    try:
        record_approval(
            approval_dir,
            tool_name=call.name,
            rule=decision.rule,
            via_autopilot=decision.via_autopilot,
            session_id=session_id,
            reason=decision.reason,
            arguments=call.arguments,
        )
    except OSError as exc:
        logger.warning("approval audit write failed (best-effort, dispatch continues): %s", exc)


def _dispatch(
    registry: Registry,
    call: ToolCall,
    *,
    log,
    event_writer: EventWriter | None = None,
    event_listener: Callable[[Event], None] | None = None,
    session_id: str | None = None,
    artifact_dir=None,
    approval_dir=None,
) -> Message:
    log(f"   tool {call.name}({call.arguments})")
    # File-backed daemon log: every tool call surfaces by name and args
    # (truncated) so debugging from `~/.veles/logs/daemon-*.log` is
    # tractable without replaying the full event-stream JSONL.
    try:
        from veles.daemon.logging import truncate_for_log

        logger.info(
            "tool.call name=%s args=%s", call.name, truncate_for_log(call.arguments)
        )
    except Exception:
        pass
    _emit(
        event_writer,
        ToolCallEvent(
            ts=now_iso(),
            session_id=session_id,
            tool_call_id=call.id,
            name=call.name,
            arguments=call.arguments,
        ),
        event_listener,
    )

    veto: VetoResult | None = fire_hook("pre_tool_call", name=call.name, arguments=call.arguments)
    if veto is not None:
        log(f"   vetoed by module {veto.module_name!r}: {veto.reason}")
        _emit(
            event_writer,
            PermissionDecision(
                ts=now_iso(),
                session_id=session_id,
                tool_name=call.name,
                decision="deny",
                rule="module_veto",
                reason=f"{veto.module_name}: {veto.reason}",
            ),
            event_listener,
        )
        return _emit_tool_refusal(
            call,
            refusal_text=f"<vetoed by module {veto.module_name!r}: {veto.reason}>",
            error_msg=f"vetoed by {veto.module_name}: {veto.reason}",
            event_writer=event_writer,
            event_listener=event_listener,
            session_id=session_id,
        )

    try:
        entry = registry.get(call.name)
    except KeyError:
        entry = None

    via_autopilot = False
    if entry is not None:
        decision = evaluate_permission(entry, call.arguments)
        if decision.kind == "approval_required":
            decision = _run_approval_prompt(
                call,
                decision,
                entry,
                event_writer=event_writer,
                event_listener=event_listener,
                session_id=session_id,
            )
        # Emit the permission event for every tool — even allow-by-default —
        # so the typed event log carries full coverage for M70 eval grading.
        _emit(
            event_writer,
            PermissionDecision(
                ts=now_iso(),
                session_id=session_id,
                tool_name=call.name,
                decision=decision.kind,
                rule=decision.rule,
                reason=decision.reason,
                via_autopilot=decision.via_autopilot,
            ),
            event_listener,
        )
        _persist_approval_if_grant(
            decision, call, approval_dir=approval_dir, session_id=session_id
        )
        if not decision.allowed:
            log(f"   refused by {decision.rule}: {decision.reason}")
            return _emit_tool_refusal(
                call,
                refusal_text=f"<refused by {decision.rule}: {decision.reason}>",
                error_msg=f"refused by {decision.rule}: {decision.reason}",
                event_writer=event_writer,
                event_listener=event_listener,
                session_id=session_id,
            )
        via_autopilot = decision.via_autopilot

    output, error = _invoke_tool_safely(registry, call, artifact_dir=artifact_dir)
    try:
        from veles.daemon.logging import truncate_for_log

        if error:
            logger.warning("tool.error name=%s err=%s", call.name, error)
        else:
            logger.info(
                "tool.result name=%s preview=%s",
                call.name,
                truncate_for_log(output),
            )
    except Exception:
        pass
    if via_autopilot:
        _audit_autopilot_dispatch(call.name, error)
    fire_hook(
        "post_tool_call",
        name=call.name,
        arguments=call.arguments,
        output=output,
        error=error,
    )
    _emit(
        event_writer,
        ToolResultEvent(
            ts=now_iso(),
            session_id=session_id,
            tool_call_id=call.id,
            name=call.name,
            output=output,
            error=error,
        ),
        event_listener,
    )
    return Message(role="tool", content=output, tool_call_id=call.id)


def _emit(
    writer: EventWriter | None,
    event,
    listener: Callable[[Event], None] | None = None,
) -> None:
    """Best-effort event fan-out.

    Two independent sinks; either may be absent. Writer persists to a
    JSONL file for audit (`_event_writer`); listener is the per-run
    in-memory firehose used by live UIs (TUI inspector, daemon push).
    Exceptions on either side are swallowed: a broken event log or a
    buggy UI subscriber must never kill the agent loop. M70 evals will
    catch a missing event log via assertion rather than propagation.
    """
    if writer is not None:
        try:
            writer.write(event)
        except Exception:  # noqa: BLE001
            pass
    if listener is not None:
        try:
            listener(event)
        except Exception:  # noqa: BLE001
            pass


def _audit_autopilot_dispatch(tool_name: str, error: str | None) -> None:
    """Append `op="autopilot-<tool>"` to the active project's LOG.md.

    M63: every sensitive-tool dispatch that bypassed the trust ladder
    via the autopilot window is recorded so the user can audit
    unattended runs. Failures don't propagate — LOG.md is best-effort.
    """
    project = current_project()
    if project is None:
        return
    try:
        from veles.core.wiki import Wiki

        summary = f"sensitive tool {tool_name!r} dispatched"
        if error is not None:
            summary += f" (failed: {error})"
        Wiki(project.wiki_root).append_log(op=f"autopilot-{tool_name}", summary=summary)
    except Exception:
        pass
