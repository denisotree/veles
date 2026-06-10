"""Turn delivery collaborator (M155 extraction from `_gateway.py`).

`TelegramDelivery` owns the daemon-stream → Telegram half of a turn:
the "..." placeholder, draining the daemon's event stream into a
`_TurnOutcome`, the final placeholder edit, the typing-indicator
refresh loop and the manager-plan notice. The orchestration itself
(`_run_turn`, `_typing_indicator` task lifecycle) stays in the gateway
— task spawning and cancellation are untouched by the split.

Test-compat invariant: all Telegram and daemon I/O goes back through
the gateway (`self._gw._send_message`, `self._gw._post_prompt`,
`self._gw.daemon_client`, ...) so instance-level stubs and class-level
patches on `TelegramGateway` keep working."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from veles.channels.daemon_client import DaemonClientError
from veles.channels.telegram._helpers import _PLACEHOLDER_TEXT
from veles.channels.telegram_format import (
    escape_html,
    html_safe_truncate,
    markdown_to_telegram_html,
)

if TYPE_CHECKING:
    from veles.channels.telegram._gateway import TelegramGateway

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _TurnOutcome:
    """Result of draining the daemon's event stream for one turn.

    `text` is None when the stream ended without producing anything
    (network drop before first delta). `error` is set when the run
    failed; in that case `_deliver` formats it visibly for the user."""

    text: str | None
    session_id: str | None
    error: str | None


class TelegramDelivery:
    __slots__ = ("_gw",)

    def __init__(self, gateway: TelegramGateway) -> None:
        self._gw = gateway

    async def send_placeholder(self, chat_id: int) -> int | None:
        """Post the "..." holder we'll edit on completion. Returns the
        message_id, or None when Telegram refused the send."""
        placeholder = await self._gw._send_message(chat_id, _PLACEHOLDER_TEXT)
        mid = placeholder.get("message_id")
        return mid if isinstance(mid, int) else None

    async def drain_stream(self, run_id: str, chat_id: int) -> _TurnOutcome:
        """Walk the daemon's event stream, ignoring intermediate text
        deltas (M108 — no live typing), and harvest the final text +
        session id + any error.

        New event types (M-channel-prompts):
          - `trust_prompt` / `approval_prompt` — daemon paused the agent
            and is waiting for the user's permission decision. We POST
            a message with an inline keyboard and keep streaming; the
            user's button tap arrives separately as a Telegram
            `callback_query` and is routed to the daemon via
            `submit_prompt_answer`.
          - `prompt_resolved` — daemon got the answer (from us or via
            timeout) and is moving on. Clear our pending entry and
            strip the buttons on the original prompt message."""
        gw = self._gw
        buffer = ""
        completed_session: str | None = None
        completed_text: str | None = None
        error: str | None = None
        try:
            async for event in gw.daemon_client.stream_events(run_id):
                kind = event.get("type")
                if kind == "text_delta":
                    delta = event.get("delta") or ""
                    if isinstance(delta, str) and delta:
                        buffer += delta
                elif kind == "completed":
                    text_out = event.get("text")
                    if isinstance(text_out, str):
                        completed_text = text_out
                    sid = event.get("session_id")
                    if isinstance(sid, str):
                        completed_session = sid
                elif kind == "error":
                    err = event.get("error")
                    error = str(err) if err else "unknown error"
                elif kind in ("trust_prompt", "approval_prompt"):
                    await gw._post_prompt(chat_id, run_id, event)
                elif kind == "prompt_resolved":
                    await gw._finalise_prompt_message(event)
                elif kind == "manager_plan":
                    # M124: surface manager-spawn decomposition before
                    # the writer's text lands. Best-effort — never
                    # break the turn if the send fails.
                    with contextlib.suppress(Exception):
                        await gw._send_manager_plan_notice(chat_id, event)
        except DaemonClientError as exc:
            error = str(exc)
        return _TurnOutcome(
            text=completed_text or buffer or None,
            session_id=completed_session,
            error=error,
        )

    async def deliver(
        self,
        chat_id: int,
        chat_key: str,
        message_id: int,
        outcome: _TurnOutcome,
    ) -> None:
        """Edit the placeholder once with the final text, then persist
        the chat→session mapping when the run completed cleanly. The
        model's answer is treated as Markdown and rendered through the
        Telegram-allowed HTML subset (`markdown_to_telegram_html`)."""
        gw = self._gw
        if outcome.error:
            final_html = f"<b>⚠️ error:</b> {escape_html(outcome.error)}"
        elif outcome.text:
            final_html = markdown_to_telegram_html(outcome.text)
        else:
            final_html = escape_html(_PLACEHOLDER_TEXT)
        await gw._edit_message(chat_id, message_id, html_safe_truncate(final_html))
        if outcome.session_id and not outcome.error:
            gw.session_map.set(chat_key, outcome.session_id)

    async def typing_loop(self, chat_id: int) -> None:
        """Re-send `sendChatAction "typing"` every 4 seconds until cancelled.

        Telegram's typing indicator auto-clears after ~5 seconds, so we
        refresh it slightly faster to keep the dot-dot-dot animation
        running while the model is generating. Errors are swallowed —
        chat-actions are advisory and should never break the turn.
        """
        gw = self._gw
        try:
            while True:
                with contextlib.suppress(Exception):
                    await gw._send_chat_action(chat_id, "typing")
                await asyncio.sleep(4.0)
        except asyncio.CancelledError:
            raise

    async def send_manager_plan_notice(
        self, chat_id: int, event: dict[str, Any]
    ) -> None:
        """M124: render the manager-spawn plan as a chat message so the
        user sees what's happening before the writer's final text lands.
        Format mirrors the WorkerPlan checkbox renderer."""
        steps = event.get("steps") or []
        roles = [str(s.get("role", "?")) for s in steps if isinstance(s, dict)]
        if not roles:
            return
        roles_label = ", ".join(roles)
        body = (
            f"🧠 <i>Decomposing into {len(roles)} workers: "
            f"{escape_html(roles_label)}…</i>"
        )
        await self._gw._send_message(chat_id, body)
