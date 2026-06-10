"""Daemon-side prompters that route trust / approval questions to a
channel client (e.g. Telegram) via the run's event stream.

The agent's permission engine calls `evaluate_trust` / `ask_for_approval`
on whatever ContextVar prompter is installed. Inside `veles daemon`,
without a custom prompter, the defaults check `sys.stdin.isatty()` and
auto-refuse — so a Telegram-originated run can never invoke a
sensitive tool.

`make_unified_prompter` builds a prompter bound to a specific
`RunHandle`. When fired (on the agent's worker thread), it:

  1. allocates an 8-char hex `prompt_id`,
  2. registers a `PendingPrompt` (carrying a `concurrent.futures.Future`)
     on `handle.pending_prompts`,
  3. emits a `trust_prompt` / `approval_prompt` event to the WebSocket
     stream via `loop.call_soon_threadsafe(handle.append_event, …)`,
  4. blocks on `future.result(timeout)`,
  5. translates the channel's string key (`"once"` / `"yes"` / …)
     back into a `PromptAnswer` decision, or falls back to the safest
     answer on timeout / unknown value.

The HTTP endpoint `POST /v1/runs/{run_id}/prompts/{prompt_id}` (see
`daemon/server.py`) is the other half: it looks up the `PendingPrompt`
and calls `future.set_result(choice_key)`."""

from __future__ import annotations

import asyncio
import logging
import secrets
from concurrent.futures import TimeoutError as _FuturesTimeout
from typing import Any

from veles.core.permission.prompt import (
    PromptAnswer,
    PromptRequest,
    Prompter as UnifiedPrompter,
)
from veles.daemon.runner import PendingPrompt, RunHandle

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TIMEOUT_SECONDS = 300.0
"""Five minutes — matches the user-chosen UX in the plan. Configurable
per call if a channel needs a different SLA."""

_TRUST_OPTIONS_TELEGRAM: tuple[dict[str, str], ...] = (
    {"key": "once", "label": "⏱ Once"},
    {"key": "always_project", "label": "🔓 Always for this project"},
    {"key": "refuse", "label": "🚫 Refuse"},
)

_APPROVAL_OPTIONS_TELEGRAM: tuple[dict[str, str], ...] = (
    {"key": "yes", "label": "✅ Allow"},
    {"key": "no", "label": "❌ Deny"},
)

def _make_prompt_id() -> str:
    return secrets.token_hex(4)


def _dispatch_trust(
    handle: RunHandle,
    loop: asyncio.AbstractEventLoop,
    tool_name: str,
    *,
    arguments: dict[str, Any],
    reason: str,
    timeout: float,
) -> str:
    """Trust-prompt dispatch for the PromptRequest-driven prompter.
    Returns the channel's raw key string (`"once"` / `"always_project"` /
    `"refuse"` / ...); the caller translates to a `PromptAnswer` decision.

    Telegram surfaces three buttons (`Once`, `Always for this project`,
    `Refuse`); `ALWAYS_GLOBAL` is omitted because a daemon is bound to
    one project. `arguments` and `reason` go into the event payload so
    the channel can show what the agent actually wants to do.
    """
    prompt_id = _make_prompt_id()
    valid_keys = tuple(opt["key"] for opt in _TRUST_OPTIONS_TELEGRAM)
    pending = PendingPrompt(
        kind="trust",
        tool=tool_name,
        valid_choices=valid_keys,
    )
    handle.pending_prompts[prompt_id] = pending
    loop.call_soon_threadsafe(
        handle.append_event,
        {
            "type": "trust_prompt",
            "prompt_id": prompt_id,
            "tool": tool_name,
            "arguments": arguments,
            "reason": reason,
            "options": list(_TRUST_OPTIONS_TELEGRAM),
        },
    )
    try:
        answer = pending.future.result(timeout=timeout)
    except _FuturesTimeout:
        logger.info(
            "trust prompt %s for tool %r timed out after %.0fs → REFUSE",
            prompt_id,
            tool_name,
            timeout,
        )
        handle.pending_prompts.pop(prompt_id, None)
        loop.call_soon_threadsafe(
            handle.append_event,
            {
                "type": "prompt_resolved",
                "prompt_id": prompt_id,
                "choice": "refuse",
                "reason": "timeout",
            },
        )
        return "refuse"
    return answer


def _dispatch_approval(
    handle: RunHandle,
    loop: asyncio.AbstractEventLoop,
    tool_name: str,
    arguments: dict[str, Any],
    reason: str,
    *,
    timeout: float,
) -> str:
    """Approval-prompt dispatch for the unified prompter. Two outcomes —
    Allow / Deny — mirroring the modal `[y/N]`; defaults to Deny on
    timeout. Returns the raw channel key (`"yes"` / `"no"`)."""

    prompt_id = _make_prompt_id()
    valid_keys = tuple(opt["key"] for opt in _APPROVAL_OPTIONS_TELEGRAM)
    pending = PendingPrompt(
        kind="approval",
        tool=tool_name,
        valid_choices=valid_keys,
    )
    handle.pending_prompts[prompt_id] = pending
    loop.call_soon_threadsafe(
        handle.append_event,
        {
            "type": "approval_prompt",
            "prompt_id": prompt_id,
            "tool": tool_name,
            "reason": reason,
            "arguments": arguments,
            "options": list(_APPROVAL_OPTIONS_TELEGRAM),
        },
    )
    try:
        answer = pending.future.result(timeout=timeout)
    except _FuturesTimeout:
        logger.info(
            "approval prompt %s for tool %r timed out after %.0fs → deny",
            prompt_id,
            tool_name,
            timeout,
        )
        handle.pending_prompts.pop(prompt_id, None)
        loop.call_soon_threadsafe(
            handle.append_event,
            {
                "type": "prompt_resolved",
                "prompt_id": prompt_id,
                "reason": "timeout",
            },
        )
        return "no"
    return answer


# Single Prompter that routes by `req.kind`. The daemon installs this
# via `permission.prompt.set_prompter` so both trust and approval flows
# reach the channel with arguments populated.

_TRUST_DECISION_BY_KEY: dict[str, str] = {
    "once": "allow_once",
    "always_project": "allow_project",
    "always_global": "allow_global",
    "refuse": "deny",
}


def make_unified_prompter(
    handle: RunHandle,
    loop: asyncio.AbstractEventLoop,
    *,
    timeout: float = DEFAULT_PROMPT_TIMEOUT_SECONDS,
) -> UnifiedPrompter:
    """One PromptRequest-based prompter for both trust and approval.

    Routes by `req.kind` to `_dispatch_trust` / `_dispatch_approval`.
    The wire format is `trust_prompt` / `approval_prompt` event types
    with an inline-keyboard `options` payload.
    """

    def prompter(req: PromptRequest) -> PromptAnswer:
        if req.kind == "trust":
            key = _dispatch_trust(
                handle,
                loop,
                req.tool_name,
                arguments=req.arguments,
                reason=req.reason,
                timeout=timeout,
            )
            return PromptAnswer(_TRUST_DECISION_BY_KEY.get(key, "deny"))  # type: ignore[arg-type]
        if req.kind == "approval":
            key = _dispatch_approval(
                handle,
                loop,
                req.tool_name,
                req.arguments,
                req.reason,
                timeout=timeout,
            )
            return PromptAnswer("allow_once" if key == "yes" else "deny")
        return PromptAnswer("deny")

    return prompter


__all__ = [
    "DEFAULT_PROMPT_TIMEOUT_SECONDS",
    "make_unified_prompter",
]
