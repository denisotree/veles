"""Daemon-side prompters that route trust / approval / critical-op questions and
the agent's `ask_user` to a channel client (e.g. Telegram) via the run's event
stream.

The agent's permission engine calls whatever ContextVar prompter is installed.
Inside `veles daemon`, without these, the defaults check `sys.stdin.isatty()`
and auto-refuse — so a Telegram-originated run could never invoke a sensitive
tool or ask the user anything.

Every prompter here goes through `_ask`, which (on the agent's worker thread):

  1. allocates an 8-char hex `prompt_id`,
  2. registers a `PendingPrompt` (carrying a `concurrent.futures.Future`)
     on `handle.pending_prompts`,
  3. emits a `<kind>_prompt` event to the run's stream via
     `loop.call_soon_threadsafe(handle.append_event, …)`,
  4. blocks on `future.result(timeout)`,
  5. returns the channel's raw answer, or None on timeout — each prompter then
     maps that to its own safest outcome.

The other half is `RunHandle.resolve_prompt`, called from
`POST /v1/runs/{run_id}/prompts/{prompt_id}` or the in-process backend."""

from __future__ import annotations

import asyncio
import logging
import secrets
from concurrent.futures import TimeoutError as _FuturesTimeout
from typing import Any

from veles.core.critical_ops import Confirmer
from veles.core.permission.prompt import (
    PromptAnswer,
    PromptRequest,
)
from veles.core.permission.prompt import (
    Prompter as UnifiedPrompter,
)
from veles.daemon.runner import PendingPrompt, RunHandle

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TIMEOUT_SECONDS = 300.0
"""Five minutes — matches the user-chosen UX in the plan. Configurable
per call if a channel needs a different SLA."""

# Telegram shows these as inline-keyboard buttons. Trust omits "always global":
# a daemon is bound to one project.
_TRUST_OPTIONS_TELEGRAM: tuple[dict[str, str], ...] = (
    {"key": "once", "label": "⏱ Once"},
    {"key": "always_project", "label": "🔓 Always for this project"},
    {"key": "refuse", "label": "🚫 Refuse"},
)

_APPROVAL_OPTIONS_TELEGRAM: tuple[dict[str, str], ...] = (
    {"key": "yes", "label": "✅ Allow"},
    {"key": "no", "label": "❌ Deny"},
)

_CRITICAL_OPTIONS_TELEGRAM: tuple[dict[str, str], ...] = (
    {"key": "yes", "label": "⚠️ Allow"},
    {"key": "no", "label": "🚫 Cancel"},
)

_TRUST_DECISION_BY_KEY: dict[str, str] = {
    "once": "allow_once",
    "always_project": "allow_project",
    "always_global": "allow_global",
    "refuse": "deny",
}


def _ask(  # noqa: PLR0913
    handle: RunHandle,
    loop: asyncio.AbstractEventLoop,
    *,
    kind: str,
    subject: str,
    payload: dict[str, Any],
    options: tuple[dict[str, str], ...] | list[dict[str, str]],
    timeout: float,
    free_text: bool = False,
    timeout_choice: str | None = None,
) -> str | None:
    """Put one question to the channel and wait for its answer (see the module
    docstring). `timeout_choice`, when given, is recorded on the timeout's
    `prompt_resolved` event as the choice taken."""
    prompt_id = secrets.token_hex(4)
    pending = PendingPrompt(
        kind=kind,
        tool=subject,
        valid_choices=tuple(opt["key"] for opt in options),
        free_text=free_text,
    )
    handle.pending_prompts[prompt_id] = pending
    loop.call_soon_threadsafe(
        handle.append_event,
        {"type": f"{kind}_prompt", "prompt_id": prompt_id, **payload, "options": list(options)},
    )
    try:
        return pending.future.result(timeout=timeout)
    except _FuturesTimeout:
        logger.info("%s prompt %s for %r timed out after %.0fs", kind, prompt_id, subject, timeout)
        handle.pending_prompts.pop(prompt_id, None)
        resolved = {"type": "prompt_resolved", "prompt_id": prompt_id, "reason": "timeout"}
        if timeout_choice is not None:
            resolved["choice"] = timeout_choice
        loop.call_soon_threadsafe(handle.append_event, resolved)
        return None


def make_unified_prompter(
    handle: RunHandle,
    loop: asyncio.AbstractEventLoop,
    *,
    timeout: float = DEFAULT_PROMPT_TIMEOUT_SECONDS,
) -> UnifiedPrompter:
    """One PromptRequest-based prompter for trust and approval, routed by
    `req.kind`; `arguments` and `reason` go to the channel so it can show what
    the agent wants to do. Anything but an explicit allow is a deny."""

    def prompter(req: PromptRequest) -> PromptAnswer:
        payload = {"tool": req.tool_name, "arguments": req.arguments, "reason": req.reason}
        if req.kind == "trust":
            key = _ask(
                handle,
                loop,
                kind="trust",
                subject=req.tool_name,
                payload=payload,
                options=_TRUST_OPTIONS_TELEGRAM,
                timeout=timeout,
                timeout_choice="refuse",
            )
            return PromptAnswer(_TRUST_DECISION_BY_KEY.get(key or "refuse", "deny"))  # type: ignore[arg-type]
        if req.kind == "approval":
            key = _ask(
                handle,
                loop,
                kind="approval",
                subject=req.tool_name,
                payload=payload,
                options=_APPROVAL_OPTIONS_TELEGRAM,
                timeout=timeout,
            )
            return PromptAnswer("allow_once" if key == "yes" else "deny")
        return PromptAnswer("deny")

    return prompter


def make_critical_confirmer(
    handle: RunHandle,
    loop: asyncio.AbstractEventLoop,
    *,
    timeout: float = DEFAULT_PROMPT_TIMEOUT_SECONDS,
) -> Confirmer:
    """Route `confirm_critical` (always-confirm ops and the exfiltration gate)
    to the channel as a `critical_prompt`; the payload carries `op`/`summary`,
    the `Confirmer` contract. Deny on timeout, cancel or anything but a literal
    `"yes"` — critical ops stay fail-closed. Installed per run by
    `run_agent_in_background`, overriding the daemon's auto-deny confirmer."""

    def confirmer(op: str, summary: str) -> bool:
        answer = _ask(
            handle,
            loop,
            kind="critical",
            subject=op,
            payload={"op": op, "summary": summary},
            options=_CRITICAL_OPTIONS_TELEGRAM,
            timeout=timeout,
        )
        return answer == "yes"

    return confirmer


def make_question_prompter(
    handle: RunHandle,
    loop: asyncio.AbstractEventLoop,
    *,
    timeout: float = DEFAULT_PROMPT_TIMEOUT_SECONDS,
):
    """Route the agent's `ask_user` to the chat as a `clarification_prompt`:
    the options, if any, become buttons, and any text the user types in reply
    is taken as the answer (`free_text`). Returns the chosen option's label,
    the typed answer, or None on timeout — `ask_user` then tells the agent to
    proceed on its best assumption."""

    def prompter(question: str, options: list[str] | None = None) -> str | None:
        choices = list(options or [])
        buttons = [{"key": str(i), "label": c} for i, c in enumerate(choices)]
        answer = _ask(
            handle,
            loop,
            kind="clarification",
            subject="ask_user",
            payload={"question": question},
            options=buttons,
            timeout=timeout,
            free_text=True,
        )
        if answer is None:
            return None
        if answer in {b["key"] for b in buttons}:
            return choices[int(answer)]
        return answer.strip() or None

    return prompter


__all__ = [
    "DEFAULT_PROMPT_TIMEOUT_SECONDS",
    "make_critical_confirmer",
    "make_question_prompter",
    "make_unified_prompter",
]
