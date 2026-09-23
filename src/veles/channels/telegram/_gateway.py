"""TelegramGateway — orchestration core of the Telegram channel.

Why not python-telegram-bot: that library is ~15MB plus a sync/async
fork, and we only need three endpoints. Rolling our own keeps the
dependency surface minimal (just aiohttp, already a daemon dep) and
gives us direct control over rate-limit handling.

M155 decomposition: the gateway keeps the lifecycle (poll loop, task
spawning, buffers/debounce, update routing, prompt/callback state) and
delegates the rest to three collaborators, called directly:

  - `_api.py` (`TelegramApi`) — raw Bot-API I/O.
  - `_media.py` (`TelegramMedia`) — voice, photo and document intake.
  - `_delivery.py` (`TelegramDelivery`) — placeholder, event-stream
    drain, final delivery, typing loop (+ the `_TurnOutcome` dataclass).

The collaborators hold a back-reference to the gateway and send through
its `_call` / `_send_message` / `_edit_message` / `_download_telegram_file`
seams, so a stubbed `_telegram_send` (or a class-level patch of those
four) intercepts all Telegram traffic.

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
    _FORWARD_BUFFER_HARD_CAP,
    _FORWARD_DEBOUNCE_SECONDS,
    _ChatBuffer,
    _classify,
    _is_relayed,
    _Kind,
)
from veles.channels.telegram._delivery import TelegramDelivery
from veles.channels.telegram._forwarded import (
    _forward_header,
    _has_forward,
    _render_forwarded,
)
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
    # Aggregation window; None = the `_DEBOUNCE_SECONDS` default.
    debounce_seconds: float | None = None
    # Wider window used once the buffer holds a forward / album item;
    # None = the `_FORWARD_DEBOUNCE_SECONDS` default.
    forward_debounce_seconds: float | None = None
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

        # `/`-commands bypass the aggregator — instant, no buffer. The
        # dispatcher in `_telegram_commands.py` returns ready-to-send HTML.
        from veles.channels._telegram_commands import dispatch, parse_command

        text = (message.get("text") or "").strip()
        parsed = parse_command(text)
        if parsed is not None:
            cmd, args = parsed
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

        # M284: while the agent waits on a question (`ask_user`), the next text is
        # its answer — not a new turn, which would queue behind the waiting one
        # and let the question time out.
        if text and await self._answer_open_question(chat_id, text):
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
        for the debounce window. Every message waits it out — including a
        lone text — so a burst sent in quick succession (a comment +
        forwarded messages, a multi-message paste) coalesces into one
        turn instead of firing a premature reply on the first piece.
        Buffer hits the hard cap → flush right away so the user doesn't
        wait forever during a flood.

        Relayed content (a forward, an album item — see `_is_relayed`)
        widens both: Telegram itself tells us the user is relaying
        something from elsewhere, and the comment that frames it lands
        seconds after the last forward, well past the base window."""
        buf = self._buffers.get(chat_key)
        if buf is None:
            buf = _ChatBuffer(chat_id=chat_id, chat_key=chat_key)
            self._buffers[chat_key] = buf
        buf.cancel_timer()
        buf.messages.append(message)
        # Sticky: once anything relayed lands, the whole burst gets the wide
        # treatment — including the plain-text comment that closes it.
        buf.relayed = buf.relayed or _is_relayed(message)
        cap = _FORWARD_BUFFER_HARD_CAP if buf.relayed else _BUFFER_HARD_CAP
        if len(buf.messages) >= cap:
            await self._flush_buffer(chat_key)
            return
        loop = asyncio.get_running_loop()
        buf.timer = loop.call_later(
            self._window_for(buf),
            lambda: self._spawn(self._flush_buffer(chat_key)),
        )

    def _window_for(self, buf: _ChatBuffer) -> float:
        if buf.relayed:
            return (
                self.forward_debounce_seconds
                if self.forward_debounce_seconds is not None
                else _FORWARD_DEBOUNCE_SECONDS
            )
        return self.debounce_seconds if self.debounce_seconds is not None else _DEBOUNCE_SECONDS

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
        the origin). Without an adapter voice gets a one-line "not
        configured" notice, while a photo is saved to `attachment_dir`
        and the prompt points the agent at `image_describe` — no vision
        adapter needed when the project's model can already see.
        """
        parts: list[str] = []
        attachments: list[Path] = []
        for message in messages:
            doc = message.get("document")
            voice = message.get("voice") or message.get("audio")
            photo = message.get("photo")
            content: str | None = None
            if isinstance(doc, dict):
                saved = await self._media.save_telegram_document(chat_id, doc)
                if saved is not None:
                    attachments.append(saved)
                    content = ""
            elif isinstance(voice, dict):
                content = await self._media.transcribe_voice(chat_id, voice)
            elif isinstance(photo, list) and photo:
                content = await self._media.describe_photo(chat_id, photo)
            else:
                if _has_forward(message):
                    parts.append(_render_forwarded(message))
                elif text := (message.get("text") or "").strip():
                    parts.append(text)
                continue
            # Media skips the text path's forward rendering, so the
            # `↪️ Forwarded from …` attribution is added here — otherwise a
            # relayed photo reads as the user's own.
            if content is not None:
                parts.extend(p for p in (_forward_header(message), content) if p)
            if caption := (message.get("caption") or "").strip():
                parts.append(caption)
        if not parts and not attachments:
            return
        prompt = _build_combined_prompt(parts, attachments, self.project_root)
        # Anchor UX on the most recent buffered message.
        trigger_id = messages[-1].get("message_id")
        await self._run_turn_serial(chat_id, chat_key, prompt, trigger_id=trigger_id)

    async def _run_turn_serial(
        self,
        chat_id: int,
        chat_key: str,
        prompt: str,
        *,
        trigger_id: int | None = None,
        mode: str | None = None,
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
                await self._api.set_message_reaction(chat_id, trigger_id, "👀")
            else:
                with contextlib.suppress(Exception):
                    await self._send_message(chat_id, t("telegram.ack_queued"))
        async with lock:
            await self._run_turn(chat_id, chat_key, prompt, reply_to=reply_to, mode=mode)

    async def _run_turn(
        self,
        chat_id: int,
        chat_key: str,
        text: str,
        *,
        reply_to: int | None = None,
        mode: str | None = None,
    ) -> None:
        """Pipeline: submit_run → placeholder → drain stream with
        typing indicator → final edit.

        M108 dropped intermediate edits; M-R2.4 split the pipeline into
        helper methods so each step is testable in isolation."""
        run_id = await self._submit_or_report(chat_id, chat_key, text, mode=mode)
        if run_id is None:
            return
        message_id = await self._delivery.send_placeholder(chat_id, reply_to=reply_to)
        if message_id is None:
            return
        async with self._typing_indicator(chat_id):
            outcome = await self._delivery.drain_stream(run_id, chat_id, message_id)
        await self._delivery.deliver(chat_id, chat_key, message_id, outcome)

    async def _submit_or_report(
        self, chat_id: int, chat_key: str, text: str, *, mode: str | None = None
    ) -> str | None:
        """Submit the user's text to the daemon and return the run_id,
        or None after surfacing the failure to the user. `mode` switches the
        chat's agent mode first (`/goal <task>`); omitted otherwise, so a
        backend without mode support still serves ordinary messages."""
        session_id = self.session_map.get(chat_key)
        extra = {"mode": mode} if mode is not None else {}
        try:
            run = await self.daemon_client.submit_run(
                text, session_id=session_id, origin=f"telegram:{chat_id}", **extra
            )
        except (DaemonClientError, ValueError) as exc:
            await self._send_message(chat_id, f"<daemon error: {exc}>")
            return None
        run_id = run.get("run_id")
        if not isinstance(run_id, str):
            await self._send_message(chat_id, "<daemon error: missing run_id>")
            return None
        return run_id

    @contextlib.asynccontextmanager
    async def _typing_indicator(self, chat_id: int):
        """Async context manager: starts a typing-loop background task,
        cancels it on exit (success or exception). Errors inside the
        loop are swallowed — the indicator is advisory."""
        task = asyncio.create_task(self._delivery.typing_loop(chat_id))
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # ---- Telegram I/O seams (collaborators and tests route through these) ----

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
    ) -> dict[str, Any] | None:
        return await self._api.edit_message(
            chat_id,
            message_id,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            link_preview_options=link_preview_options,
        )

    async def deliver(self, chat_id: str, text: str, thread_id: str | None = None) -> None:
        """M165: outbound delivery entry point for the `DeliveryRouter`.

        Send `text` (agent Markdown, e.g. a scheduled job's report or a
        reminder) to `chat_id`, rendered through the Telegram-allowed HTML
        subset like a normal turn. Registered onto the daemon's router by
        `start_channel_runners`, so `deliver_to = "telegram:<chat>"` jobs
        actually reach the user instead of only landing in `.veles/jobs/`.

        `thread_id` (forum topics) is accepted to satisfy the
        `PlatformDeliverer` signature but unused for direct chats."""
        from veles.channels.telegram_format import (
            markdown_to_telegram_html,
            split_telegram_html,
        )

        del thread_id  # forum topics unsupported for direct delivery (M165)
        chunks = split_telegram_html(markdown_to_telegram_html(text or ""))
        await self._delivery.send_chunks(int(chat_id), chunks)

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
        if not buttons and kind != "clarification":
            return
        body = _format_prompt_body(kind, event)
        if kind == "clarification":
            # M284: an agent's question — options (free-form labels, often long)
            # one per row; none at all is fine, the reply is typed.
            markup = {"inline_keyboard": [[b] for b in buttons]} if buttons else None
            sent = await self._send_message(chat_id, body, reply_markup=markup)
        else:
            sent = await self._send_message(
                chat_id, body, reply_markup={"inline_keyboard": [buttons]}
            )
        message_id = sent.get("message_id")
        if not isinstance(message_id, int):
            return
        self._pending_prompts[prompt_id] = _PendingTelegramPrompt(
            run_id=run_id,
            chat_id=chat_id,
            message_id=message_id,
            kind=kind,
            short_to_key=short_to_key,
            question=str(event.get("question") or ""),
            labels={
                str(o["key"]): str(o["label"])
                for o in options
                if isinstance(o, dict) and "key" in o and "label" in o
            },
        )
        del short_codes  # unused after building the keyboard row

    async def _answer_open_question(self, chat_id: int, text: str) -> bool:
        """M284: hand `text` to the agent's open question in this chat, if one
        is waiting; True when it was taken as the answer. A question that
        already timed out (the daemon refuses) lets the text through as an
        ordinary message."""
        for prompt_id, pending in list(self._pending_prompts.items()):
            if pending.kind != "clarification" or pending.chat_id != chat_id:
                continue
            try:
                await self.daemon_client.submit_prompt_answer(pending.run_id, prompt_id, text)
            except Exception as exc:
                # Timed out or already answered — the daemon's `prompt_resolved`
                # clears it; here the text simply becomes a normal message.
                self._pending_prompts.pop(prompt_id, None)
                logger.info("telegram: question %s no longer open: %s", prompt_id, exc)
                return False
            return True  # `prompt_resolved` edits the question message
        return False

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
        if pending.kind == "clarification" and isinstance(choice, str):
            choice = (pending.labels or {}).get(choice, choice)  # option key → its label
        if reason == "timeout":
            tail = "⌛ timed out"
        elif isinstance(choice, str):
            tail = f"✓ {escape_html(choice)}"
        else:
            tail = "✓ resolved"
        if pending.kind == "clarification":
            body = f"❓ {escape_html(pending.question)}\n{tail}"
        else:
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
            await self._api.answer_callback_query(callback_id, text="not allowed")
            return

        parts = data.split(":", 2)
        kind = parts[0] if parts else ""

        if kind == "v":
            # Existing trust/approval flow
            if len(parts) != 3:
                await self._api.answer_callback_query(callback_id)
                return
            prompt_id, short = parts[1], parts[2]
            pending = self._pending_prompts.get(prompt_id)
            if pending is None:
                await self._api.answer_callback_query(
                    callback_id, text="this prompt has already closed"
                )
                return
            full_key = pending.short_to_key.get(short)
            if full_key is None:
                await self._api.answer_callback_query(callback_id, text="unknown choice")
                return
            try:
                await self.daemon_client.submit_prompt_answer(pending.run_id, prompt_id, full_key)
            except DaemonClientError as exc:
                await self._api.answer_callback_query(callback_id, text=f"daemon error: {exc}")
                return
            await self._api.answer_callback_query(callback_id, text="✓")
            return

        if kind == "mo":
            # M127: only `/mode` (mo:) remains; the `/model` picker
            # callbacks (m:, mn:, mc:) were removed — model is fixed.
            await self._handle_settings_callback(callback, callback_id, kind, parts)
            return

        # Unknown prefix — silently dismiss spinner
        await self._api.answer_callback_query(callback_id)

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
            await self._api.answer_callback_query(callback_id, text="missing chat")
            return
        chat_key = str(chat_id)
        session_id = self.session_map.get(chat_key)
        if not session_id:
            await self._api.answer_callback_query(
                callback_id,
                text="send a message first to start a session",
            )
            return

        if kind == "mo":
            # `mo:<mode>` — one of `_MODE_CHOICES` (default/auto/planning/writing);
            # the daemon validates it (unknown → 400 / ValueError).
            if len(parts) < 2 or not parts[1]:
                await self._api.answer_callback_query(callback_id, text="bad payload")
                return
            mode = parts[1]
            try:
                await self.daemon_client.update_session(session_id, mode=mode)
            except (DaemonClientError, AttributeError, ValueError) as exc:
                await self._api.answer_callback_query(
                    callback_id, text=f"could not set mode: {exc}"
                )
                return
            await self._api.answer_callback_query(callback_id, text=f"✓ mode → {mode}")
            return

        # M127: only `mo:` (mode) reaches here now. The `/model` picker
        # branch (`m:`) and its pagination/cancel handlers
        # (`_handle_model_page_callback`, `_handle_model_cancel_callback`)
        # were removed — model/provider are fixed at daemon launch.
        await self._api.answer_callback_query(callback_id)

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

    async def _download_telegram_file(self, file_id: str, expected_size: int) -> bytes:
        return await self._api.download_telegram_file(file_id, expected_size)
