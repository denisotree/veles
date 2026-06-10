"""Agent runtime state (Tier ε, M71).

The earlier loop was procedural — `run()` had no state enum at all, just
behavioural flags inferred from positional context. Veles collapses that
into a single `AgentState` enum so:

  - the Permission Engine can read "are we in Planning mode?" without
    threading the flag through every call site,
  - the typed event log (M69) can stamp `state` on observations and
    decisions for replay,
  - future Tier ζ work (suspend/resume, approval-pending UX) plugs in
    by adding states without re-shaping the loop.

For now only `IDLE` and `PLANNING` change runtime behaviour
(Planning blocks mutation tools via Permission Engine). The remaining
states are reserved — Agent transitions them but no rule keys off them
yet, which is fine: surface stays narrow, semantics are explicit.
"""

from __future__ import annotations

import enum
from contextvars import ContextVar, Token


class AgentState(enum.Enum):
    IDLE = "idle"
    PLANNING = "planning"  # read-only / draft-only tools; mutations denied
    CALLING = "calling"  # model call in flight
    TOOLING = "tooling"  # dispatching a tool result
    APPROVAL_PENDING = "approval_pending"  # paused, waiting for user
    COMPACTING = "compacting"
    DONE = "done"


_active_state: ContextVar[AgentState] = ContextVar(
    "veles_agent_state", default=AgentState.IDLE
)


def current_state() -> AgentState:
    return _active_state.get()


def set_state(s: AgentState) -> Token[AgentState]:
    return _active_state.set(s)


def reset_state(token: Token[AgentState]) -> None:
    _active_state.reset(token)


def is_planning() -> bool:
    """Convenience predicate — the Permission Engine's hot path."""
    return _active_state.get() is AgentState.PLANNING


# ---- M72: draft/commit invocation tracking ----------------------------------
#
# The Permission Engine's `_draft_commit_rule` needs to know whether a draft
# tool has been invoked earlier in the current session before letting its
# paired commit tool proceed. We track that as a per-session set of tool
# names, populated by the agent loop right before each dispatch.

_invoked_tools: ContextVar[frozenset[str]] = ContextVar(
    "veles_invoked_tools", default=frozenset()
)


def invoked_tools() -> frozenset[str]:
    """Names of tools that have been dispatched in the current session so far."""
    return _invoked_tools.get()


def record_invocation(name: str) -> Token[frozenset[str]]:
    """Append `name` to the per-session invoked-tools set.

    Returns a token so the agent loop can reset on session end if it
    cares (the agent currently does not — sessions are pinned to one
    run() call, so the ContextVar tears down naturally).
    """
    current = _invoked_tools.get()
    return _invoked_tools.set(current | {name})


def reset_invoked_tools(token: Token[frozenset[str]]) -> None:
    _invoked_tools.reset(token)


def clear_invoked_tools() -> Token[frozenset[str]]:
    """Wipe the set at the start of a run; returns reset token."""
    return _invoked_tools.set(frozenset())
