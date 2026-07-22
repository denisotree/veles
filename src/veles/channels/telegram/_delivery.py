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
    markdown_to_telegram_html,
    split_telegram_html,
)

if TYPE_CHECKING:
    from veles.channels.telegram._gateway import TelegramGateway

logger = logging.getLogger(__name__)

# Agent answers are prose-first; incidental links shouldn't render as
# large preview cards that flood the chat. Disable previews on answers.
_NO_LINK_PREVIEW = {"is_disabled": True}


@dataclass(frozen=True, slots=True)
class _TurnOutcome:
    """Result of draining the daemon's event stream for one turn.

    `text` is None when the stream ended without producing anything
    (network drop before first delta). `error` is set when the run
    failed; in that case `_deliver` formats it visibly for the user.
    `acked` is True when the placeholder was already edited into a
    contextual "on it" ack (the agent's first action was a tool call),
    so `deliver` sends the final answer as a NEW message instead of
    overwriting the ack."""

    text: str | None
    session_id: str | None
    error: str | None
    acked: bool = False


class TelegramDelivery:
    __slots__ = ("_gw",)

    def __init__(self, gateway: TelegramGateway) -> None:
        self._gw = gateway

    async def send_placeholder(self, chat_id: int, *, reply_to: int | None = None) -> int | None:
        """Post the "..." holder we'll edit on completion. Returns the
        message_id, or None when Telegram refused the send.

        `reply_to` (group chats) threads the whole turn under the user's
        message. `allow_sending_without_reply` keeps the turn alive if
        that message was deleted before we replied."""
        reply_parameters = (
            {"message_id": reply_to, "allow_sending_without_reply": True}
            if reply_to is not None
            else None
        )
        placeholder = await self._gw._send_message(
            chat_id, _PLACEHOLDER_TEXT, reply_parameters=reply_parameters
        )
        mid = placeholder.get("message_id")
        return mid if isinstance(mid, int) else None

    async def drain_stream(
        self, run_id: str, chat_id: int, message_id: int | None = None
    ) -> _TurnOutcome:
        """Walk the daemon's event stream, ignoring intermediate text
        deltas (M108 — no live typing), and harvest the final text +
        session id + any error.

        When the agent's FIRST action is a tool call (search, write,
        build…), edit the `...` placeholder (identified by `message_id`)
        into a contextual "on it" ack once — a single edit, not the M108
        per-delta stream — so the user sees work started instead of a
        bare `...`. A text-first turn shows no ack and edits straight to
        the answer.

        New event types (M-channel-prompts):
          - `trust_prompt` / `approval_prompt` / `critical_prompt` (M213)
            — daemon paused the agent and is waiting for the user's
            permission decision. We POST a message with an inline
            keyboard and keep streaming; the user's button tap arrives
            separately as a Telegram `callback_query` and is routed to
            the daemon via `submit_prompt_answer`.
          - `prompt_resolved` — daemon got the answer (from us or via
            timeout) and is moving on. Clear our pending entry and
            strip the buttons on the original prompt message."""
        gw = self._gw
        buffer = ""
        completed_session: str | None = None
        completed_text: str | None = None
        error: str | None = None
        acked = False
        try:
            async for event in gw.daemon_client.stream_events(run_id):
                kind = event.get("type")
                # Adopt the session id from the FIRST event that carries one
                # (the daemon now puts it on `started`, so a mid-run error or
                # stream drop still leaves us a mapping to persist — the chat
                # keeps its session instead of restarting empty next turn).
                sid = event.get("session_id")
                if isinstance(sid, str) and sid:
                    completed_session = sid
                if kind == "text_delta":
                    delta = event.get("delta") or ""
                    if isinstance(delta, str) and delta:
                        buffer += delta
                elif kind == "tool_call":
                    # First tool call before any answer text → the turn needs
                    # work; show a contextual ack in place of the "..." holder.
                    if not acked and not buffer and message_id is not None:
                        acked = await self._show_ack(chat_id, message_id, event.get("name"))
                elif kind == "completed":
                    text_out = event.get("text")
                    if isinstance(text_out, str):
                        completed_text = text_out
                elif kind == "error":
                    err = event.get("error")
                    error = str(err) if err else "unknown error"
                elif kind in ("trust_prompt", "approval_prompt", "critical_prompt"):
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
            acked=acked,
        )

    async def _show_ack(self, chat_id: int, message_id: int, tool_name: Any) -> bool:
        """Edit the placeholder into the contextual "on it" ack for the
        agent's first tool call. Best-effort — a failed edit must not
        break the turn, so a failure just leaves the "..." in place and
        reports no ack (the final answer then overwrites it)."""
        from veles.channels.telegram._helpers import ack_key_for_tool
        from veles.core.i18n import t

        try:
            await self._gw._edit_message(chat_id, message_id, t(ack_key_for_tool(str(tool_name))))
            return True
        except Exception:
            return False

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
        # Long answers are split into ≤-limit chunks rather than truncated:
        # each chunk is independently valid (tags reopened across the split).
        chunks = split_telegram_html(final_html)
        if outcome.acked:
            # The placeholder already shows the "on it" ack — keep it as the
            # progress line and deliver the answer as fresh message(s), so the
            # user gets the spec'd "accepted → final" two-message experience.
            for chunk in chunks:
                await gw._send_message(chat_id, chunk, link_preview_options=_NO_LINK_PREVIEW)
        else:
            # No ack shown: the "..." holder becomes the answer's first chunk.
            await gw._edit_message(
                chat_id, message_id, chunks[0], link_preview_options=_NO_LINK_PREVIEW
            )
            for extra in chunks[1:]:
                await gw._send_message(chat_id, extra, link_preview_options=_NO_LINK_PREVIEW)
        # Persist the chat→session mapping whenever we learned a session id —
        # including on error. The session was already created and the user
        # turn stored before any failure, so the next message must continue
        # that same session, not open a fresh (empty) one.
        if outcome.session_id:
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

    async def send_manager_plan_notice(self, chat_id: int, event: dict[str, Any]) -> None:
        """M124: render the manager-spawn plan as a chat message so the
        user sees what's happening before the writer's final text lands.
        Format mirrors the WorkerPlan checkbox renderer."""
        steps = event.get("steps") or []
        roles = [str(s.get("role", "?")) for s in steps if isinstance(s, dict)]
        if not roles:
            return
        roles_label = ", ".join(roles)
        body = f"🧠 <i>Decomposing into {len(roles)} workers: {escape_html(roles_label)}…</i>"
        await self._gw._send_message(chat_id, body)
