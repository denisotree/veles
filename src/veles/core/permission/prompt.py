"""Unified prompt-request shape for the Permission Engine.

Before this module, two parallel prompter contracts lived side by side:
the M38 trust-ladder prompter (`(str) -> TrustChoice`, no args) and the
M71 approval prompter (`(str, dict, str) -> bool`, args present).
The split forced two render paths in every UI (TUI, Telegram, CLI),
and the trust path silently dropped tool arguments — users saw
`Tool 'run_shell' wants to execute` without the actual command.

`PromptRequest` is the single shape every UI receives. `PromptAnswer`
carries one of five outcomes — the trust path uses all of them, the
approval path only the first two. `format_prompt_body` is the shared
render helper that takes care of value-level truncation; UI wrappers
keep their own framing (Telegram-HTML, Textual widget, stderr).
"""

from __future__ import annotations

import json as _json
from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Literal

PromptKind = Literal["trust", "approval"]

PromptDecision = Literal[
    "allow_once",
    "allow_session",
    "allow_project",
    "allow_global",
    "deny",
]


@dataclass(slots=True, frozen=True)
class PromptRequest:
    """One permission prompt the engine needs answered.

    `kind="trust"` accepts all five PromptDecision values (M38 ladder
    persistence semantics — allow_project / allow_global write into
    `<scope>/trust.json`). `kind="approval"` accepts only
    `allow_once / allow_session / deny` (M71 turn-scope semantics).
    Engine validates the answer against the kind; an out-of-band value
    degrades to `deny`.
    """

    tool_name: str
    arguments: dict[str, Any]
    reason: str = ""
    kind: PromptKind = "trust"


@dataclass(slots=True, frozen=True)
class PromptAnswer:
    """Outcome of one prompt. See `PromptDecision` for semantics."""

    decision: PromptDecision

    @property
    def approved(self) -> bool:
        return self.decision != "deny"


Prompter = Callable[[PromptRequest], PromptAnswer]


# ---------------- rendering ----------------


def format_prompt_body(
    req: PromptRequest,
    *,
    max_value_chars: int = 1000,
) -> str:
    """Plain-text body shared by every prompt UI.

    Format:
        Tool: <name>
        Reason: <reason or "(unspecified)">
        Arguments:
          <key>: <value>
          ...

    Scalar values are stringified; long ones get a soft truncate at
    `max_value_chars` with a `(total N chars)` suffix. dict/list values
    are JSON-dumped (indent=2) and truncated the same way. Empty args
    render as `Arguments: (none)`.

    The Telegram channel formats arguments separately via
    `_render_prompt_args` (HTML, harder limit) — this helper is for
    plain-text surfaces (TUI body, CLI stderr).
    """

    lines = [
        f"Tool: {req.tool_name}",
        f"Reason: {req.reason or '(unspecified)'}",
    ]
    if not req.arguments:
        lines.append("Arguments: (none)")
    else:
        lines.append("Arguments:")
        for key, value in req.arguments.items():
            lines.append(f"  {key}: {_render_value(value, max_value_chars)}")
    return "\n".join(lines)


def _render_value(value: Any, max_chars: int) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = str(value)
    else:
        try:
            text = _json.dumps(value, indent=2, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = repr(value)
    if len(text) > max_chars:
        return f"{text[:max_chars]}… (total {len(text)} chars)"
    return text


# ---------------- prompter ContextVar ----------------

_active: ContextVar[Prompter | None] = ContextVar("veles_unified_prompter", default=None)


def current_prompter() -> Prompter | None:
    """Return the unified prompter set for this ContextVar scope.

    `None` when no unified prompter is installed — callers fall back to
    the interactive default prompters (see core/trust.py and
    core/approval_prompter.py).
    """

    return _active.get()


def set_prompter(p: Prompter) -> Token[Prompter | None]:
    return _active.set(p)


def reset_prompter(token: Token[Prompter | None]) -> None:
    _active.reset(token)


__all__ = [
    "PromptAnswer",
    "PromptDecision",
    "PromptKind",
    "PromptRequest",
    "Prompter",
    "current_prompter",
    "format_prompt_body",
    "reset_prompter",
    "set_prompter",
]
