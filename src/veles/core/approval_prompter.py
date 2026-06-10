"""Interactive prompter for `approval_required` decisions (M71 follow-up).

The Permission Engine returns `approval_required` for risk classes that
the trust ladder doesn't cover (write_external, network_open_world, and
process_execution when the tool isn't marked `sensitive=True`). Before
this module that outcome silently became a `<refused>` tool message and
the agent moved on without ever asking the user.

This is the interactive half: when the engine surfaces
`approval_required`, the agent flips its state to `APPROVAL_PENDING`,
calls a prompter, and translates the answer into `allow` / `deny`. A
sensible default prompter prints the tool name + arguments to stderr
and reads y/N from stdin. Daemon / TUI callers install the unified
PromptRequest prompter (`veles.core.permission.prompt`) instead.

Approval records (M73) are written through the same path the trust
ladder uses, so the audit log carries a uniform shape.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any


def _default_prompter(tool_name: str, arguments: dict[str, Any], reason: str) -> bool:
    """Stderr/stdin prompt for the interactive `veles run` path.

    Pre-condition: stdin is a TTY. When it isn't (CI, piped scripts,
    daemon flow) the caller should install its own prompter explicitly —
    the default refuses non-interactive contexts so we never block a
    headless run on input that will never come.
    """
    if not sys.stdin.isatty():
        print(
            f"warning: {tool_name!r} requested approval but stdin is non-interactive; "
            f"denying by default",
            file=sys.stderr,
        )
        return False
    print(
        f"\nApproval required for tool {tool_name!r}:\n"
        f"  reason:    {reason}\n"
        f"  arguments: {arguments}\n"
        f"Approve? [y/N] ",
        file=sys.stderr,
        end="",
        flush=True,
    )
    try:
        ans = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n(no answer; denying)", file=sys.stderr)
        return False
    return ans in ("y", "yes")


@dataclass(slots=True, frozen=True)
class ApprovalAnswer:
    """Outcome of a single approval prompt — used by the dispatch path
    to decide whether to upgrade the decision and write a record."""

    approved: bool
    reason: str


def ask_for_approval(tool_name: str, arguments: dict[str, Any], reason: str) -> ApprovalAnswer:
    """Wrap the prompter call with a stable return shape.

    Uses the unified PromptRequest-based prompter if one is installed
    in the active ContextVar scope (TUI / Telegram install it); falls
    back to `_default_prompter` (stderr/stdin) otherwise. Exceptions
    from either prompter degrade to a hard deny — we never let a bug
    in a custom prompter block a run silently.
    """
    from veles.core.permission.prompt import (
        PromptRequest,
        current_prompter as _unified_prompter,
    )

    try:
        unified = _unified_prompter()
        if unified is not None:
            req = PromptRequest(
                tool_name=tool_name,
                arguments=arguments,
                reason=reason,
                kind="approval",
            )
            answer = unified(req)
            approved = answer.approved
        else:
            approved = _default_prompter(tool_name, arguments, reason)
    except Exception as exc:  # noqa: BLE001
        print(
            f"warning: approval prompter raised {type(exc).__name__}: {exc}; denying",
            file=sys.stderr,
        )
        approved = False
    return ApprovalAnswer(approved=approved, reason=reason)


__all__ = [
    "ApprovalAnswer",
    "ask_for_approval",
]
