"""TelegramGateway — orchestration core of the Telegram channel.

Why not python-telegram-bot: that library is ~15MB plus a sync/async
fork, and we only need three endpoints. Rolling our own keeps the
dependency surface minimal (just aiohttp, already a daemon dep) and
gives us direct control over rate-limit handling.

M155 decomposition: the gateway keeps the lifecycle (poll loop, task
spawning, buffers/debounce, update routing, prompt/callback state) and
delegates the rest to three collaborators, each holding a back-
reference to the gateway so instance/class-level stubs on
`TelegramGateway` keep working:

  - `_api.py` (`TelegramApi`) — raw Bot-API I/O: `_call`,
    `_send_message`, `_edit_message`, `_answer_callback_query`,
    `_send_chat_action`, `_download_telegram_file`.
  - `_media.py` (`TelegramMedia`) — `_transcribe_voice`,
    `_describe_photo`, `_save_telegram_document`, `_persist_attachment`.
  - `_delivery.py` (`TelegramDelivery`) — `_send_placeholder`,
    `_drain_stream`, `_deliver`, `_typing_loop`,
    `_send_manager_plan_notice` (+ the `_TurnOutcome` dataclass).

Every delegated name survives on the gateway as a thin async delegate
with an identical signature.

Long-polling loop:

    while running:
        updates = getUpdates(offset=last_id+1, timeout=30)
        for u in updates:
            spawn handle_update(u)

Per-update flow:

    chat_id ↔ session_id from SessionMap (created lazily on first msg).
    Show "typing" → POST /v1/runs → WS /v1/runs/{id}/events.
    Buffer text_delta. Edit Telegram message every 500ms or every 200 chars.
    On `completed`: final edit with full text + flush session_id back.
    On `error`: edit with "<error: ...>".

`/start` and `/reset` shortcuts: `/start` shows a greeting; `/reset`
forgets the chat's session mapping so the next message starts fresh.

Rate-limit safety: editMessageText is the cheap path (no global cap
per chat); we still cooldown 500ms between edits to avoid hammering.
Telegram's per-chat sendMessage cap is 1/sec — we only send once per
turn (the initial placeholder), then edit it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp

from veles.channels.daemon_client import DaemonClientError
from veles.channels.protocols import RunBackend
from veles.channels.session_map import SessionMap
from veles.channels.telegram._api import TelegramApi
from veles.channels.telegram._buffer import (
    _BUFFER_HARD_CAP,
    _DEBOUNCE_SECONDS,
    _ChatBuffer,
    _classify,
    _Kind,
)
from veles.channels.telegram._delivery import TelegramDelivery, _TurnOutcome
from veles.channels.telegram._forwarded import _has_forward, _render_forwarded
from veles.channels.telegram._helpers import (
    _LONG_POLL_TIMEOUT,
    _POLL_RETRY_INITIAL,
    _POLL_RETRY_MAX,
    _TELEGRAM_API,
    _build_combined_prompt,
)
from veles.channels.telegram._media import TelegramMedia
from veles.channels.telegram._prompts import (
    _build_buttons,
    _format_prompt_body,
    _PendingTelegramPrompt,
)
from veles.channels.telegram_format import escape_html
from veles.core.i18n import t

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TelegramGateway:
    bot_token: str
    daemon_client: RunBackend  # DaemonClient (HTTP) or InProcessRunBackend
    session_map: SessionMap
    name: str = "telegram"
    whitelist: tuple[str, ...] = field(default_factory=tuple)
    # Where to drop documents the user uploads. None disables attachment
    # handling (the bot replies that attachments aren't configured).
    # Production daemon sets this to `<project>/.veles/tmp/`.
    attachment_dir: Path | None = None
    # Project root for building `read_file(...)` paths inside the prompt.
    # When None we fall back to attachment basenames.
    project_root: Path | None = None
    _running: bool = field(default=False, init=False)
    _http: aiohttp.ClientSession | None = field(default=None, init=False)
    _telegram_send: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = field(
        default=None, init=False
    )
    _offset: int = field(default=0, init=False)
    _tasks: set = field(default_factory=set, init=False)
    _pending_prompts: dict[str, _PendingTelegramPrompt] = field(default_factory=dict, init=False)
    # M127: the Telegram `/model` picker was removed (model/provider are
    # fixed at daemon launch), so the picker state fields
    # (`_model_callbacks`, `_daemon_provider`, `_daemon_default_model`,
    # `_model_refresh_pending`, `_model_list_cache`) are gone too.
    # Per-chat aggregation: forward+comment / document+comment arrive as
    # two separate updates; a debouncer merges them into one turn.
    _buffers: dict[str, _ChatBuffer] = field(default_factory=dict, init=False)
    # Per-chat serial execution: one turn per chat at a time. A message
    # arriving while a turn runs waits on the chat's lock (FIFO) and gets
    # a "queued" ack up front. Different chats stay fully parallel.
    _chat_locks: dict[str, asyncio.Lock] = field(default_factory=dict, init=False)
    # M155 collaborators. They hold a back-reference to the gateway and
    # call through `self._gw.<method>` so instance/class-level stubs on
    # the gateway keep working.
    _api: TelegramApi = field(init=False, repr=False)
    _media: TelegramMedia = field(init=False, repr=False)
    _delivery: TelegramDelivery = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._api = TelegramApi(self)
        self._media = TelegramMedia(self)
        self._delivery = TelegramDelivery(self)

    @property
    def api_base(self) -> str:
        return f"{_TELEGRAM_API}/bot{self.bot_token}"

    # ---- lifecycle ----

    async def start(self) -> None:
        if self._http is None:
            # M210: explicit timeouts. aiohttp's default is a 5-minute *total*
            # cap and nothing else, so a hung DNS lookup / dead connect stalled
            # a poll for minutes and then surfaced as a bare `TimeoutError`
            # whose str() is empty (the `getUpdates failed:` log lines with no
            # reason). Long-poll reads idle up to `_LONG_POLL_TIMEOUT` between
            # bytes, so `sock_read` stays comfortably above it.
            self._http = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(
                    total=None,
                    connect=10,
                    sock_connect=10,
                    sock_read=_LONG_POLL_TIMEOUT + 15,
                )
            )
        self._running = True
        # M116.1: publish the command menu so users see the supported
        # commands in Telegram's `/`-tap interface. Best-effort —
        # failure to publish doesn't block the polling loop (the
        # commands still work, just won't autocomplete in the client).
        try:
            await self._publish_command_menu()
        except Exception:
            logger.warning("telegram: setMyCommands failed; menu may be stale")
        try:
            await self._poll_loop()
        finally:
            await self.stop()

    async def _publish_command_menu(self) -> None:
        from veles.channels._telegram_commands import menu_descriptors

        await self._call("setMyCommands", {"commands": menu_descriptors()})

    async def stop(self) -> None:
        self._running = False
        if self._http is not None:
            await self._http.close()
            self._http = None

    # ---- transport (delegates → TelegramApi, M155) ----

    async def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST `payload` to `api_base/<method>` and return the parsed `result` field."""
        return await self._api.call(method, payload)

    # ---- poll loop ----

    async def _poll_loop(self) -> None:
        # M210: exponential backoff with log suppression. A machine that goes
        # offline (sleep, no Wi-Fi) fails every poll with the same DNS error;
        # log the first failure, any *change* of error text, and a periodic
        # heartbeat — not one WARNING per retry — and say when we recover.
        delay = _POLL_RETRY_INITIAL
        failures = 0
        last_error = ""
        while self._running:
            try:
                updates = await self._get_updates()
            except Exception as exc:
                failures += 1
                message = str(exc) or repr(exc)  # bare TimeoutError str() is ""
                if failures == 1 or message != last_error or failures % 30 == 0:
                    logger.warning("getUpdates failed (attempt %d): %s", failures, message)
                last_error = message
                await asyncio.sleep(delay)
                delay = min(delay * 2, _POLL_RETRY_MAX)
                continue
            if failures:
                logger.info("getUpdates recovered after %d failed polls", failures)
                failures = 0
                last_error = ""
                delay = _POLL_RETRY_INITIAL
            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    self._offset = max(self._offset, update_id + 1)
                task = asyncio.create_task(self._safe_handle(update))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

    async def _get_updates(self) -> list[dict[str, Any]]:
        payload = {"offset": self._offset, "timeout": _LONG_POLL_TIMEOUT}
        # getUpdates is a GET endpoint per Telegram docs but accepts POST with
        # JSON body — use POST for uniformity.
        result = await self._call("getUpdates", payload)
        raw = result.get("raw") if "raw" in result else result
        if isinstance(raw, list):
            return [u for u in raw if isinstance(u, dict)]
        return []

    async def _safe_handle(self, update: dict[str, Any]) -> None:
        try:
            await self._handle_update(update)
        except Exception as exc:
            logger.exception("handle_update failed: %s", exc)

    # ---- update handling ----

    async def _handle_update(self, update: dict[str, Any]) -> None:
        callback = update.get("callback_query")
        if isinstance(callback, dict):
            await self._handle_callback_query(callback)
            return
        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if not isinstance(chat_id, int):
            return
        if not self._is_allowed(message):
            logger.info(
                "telegram: dropped update from non-whitelisted sender %r",
                (message.get("from") or {}).get("id"),
            )
            return
        chat_key = str(chat_id)

        # `/`-commands bypass the aggregator — instant, no buffer.
        # `/start` and `/reset` are owned by the gateway flow (they
        # mutate session_map directly); every other slash-command is
        # handled by the M116.1 dispatcher in `_telegram_commands.py`,
        # which returns ready-to-send HTML and never touches gateway
        # state.
        from veles.channels._telegram_commands import dispatch, parse_command

        text = (message.get("text") or "").strip()
        parsed = parse_command(text)
        if parsed is not None:
            cmd, args = parsed
            if cmd == "start":
                await self._send_message(chat_id, t("telegram.start_greeting"))
                return
            if cmd == "reset":
                removed = self.session_map.reset(chat_key)
                await self._send_message(
                    chat_id,
                    t("telegram.history_cleared") if removed else t("telegram.history_empty"),
                )
                return
            reply = await dispatch(self, chat_key, cmd, args)
            if reply is not None:
                # Empty string = handler already sent its own message
                # (e.g. inline-keyboard pickers) — skip the auto-reply.
                if reply.strip():
                    await self._send_message(chat_id, reply)
                return
            # Unknown slash-command: hint at /help instead of treating
            # the text as a regular message (which would send it to the
            # agent and produce a confusing reply).
            await self._send_message(
                chat_id,
                f"Unknown command: /{cmd}. Send /help for the list.",
            )
            return

        kind = _classify(message)
        if kind is _Kind.IGNORED:
            return  # photo-only / voice / sticker — silently dropped, as before

        logger.info(
            "telegram: chat=%s kind=%s text_len=%d caption_len=%d preview=%r",
            chat_key,
            kind.value,
            len(text),
            len(message.get("caption") or ""),
            text[:80] or (message.get("caption") or "")[:80],
        )
        await self._enqueue(chat_key, chat_id, message)

    # ---- aggregation pipeline (DOC-4 / DOC-5) ----

    async def _enqueue(self, chat_key: str, chat_id: int, message: dict[str, Any]) -> None:
        """Place an incoming message into the per-chat buffer, deferred
        for `_DEBOUNCE_SECONDS`. Every message waits out the window —
        including a lone text — so a burst sent in quick succession
        (a comment + forwarded messages, a multi-message paste) coalesces
        into one turn instead of firing a premature reply on the first
        piece. Buffer hits `_BUFFER_HARD_CAP` → flush right away so the
        user doesn't wait forever during a flood."""
        buf = self._buffers.get(chat_key)
        if buf is None:
            buf = _ChatBuffer(chat_id=chat_id, chat_key=chat_key)
            self._buffers[chat_key] = buf
        buf.cancel_timer()
        buf.messages.append(message)
        if len(buf.messages) >= _BUFFER_HARD_CAP:
            await self._flush_buffer(chat_key)
            return
        loop = asyncio.get_running_loop()
        buf.timer = loop.call_later(
            _DEBOUNCE_SECONDS,
            lambda: self._spawn(self._flush_buffer(chat_key)),
        )

    def _spawn(self, coro) -> None:
        """Fire-and-forget for callbacks that can't await. The task is
        tracked in `_tasks` so it isn't GC'd mid-flight."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _flush_buffer(self, chat_key: str) -> None:
        buf = self._buffers.pop(chat_key, None)
        if buf is None or not buf.messages:
            return
        buf.cancel_timer()
        await self._dispatch_messages(buf.chat_id, chat_key, buf.messages)

    async def _dispatch_messages(
        self, chat_id: int, chat_key: str, messages: list[dict[str, Any]]
    ) -> None:
        """Collapse buffered messages into one prompt and run one turn.

        Order in the prompt mirrors arrival order: forwarded post first,
        user's comment second — that's how a human reads it. Documents
        are downloaded inline (so any reject/ack the user needs to see
        is sent before the agent starts thinking).

        Multimodal (M-multimodal-dispatch): voice and photo messages
        consult `veles.modules.get_{stt,vision}_adapter()`. When an
        adapter is registered, the file is fetched, transcribed /
        described, and the resulting text is folded into the prompt
        (with a `[voice: …]` / `[photo: …]` marker so the agent knows
        the origin). When no adapter is registered, the channel sends
        a one-line `multimodal not configured` notice instead of
        silently dropping the input.
        """
        parts: list[str] = []
        attachments: list[Path] = []
        for message in messages:
            doc = message.get("document")
            if isinstance(doc, dict):
                saved = await self._save_telegram_document(chat_id, doc)
                if saved is not None:
                    attachments.append(saved)
                caption = (message.get("caption") or "").strip()
                if caption:
                    parts.append(caption)
                continue
            voice = message.get("voice") or message.get("audio")
            if isinstance(voice, dict):
                transcript = await self._transcribe_voice(chat_id, voice)
                if transcript is not None:
                    parts.append(transcript)
                caption = (message.get("caption") or "").strip()
                if caption:
                    parts.append(caption)
                continue
            photo = message.get("photo")
            if isinstance(photo, list) and photo:
                description = await self._describe_photo(chat_id, photo)
                if description is not None:
                    parts.append(description)
                caption = (message.get("caption") or "").strip()
                if caption:
                    parts.append(caption)
                continue
            if _has_forward(message):
                parts.append(_render_forwarded(message))
                continue
            text = (message.get("text") or "").strip()
            if text:
                parts.append(text)
        if not parts and not attachments:
            return
        prompt = _build_combined_prompt(parts, attachments, self.project_root)
        # Anchor UX on the most recent buffered message.
        trigger_id = messages[-1].get("message_id")
        await self._run_turn_serial(chat_id, chat_key, prompt, trigger_id=trigger_id)

    async def _run_turn_serial(
        self, chat_id: int, chat_key: str, prompt: str, *, trigger_id: int | None = None
    ) -> None:
        """Run one turn under the chat's serial lock. If a turn is already
        in flight for this chat, acknowledge the wait (a 👀 reaction on the
        message, or a queued text if the message can't be reacted to)
        before waiting on the lock — the daemon also serializes per
        session, but the lock lets us surface the wait and keep FIFO order
        at the channel edge."""
        # In group chats (negative chat_id) thread the answer to the
        # triggering message so it's clear which one it answers; in 1:1
        # chats threading is just visual noise.
        reply_to = trigger_id if chat_id < 0 else None
        lock = self._chat_locks.get(chat_key)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_key] = lock
        if lock.locked():
            # A 👀 reaction keeps a busy chat quiet instead of piling up
            # "queued" messages; fall back to text when there's no message
            # to react to.
            if trigger_id is not None:
                await self._set_reaction(chat_id, trigger_id, "👀")
            else:
                with contextlib.suppress(Exception):
                    await self._send_message(chat_id, t("telegram.ack_queued"))
        async with lock:
            await self._run_turn(chat_id, chat_key, prompt, reply_to=reply_to)

    # ---- media (delegates → TelegramMedia, M155) ----

    async def _transcribe_voice(self, chat_id: int, voice: dict[str, Any]) -> str | None:
        return await self._media.transcribe_voice(chat_id, voice)

    async def _describe_photo(self, chat_id: int, photo: list[dict[str, Any]]) -> str | None:
        return await self._media.describe_photo(chat_id, photo)

    async def _run_turn(
        self, chat_id: int, chat_key: str, text: str, *, reply_to: int | None = None
    ) -> None:
        """Pipeline: submit_run → placeholder → drain stream with
        typing indicator → final edit.

        M108 dropped intermediate edits; M-R2.4 split the pipeline into
        helper methods so each step is testable in isolation."""
        run_id = await self._submit_or_report(chat_id, chat_key, text)
        if run_id is None:
            return
        message_id = await self._send_placeholder(chat_id, reply_to=reply_to)
        if message_id is None:
            return
        async with self._typing_indicator(chat_id):
            outcome = await self._drain_stream(run_id, chat_id, message_id)
        await self._deliver(chat_id, chat_key, message_id, outcome)

    async def _submit_or_report(self, chat_id: int, chat_key: str, text: str) -> str | None:
        """Submit the user's text to the daemon and return the run_id,
        or None after surfacing the failure to the user."""
        session_id = self.session_map.get(chat_key)
        try:
            run = await self.daemon_client.submit_run(
                text, session_id=session_id, origin=f"telegram:{chat_id}"
            )
        except DaemonClientError as exc:
            await self._send_message(chat_id, f"<daemon error: {exc}>")
            return None
        run_id = run.get("run_id")
        if not isinstance(run_id, str):
            await self._send_message(chat_id, "<daemon error: missing run_id>")
            return None
        return run_id

    async def _send_placeholder(self, chat_id: int, *, reply_to: int | None = None) -> int | None:
        return await self._delivery.send_placeholder(chat_id, reply_to=reply_to)

    @contextlib.asynccontextmanager
    async def _typing_indicator(self, chat_id: int):
        """Async context manager: starts a typing-loop background task,
        cancels it on exit (success or exception). Errors inside the
        loop are swallowed — the indicator is advisory."""
        task = asyncio.create_task(self._typing_loop(chat_id))
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _drain_stream(
        self, run_id: str, chat_id: int, message_id: int | None = None
    ) -> _TurnOutcome:
        return await self._delivery.drain_stream(run_id, chat_id, message_id)

    async def _deliver(
        self,
        chat_id: int,
        chat_key: str,
        message_id: int,
        outcome: _TurnOutcome,
    ) -> None:
        await self._delivery.deliver(chat_id, chat_key, message_id, outcome)

    async def _typing_loop(self, chat_id: int) -> None:
        await self._delivery.typing_loop(chat_id)

    # ---- Telegram wrappers ----

    async def _send_manager_plan_notice(self, chat_id: int, event: dict[str, Any]) -> None:
        await self._delivery.send_manager_plan_notice(chat_id, event)

    async def _send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = "HTML",
        link_preview_options: dict[str, Any] | None = None,
        reply_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._api.send_message(
            chat_id,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            link_preview_options=link_preview_options,
            reply_parameters=reply_parameters,
        )

    async def _edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = "HTML",
        link_preview_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._api.edit_message(
            chat_id,
            message_id,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            link_preview_options=link_preview_options,
        )

    async def _set_reaction(self, chat_id: int, message_id: int, emoji: str) -> None:
        await self._api.set_message_reaction(chat_id, message_id, emoji)

    async def _answer_callback_query(self, callback_id: str, *, text: str | None = None) -> None:
        await self._api.answer_callback_query(callback_id, text=text)

    async def deliver(self, chat_id: str, text: str, thread_id: str | None = None) -> None:
        """M165: outbound delivery entry point for the `DeliveryRouter`.

        Send `text` (agent Markdown, e.g. a scheduled job's report or a
        reminder) to `chat_id`, rendered through the Telegram-allowed HTML
        subset like a normal turn. Registered onto the daemon's router by
        `_start_channel_runners`, so `deliver_to = "telegram:<chat>"` jobs
        actually reach the user instead of only landing in `.veles/jobs/`.

        `thread_id` (forum topics) is accepted to satisfy the
        `PlatformDeliverer` signature but unused for direct chats."""
        from veles.channels.telegram_format import (
            markdown_to_telegram_html,
            split_telegram_html,
        )

        del thread_id  # forum topics unsupported for direct delivery (M165)
        for chunk in split_telegram_html(markdown_to_telegram_html(text or "")):
            await self._send_message(
                int(chat_id), chunk, link_preview_options={"is_disabled": True}
            )

    # M127: `_refresh_daemon_health` / `_get_daemon_provider` /
    # `_get_active_model_for` were removed with the Telegram `/model`
    # picker — model/provider are fixed at daemon launch from config.

    # ---- prompt rendering / answering ----

    async def _post_prompt(self, chat_id: int, run_id: str, event: dict[str, Any]) -> None:
        """Render a `trust_prompt` / `approval_prompt` daemon event as a
        Telegram message with an inline keyboard. Cache the
        `prompt_id → (run, message, options)` mapping so an inbound
        button tap can resolve it back to the daemon."""
        prompt_id = event.get("prompt_id")
        kind_raw = event.get("type")
        options = event.get("options") or []
        if not isinstance(prompt_id, str) or not isinstance(options, list):
            return
        # trust_prompt → "trust", approval_prompt → "approval",
        # clarification_prompt → "clarification" (M116c, manager-emitted
        # question), critical_prompt → "critical" (M213, always-confirm /
        # exfiltration gate — the channel mirror of the REPL's hard-confirm).
        if kind_raw == "trust_prompt":
            kind = "trust"
        elif kind_raw == "clarification_prompt":
            kind = "clarification"
        elif kind_raw == "critical_prompt":
            kind = "critical"
        else:
            kind = "approval"
        short_codes, buttons, short_to_key = _build_buttons(prompt_id, kind, options)
        if not buttons:
            return
        body = _format_prompt_body(kind, event)
        reply_markup = {"inline_keyboard": [buttons]}
        sent = await self._send_message(chat_id, body, reply_markup=reply_markup)
        message_id = sent.get("message_id")
        if not isinstance(message_id, int):
            return
        self._pending_prompts[prompt_id] = _PendingTelegramPrompt(
            run_id=run_id,
            chat_id=chat_id,
            message_id=message_id,
            kind=kind,
            short_to_key=short_to_key,
        )
        del short_codes  # unused after building the keyboard row

    async def _finalise_prompt_message(self, event: dict[str, Any]) -> None:
        """`prompt_resolved` — strip the buttons on the original prompt
        message and append the chosen answer (or `timeout`) for context.
        Idempotent: a `prompt_resolved` for an already-cleaned prompt is
        a no-op."""
        prompt_id = event.get("prompt_id")
        if not isinstance(prompt_id, str):
            return
        pending = self._pending_prompts.pop(prompt_id, None)
        if pending is None:
            return
        choice = event.get("choice")
        reason = event.get("reason")
        if reason == "timeout":
            tail = "⌛ timed out"
        elif isinstance(choice, str):
            tail = f"✓ {escape_html(choice)}"
        else:
            tail = "✓ resolved"
        body = f"<i>{escape_html(pending.kind)} resolved</i> · {tail}"
        # `reply_markup={}` (no `inline_keyboard`) is how the Bot API
        # removes a previously-set keyboard.
        await self._edit_message(
            pending.chat_id, pending.message_id, body, reply_markup={"inline_keyboard": []}
        )

    async def _handle_callback_query(self, callback: dict[str, Any]) -> None:
        """Inbound button tap. Parse `callback_data`, dispatch by prefix:
        - `v:` — trust/approval prompt resolution (existing)
        - `mo:` — mode switch (Telegram /mode inline keyboard)
        (M127: the `m:`/`mn:`/`mc:` model-picker prefixes were removed.)

        Dismiss the Telegram client-side spinner regardless of outcome
        so the user doesn't see a perpetual loading state."""
        callback_id = callback.get("id")
        data = callback.get("data") or ""
        if not isinstance(callback_id, str) or not isinstance(data, str):
            return
        # Whitelist filter applies to taps too — same identity gate as
        # text messages.
        msg = {"from": callback.get("from") or {}}
        if not self._is_allowed(msg):
            await self._answer_callback_query(callback_id, text="not allowed")
            return

        parts = data.split(":", 2)
        kind = parts[0] if parts else ""

        if kind == "v":
            # Existing trust/approval flow
            if len(parts) != 3:
                await self._answer_callback_query(callback_id)
                return
            prompt_id, short = parts[1], parts[2]
            pending = self._pending_prompts.get(prompt_id)
            if pending is None:
                await self._answer_callback_query(
                    callback_id, text="this prompt has already closed"
                )
                return
            full_key = pending.short_to_key.get(short)
            if full_key is None:
                await self._answer_callback_query(callback_id, text="unknown choice")
                return
            try:
                await self.daemon_client.submit_prompt_answer(pending.run_id, prompt_id, full_key)
            except DaemonClientError as exc:
                await self._answer_callback_query(callback_id, text=f"daemon error: {exc}")
                return
            await self._answer_callback_query(callback_id, text="✓")
            return

        if kind == "mo":
            # M127: only `/mode` (mo:) remains; the `/model` picker
            # callbacks (m:, mn:, mc:) were removed — model is fixed.
            await self._handle_settings_callback(callback, callback_id, kind, parts)
            return

        # Unknown prefix — silently dismiss spinner
        await self._answer_callback_query(callback_id)

    async def _handle_settings_callback(
        self,
        callback: dict[str, Any],
        callback_id: str,
        kind: str,
        parts: list[str],
    ) -> None:
        """Handle `/mode` button taps (`mo:<mode>`). Resolves session_id
        from chat_id and PATCHes the daemon. (M127: the `/model` picker
        that also routed here was removed — model is fixed at launch.)"""
        chat = callback.get("message", {}).get("chat") or {}
        chat_id = chat.get("id")
        if not isinstance(chat_id, int):
            await self._answer_callback_query(callback_id, text="missing chat")
            return
        chat_key = str(chat_id)
        session_id = self.session_map.get(chat_key)
        if not session_id:
            await self._answer_callback_query(
                callback_id,
                text="send a message first to start a session",
            )
            return

        if kind == "mo":
            # `mo:<mode>` — mode is exactly one of auto/planning/writing/goal
            if len(parts) < 2 or not parts[1]:
                await self._answer_callback_query(callback_id, text="bad payload")
                return
            mode = parts[1]
            try:
                await self.daemon_client.update_session(  # type: ignore[attr-defined]
                    session_id, mode=mode
                )
            except (DaemonClientError, AttributeError) as exc:
                await self._answer_callback_query(callback_id, text=f"could not set mode: {exc}")
                return
            await self._answer_callback_query(callback_id, text=f"✓ mode → {mode}")
            return

        # M127: only `mo:` (mode) reaches here now. The `/model` picker
        # branch (`m:`) and its pagination/cancel handlers
        # (`_handle_model_page_callback`, `_handle_model_cancel_callback`)
        # were removed — model/provider are fixed at daemon launch.
        await self._answer_callback_query(callback_id)

    def _is_allowed(self, message: dict[str, Any]) -> bool:
        """Return True iff the sender is on the whitelist (or the whitelist is empty).

        Whitelist entries are matched case-insensitively against both the
        numeric `from.id` (as decimal string) and `from.username` (with or
        without leading `@`). An empty whitelist disables the filter.
        """
        if not self.whitelist:
            return True
        sender = message.get("from") or {}
        sender_id = sender.get("id")
        sender_user = (sender.get("username") or "").lower().lstrip("@")
        for raw in self.whitelist:
            entry = raw.strip().lstrip("@").lower()
            if not entry:
                continue
            if entry.isdigit() and isinstance(sender_id, int) and str(sender_id) == entry:
                return True
            if not entry.isdigit() and sender_user and sender_user == entry:
                return True
        return False

    async def _send_chat_action(self, chat_id: int, action: str) -> None:
        await self._api.send_chat_action(chat_id, action)

    # ---- attachment download / persist (DOC-3) ----

    async def _download_telegram_file(self, file_id: str, expected_size: int) -> bytes:
        return await self._api.download_telegram_file(file_id, expected_size)

    def _persist_attachment(self, name: str, data: bytes) -> Path:
        return self._media.persist_attachment(name, data)

    async def _save_telegram_document(self, chat_id: int, document: dict[str, Any]) -> Path | None:
        return await self._media.save_telegram_document(chat_id, document)
