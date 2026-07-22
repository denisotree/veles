"""Raw Telegram Bot-API I/O collaborator (M155 extraction from `_gateway.py`).

`TelegramApi` owns the HTTPS transport against api.telegram.org: the
generic `call` POST, the sendMessage / editMessageText /
answerCallbackQuery / sendChatAction wrappers, and file download.

Test-compat invariant: every method routes back through the *gateway*
(`self._gw._call`, `self._gw._telegram_send`, `self._gw._http`) so
instance-level stubs (`gateway._telegram_send = ...`) and class-level
patches on `TelegramGateway` keep working — the collaborator never
caches its own reference to the transport."""

from __future__ import annotations

import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

from veles.channels.telegram._attachments import _MAX_ATTACHMENT_BYTES
from veles.channels.telegram._helpers import (
    _TELEGRAM_API,
    _html_to_plain,
    _is_parse_error,
    _truncate,
)

if TYPE_CHECKING:
    from veles.channels.telegram._gateway import TelegramGateway

logger = logging.getLogger(__name__)


class TelegramApi:
    __slots__ = ("_gw",)

    def __init__(self, gateway: TelegramGateway) -> None:
        self._gw = gateway

    async def call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST `payload` to `api_base/<method>` and return the parsed `result` field."""
        gw = self._gw
        if gw._telegram_send is not None:
            return await gw._telegram_send(method, payload)
        assert gw._http is not None
        async with gw._http.post(f"{gw.api_base}/{method}", json=payload) as resp:
            text = await resp.text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"telegram {method}: non-JSON response {text[:200]!r}") from exc
            if not isinstance(data, dict) or not data.get("ok"):
                raise RuntimeError(f"telegram {method} failed: {text[:200]}")
            result = data.get("result")
            return result if isinstance(result, dict) else {"raw": result}

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = "HTML",
        link_preview_options: dict[str, Any] | None = None,
        reply_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": _truncate(text)}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
        if link_preview_options is not None:
            payload["link_preview_options"] = link_preview_options
        if reply_parameters is not None:
            payload["reply_parameters"] = reply_parameters
        try:
            return await self._gw._call("sendMessage", payload)
        except RuntimeError as exc:
            if parse_mode is not None and _is_parse_error(exc):
                logger.warning(
                    "telegram sendMessage parse error (%s) — retrying as plain text: %.200s",
                    exc,
                    text,
                )
                fallback = dict(payload)
                fallback.pop("parse_mode", None)
                fallback["text"] = _truncate(_html_to_plain(text))
                return await self._gw._call("sendMessage", fallback)
            raise

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = "HTML",
        link_preview_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": _truncate(text),
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
        if link_preview_options is not None:
            payload["link_preview_options"] = link_preview_options
        try:
            return await self._gw._call("editMessageText", payload)
        except RuntimeError as exc:
            if parse_mode is not None and _is_parse_error(exc):
                logger.warning(
                    "telegram editMessageText parse error (%s) — retrying as plain text: %.200s",
                    exc,
                    text,
                )
                fallback = dict(payload)
                fallback.pop("parse_mode", None)
                fallback["text"] = _truncate(_html_to_plain(text))
                try:
                    return await self._gw._call("editMessageText", fallback)
                except RuntimeError as retry_exc:
                    logger.debug("editMessageText retry failed (ignored): %s", retry_exc)
                    return {}
            logger.debug("editMessageText failed (ignored): %s", exc)
            return {}

    async def answer_callback_query(self, callback_id: str, *, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_id}
        if text is not None:
            payload["text"] = text
        with contextlib.suppress(RuntimeError):
            await self._gw._call("answerCallbackQuery", payload)

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        with contextlib.suppress(RuntimeError):
            await self._gw._call("sendChatAction", {"chat_id": chat_id, "action": action})

    async def set_message_reaction(self, chat_id: int, message_id: int, emoji: str) -> None:
        """Best-effort emoji reaction on a user's message (a light-weight
        ack). Swallows errors — the message may be unreactable or gone."""
        with contextlib.suppress(RuntimeError):
            await self._gw._call(
                "setMessageReaction",
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reaction": [{"type": "emoji", "emoji": emoji}],
                },
            )

    async def download_telegram_file(self, file_id: str, expected_size: int) -> bytes:
        """`getFile` resolves the bot-specific download URL, then GET it
        as a stream. We cap at 5 MB during the stream too, because
        `file_size` from the message metadata isn't authoritative for
        all clients."""
        del expected_size  # only used by the caller's reject check
        gw = self._gw
        meta = await gw._call("getFile", {"file_id": file_id})
        file_path = meta.get("file_path") if isinstance(meta, dict) else None
        if not isinstance(file_path, str) or not file_path:
            raise RuntimeError("getFile returned no file_path")
        assert gw._http is not None, "TelegramGateway not started (no aiohttp session)"
        url = f"{_TELEGRAM_API}/file/bot{gw.bot_token}/{file_path}"
        async with gw._http.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"download HTTP {resp.status}")
            chunks: list[bytes] = []
            read = 0
            async for chunk in resp.content.iter_chunked(64 * 1024):
                read += len(chunk)
                if read > _MAX_ATTACHMENT_BYTES:
                    raise RuntimeError("file exceeds 5 MB cap mid-download")
                chunks.append(chunk)
        return b"".join(chunks)
