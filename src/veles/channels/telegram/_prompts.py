"""Prompt rendering (trust / approval / clarification) for Telegram.

Three flavours of daemon prompt land here:
- `trust_prompt` — once / always_project / always_global / refuse
- `approval_prompt` — yes / no
- `clarification_prompt` (M116c) — manager-emitted free-form question
  with arbitrary options plus an optional "type your own" entry.

Telegram's `callback_data` is capped at 64 bytes per button, so we send
a short code per option and decode it back via the `short_to_key` map
attached to the `_PendingTelegramPrompt`."""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from typing import Any

from veles.channels.telegram_format import escape_html


@dataclass(slots=True)
class _PendingTelegramPrompt:
    """One inline-keyboard prompt the gateway is waiting on. Cached so
    that an inbound `callback_query` can be routed back to the right
    run, and so `prompt_resolved` can clear the buttons on the original
    message."""

    run_id: str
    chat_id: int
    message_id: int
    kind: str
    short_to_key: dict[str, str]
    # Inline-keyboard buttons accept arbitrary `callback_data` strings
    # up to 64 bytes. We send a short code per option (`o`/`p`/`r`,
    # `y`/`n`) and decode here.


# Short codes for callback_data — Telegram's 64-byte limit means we
# can't put the full TrustChoice / ApprovalAnswer key inline; pick a
# 1-char marker per kind that round-trips back to the daemon's key.
_TRUST_SHORT_BY_KEY: dict[str, str] = {
    "once": "o",
    "always_project": "p",
    "always_global": "g",
    "refuse": "r",
}
_APPROVAL_SHORT_BY_KEY: dict[str, str] = {"yes": "y", "no": "n"}


def _build_buttons(
    prompt_id: str,
    kind: str,
    options: list[Any],
) -> tuple[list[str], list[dict[str, str]], dict[str, str]]:
    """Convert the daemon's option list into a Telegram `inline_keyboard`
    row plus a `short → key` mapping the callback handler decodes.

    Returns (`short_codes`, `buttons`, `short_to_key`).

    For `trust` / `approval` prompts the short codes come from the
    fixed tables (o/p/g/r and y/n). For `clarification` prompts (M116c)
    the option set is arbitrary — generic index-based shorts (`0`,
    `1`, `2`, …) are issued in option order; the `short_to_key`
    mapping carries them back to the daemon's key string.
    """
    shorts: list[str] = []
    buttons: list[dict[str, str]] = []
    short_to_key: dict[str, str] = {}
    if kind == "trust":
        short_table = _TRUST_SHORT_BY_KEY
    elif kind == "approval":
        short_table = _APPROVAL_SHORT_BY_KEY
    else:
        short_table = None  # clarification → index shorts
    for idx, opt in enumerate(options):
        if not isinstance(opt, dict):
            continue
        key = opt.get("key")
        label = opt.get("label")
        if not isinstance(key, str) or not isinstance(label, str):
            continue
        if short_table is not None:
            short = short_table.get(key)
            if short is None:
                continue
        else:
            short = str(idx)
        shorts.append(short)
        short_to_key[short] = key
        buttons.append({"text": label, "callback_data": f"v:{prompt_id}:{short}"})
    return shorts, buttons, short_to_key


def _format_prompt_body(kind: str, event: dict[str, Any]) -> str:
    """Render a trust/approval/clarification prompt as Telegram-HTML
    with emoji and no raw Python `repr()` or dict dumps. Argument
    values run through `core.sanitize` so paths/secrets don't leak
    into the prompt body."""
    from veles.core.sanitize import sanitize

    tool = str(event.get("tool") or "?")
    if kind == "clarification":
        question = str(event.get("question") or "(no question)")
        return (
            f"❓ <b>The agent needs your input</b>\n"
            f"{escape_html(sanitize(question))}\n\n"
            f"Tap an option below, or reply with a free-form answer."
        )
    # trust + approval share the same body shape (M124-perm-unify): both
    # show the tool, the reason, and the rendered arguments so the user
    # can see what the agent is about to do before granting consent.
    # The header emoji + leading line differ — trust offers the four-way
    # scoped ladder, approval is a two-way per-call y/N.
    reason = str(event.get("reason") or "(no reason supplied)")
    args = event.get("arguments") or {}
    if kind == "trust":
        header = (
            f"🔧 <b>Tool:</b> <code>{escape_html(tool)}</code> wants to run."
        )
    else:
        header = (
            f"🔐 <b>Approval required</b>\n"
            f"🔧 <b>Tool:</b> <code>{escape_html(tool)}</code>"
        )
    return (
        f"{header}\n"
        f"📝 <b>Reason:</b> {escape_html(sanitize(reason))}\n"
        f"📋 <b>Arguments:</b>\n{_render_prompt_args(args)}"
    )


def _render_prompt_args(args: Any) -> str:
    """Format tool arguments as a bullet list suitable for Telegram-HTML.

    Scalar values inline, dicts/lists into a `<pre>` JSON block. Strings
    > 200 chars are trimmed. Empty/no args → `(none)`."""
    from veles.core.sanitize import sanitize

    if not isinstance(args, dict) or not args:
        return "(none)"
    lines: list[str] = []
    for key, value in args.items():
        key_html = escape_html(str(key))
        if isinstance(value, (str, int, float, bool)) or value is None:
            text = str(value)
            text = sanitize(text)
            if len(text) > 200:
                text = text[:200] + "…"
            lines.append(f"• <code>{key_html}</code>: {escape_html(text)}")
        else:
            try:
                dumped = _json.dumps(value, indent=2, ensure_ascii=False)
            except (TypeError, ValueError):
                dumped = repr(value)
            dumped = sanitize(dumped)
            if len(dumped) > 400:
                dumped = dumped[:400] + "\n…"
            lines.append(
                f"• <code>{key_html}</code>:\n<pre>{escape_html(dumped)}</pre>"
            )
    return "\n".join(lines)
