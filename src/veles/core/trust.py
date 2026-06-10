"""Trust ladder per-operation (M38) — 4-option user prompt before sensitive dispatch.

Closes VISION §8 ladder. Tools marked `@tool(sensitive=True)` (currently
`run_shell`, `write_file`, `fetch_url`) require an explicit grant before
the agent can call them. On the first such call within a project, the
user sees:

    Tool 'run_shell' wants to execute. Allow?
      [1] Once (this call only)
      [2] Always for this project
      [3] Always everywhere
      [4] Refuse
    Choice [1-4, default=4]:

Choices 2 and 3 persist via `TrustStore` so subsequent calls dispatch
silently. Choice 1 grants for the current invocation only. Choice 4 (and
any unparseable input, including EOF) refuses.

The check is short-circuited by:

- `VELES_TRUST_AUTO_ALLOW=1` — bypass entirely (CI, autopilot, MCP child
  pre-authorised by parent).
- Existing user-scope or project-scope grant → silent allow.
- Tool not marked `sensitive=True` → silent allow.

Non-TTY contexts (no `sys.stdin.isatty()`) refuse by default so a batch
job can't accidentally answer the prompt with garbage stdin. Tests
inject a fake unified prompter via `veles.core.permission.prompt.set_prompter`.

Module veto from M26 (`pre_tool_call` returning `VetoResult`) wins over
the trust check — vetoed dispatches never reach this evaluator.
"""

from __future__ import annotations

import enum
import os
import sys
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

from veles.core.autopilot import is_active as _autopilot_active
from veles.core.context import current_project
from veles.core.permission.prompt import (
    PromptAnswer,
    PromptRequest,
)
from veles.core.permission.prompt import current_prompter as _unified_prompter
from veles.core.trust_store import TrustStore, user_trust_path

_AUTO_ALLOW_ENV = "VELES_TRUST_AUTO_ALLOW"


class TrustChoice(enum.Enum):
    ONCE = "once"
    ALWAYS_PROJECT = "always_project"
    ALWAYS_GLOBAL = "always_global"
    REFUSE = "refuse"


@dataclass(frozen=True, slots=True)
class TrustDecision:
    allowed: bool
    reason: str = ""
    via_autopilot: bool = False


_turn_grants: ContextVar[set[str] | None] = ContextVar("veles_turn_grants", default=None)


def begin_trust_turn() -> Token:
    """Open a fresh per-turn grant scope. Call before agent.run()."""
    return _turn_grants.set(set())


def end_trust_turn(token: Token) -> None:
    _turn_grants.reset(token)


def evaluate_trust(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    reason: str = "",
) -> TrustDecision:
    """Run the trust ladder for a sensitive tool call.

    Resolution order:
    1. `VELES_TRUST_AUTO_ALLOW=1` env → allow.
    2. Existing user-scope grant → allow.
    3. Existing project-scope grant (when an active project exists) → allow.
    4. Prompt the user (TTY) or refuse (non-TTY). Persist scoped grants.

    `arguments` and `reason` are passed to the prompter so the UI can
    show what the agent actually wants to do; the unified prompter
    receives a `PromptRequest` with the args dict populated.
    """
    if os.environ.get(_AUTO_ALLOW_ENV) == "1":
        return TrustDecision(allowed=True, reason="auto-allow")

    user_store = TrustStore.load(user_trust_path())
    if user_store.is_granted(tool_name):
        return TrustDecision(allowed=True, reason="user-scope grant")

    project = current_project()
    project_store = None
    if project is not None:
        project_store = TrustStore.load(project.trust_path)
        if project_store.is_granted(tool_name):
            return TrustDecision(allowed=True, reason="project-scope grant")

    turn = _turn_grants.get()
    if turn is not None and tool_name in turn:
        return TrustDecision(allowed=True, reason="granted once (turn)")

    if _autopilot_active():
        return TrustDecision(
            allowed=True,
            reason="autopilot window active",
            via_autopilot=True,
        )

    try:
        choice = _ask_user(tool_name, arguments or {}, reason)
    except Exception as exc:
        return TrustDecision(allowed=False, reason=f"prompt failed: {exc}")

    if choice is TrustChoice.ONCE:
        turn = _turn_grants.get()
        if turn is not None:
            turn.add(tool_name)
        return TrustDecision(allowed=True, reason="granted once")
    if choice is TrustChoice.ALWAYS_PROJECT:
        if project_store is None:
            return TrustDecision(
                allowed=True,
                reason="granted once (no active project for project-scope persistence)",
            )
        project_store.grant(tool_name)
        return TrustDecision(allowed=True, reason="granted always-project")
    if choice is TrustChoice.ALWAYS_GLOBAL:
        user_store.grant(tool_name)
        return TrustDecision(allowed=True, reason="granted always-global")
    return TrustDecision(allowed=False, reason="refused by user")


_CHOICE_ITEMS = (
    (TrustChoice.ONCE, "Once (this call only)"),
    (TrustChoice.ALWAYS_PROJECT, "Always for this project"),
    (TrustChoice.ALWAYS_GLOBAL, "Always everywhere"),
    (TrustChoice.REFUSE, "Refuse"),
)


_DECISION_TO_CHOICE = {
    "allow_once": TrustChoice.ONCE,
    "allow_session": TrustChoice.ONCE,
    "allow_project": TrustChoice.ALWAYS_PROJECT,
    "allow_global": TrustChoice.ALWAYS_GLOBAL,
    "deny": TrustChoice.REFUSE,
}


def _ask_user(
    tool_name: str, arguments: dict[str, Any], reason: str
) -> TrustChoice:
    """Resolve the user-prompt step of `evaluate_trust`.

    Uses the unified Prompter (PromptRequest → PromptAnswer) if one is
    installed in the active ContextVar scope; otherwise falls back to
    `_default_prompter` (interactive menu / non-TTY refuse).
    """
    unified = _unified_prompter()
    if unified is not None:
        req = PromptRequest(
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            kind="trust",
        )
        answer = unified(req)
        if not isinstance(answer, PromptAnswer):
            return TrustChoice.REFUSE
        return _DECISION_TO_CHOICE.get(answer.decision, TrustChoice.REFUSE)
    return _default_prompter(tool_name, arguments, reason)


def _show_interactive_menu(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    reason: str = "",
) -> TrustChoice:
    """Arrow-key menu via prompt_toolkit. Selected[0] default = 3 (Refuse)."""
    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    selected = [3]
    result = [TrustChoice.REFUSE]

    kb = KeyBindings()

    @kb.add("up")
    def _up(e):
        selected[0] = (selected[0] - 1) % len(_CHOICE_ITEMS)

    @kb.add("down")
    def _down(e):
        selected[0] = (selected[0] + 1) % len(_CHOICE_ITEMS)

    for _i in range(len(_CHOICE_ITEMS)):

        @kb.add(str(_i + 1))
        def _num(e, idx=_i):
            selected[0] = idx

    @kb.add("enter")
    def _enter(e):
        result[0] = _CHOICE_ITEMS[selected[0]][0]
        e.app.exit()

    @kb.add("escape")
    @kb.add("c-c")
    def _esc(e):
        result[0] = TrustChoice.REFUSE
        e.app.exit()

    def get_text():
        from veles.core.permission.prompt import (
            PromptRequest as _Req,
        )
        from veles.core.permission.prompt import (
            format_prompt_body as _fmt,
        )

        req = _Req(
            tool_name=tool_name,
            arguments=arguments or {},
            reason=reason,
            kind="trust",
        )
        header = "Tool wants to execute. Allow?\n\n"
        body = _fmt(req, max_value_chars=1000) + "\n\n"
        lines: list[tuple[str, str]] = [
            ("bold", header),
            ("", body),
        ]
        for i, (_, label) in enumerate(_CHOICE_ITEMS):
            if i == selected[0]:
                lines.append(("bold ansiblue", f"  ❯ {label}\n"))
            else:
                lines.append(("", f"    {label}\n"))
        lines.append(("ansibrightblack", "\n  ↑↓ navigate  Enter select  Esc refuse\n"))
        return FormattedText(lines)

    Application(
        layout=Layout(Window(FormattedTextControl(get_text, focusable=True))),
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    ).run()
    return result[0]


def _default_prompter(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    reason: str = "",
) -> TrustChoice:
    """Interactive arrow-key menu. Refuses if not a TTY.

    Takes optional `arguments` and `reason` so the menu can show what
    the agent actually wants to do.
    """
    if not sys.stdin.isatty():
        return TrustChoice.REFUSE
    return _show_interactive_menu(tool_name, arguments or {}, reason)


def _parse_choice(raw: str) -> TrustChoice:
    mapping: dict[str, TrustChoice] = {
        "1": TrustChoice.ONCE,
        "once": TrustChoice.ONCE,
        "2": TrustChoice.ALWAYS_PROJECT,
        "project": TrustChoice.ALWAYS_PROJECT,
        "3": TrustChoice.ALWAYS_GLOBAL,
        "global": TrustChoice.ALWAYS_GLOBAL,
        "4": TrustChoice.REFUSE,
        "refuse": TrustChoice.REFUSE,
        "n": TrustChoice.REFUSE,
        "no": TrustChoice.REFUSE,
        "": TrustChoice.REFUSE,
    }
    return mapping.get(raw.lower(), TrustChoice.REFUSE)
