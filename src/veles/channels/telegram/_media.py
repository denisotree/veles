"""Media handling collaborator (M155 extraction from `_gateway.py`).

`TelegramMedia` owns voice transcription (STT adapter), photo
description (Vision adapter) and document persistence for incoming
Telegram messages. The STT/Vision adapter imports stay lazy — they are
module-registry lookups resolved per message, exactly as before the
split.

Test-compat invariant: all Telegram I/O goes back through the gateway
(`self._gw._send_message`, `self._gw._download_telegram_file`, ...) so
instance-level stubs and class-level patches on `TelegramGateway`
(e.g. `monkeypatch.setattr(TelegramGateway, "_download_telegram_file",
...)`) keep working."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from veles.channels.telegram._attachments import (
    _MAX_ATTACHMENT_BYTES,
    _reject_reason,
    _safe_filename,
)
from veles.channels.telegram_format import escape_html

if TYPE_CHECKING:
    from veles.channels.telegram._gateway import TelegramGateway

logger = logging.getLogger(__name__)


class TelegramMedia:
    __slots__ = ("_gw",)

    def __init__(self, gateway: TelegramGateway) -> None:
        self._gw = gateway

    async def transcribe_voice(self, chat_id: int, voice: dict[str, Any]) -> str | None:
        """Fetch voice file → STT adapter → return text. Returns the
        already-formatted prompt chunk on success, or a polite "not
        configured" notice on missing adapter / size cap, or None to
        skip the message entirely.

        Adapter call runs in a thread because the typical STT
        implementation is sync HTTP/IO — keeps aiohttp's event loop
        responsive while a Whisper call burns 1-3 seconds."""
        from veles.modules.stt import STTError, get_stt_adapter

        gw = self._gw
        adapter = get_stt_adapter()
        if adapter is None:
            await gw._send_message(
                chat_id,
                "<i>voice received but no speech-to-text adapter is "
                "configured.</i> Install one via "
                "<code>register_stt_adapter(...)</code> at daemon "
                "startup, or send the message as text.",
            )
            return None

        file_id = voice.get("file_id")
        size = voice.get("file_size") or 0
        mime = voice.get("mime_type") or "audio/ogg"
        if not isinstance(file_id, str):
            return None
        if size and size > _MAX_ATTACHMENT_BYTES:
            await gw._send_message(
                chat_id,
                f"<i>voice file too large ({size // 1024} KB > "
                f"{_MAX_ATTACHMENT_BYTES // 1024} KB cap). Skipped.</i>",
            )
            return None
        try:
            audio_bytes = await gw._download_telegram_file(file_id, size or 0)
        except Exception as exc:
            logger.warning("voice download failed: %s", exc)
            return None
        try:
            text = await asyncio.to_thread(adapter.transcribe, audio_bytes, mime)
        except STTError as exc:
            await gw._send_message(
                chat_id, f"<i>couldn't transcribe voice: {escape_html(str(exc))}</i>"
            )
            return None
        except Exception as exc:
            logger.warning("STT adapter raised %s: %s", type(exc).__name__, exc)
            return None
        return f"[voice transcript] {text.strip()}"

    async def describe_photo(self, chat_id: int, photo: list[dict[str, Any]]) -> str | None:
        """Same shape as `transcribe_voice` but via the Vision
        adapter. `photo` is Telegram's size-variants array; we pick
        the largest so the vision model sees the most detail."""
        from veles.modules.vision import VisionError, get_vision_adapter

        gw = self._gw
        adapter = get_vision_adapter()
        if adapter is None:
            await gw._send_message(
                chat_id,
                "<i>photo received but no vision adapter is "
                "configured.</i> Install one via "
                "<code>register_vision_adapter(...)</code> at daemon "
                "startup, or describe the image in text.",
            )
            return None
        # Telegram delivers photo as variants; the last entry is the
        # largest available size.
        largest = max(
            (p for p in photo if isinstance(p, dict)),
            key=lambda p: int(p.get("file_size") or 0),
            default=None,
        )
        if largest is None:
            return None
        file_id = largest.get("file_id")
        size = int(largest.get("file_size") or 0)
        if not isinstance(file_id, str):
            return None
        if size and size > _MAX_ATTACHMENT_BYTES:
            await gw._send_message(
                chat_id,
                f"<i>photo too large ({size // 1024} KB > "
                f"{_MAX_ATTACHMENT_BYTES // 1024} KB cap). Skipped.</i>",
            )
            return None
        try:
            image_bytes = await gw._download_telegram_file(file_id, size)
        except Exception as exc:
            logger.warning("photo download failed: %s", exc)
            return None
        try:
            description = await asyncio.to_thread(adapter.describe_image, image_bytes, "image/jpeg")
        except VisionError as exc:
            await gw._send_message(
                chat_id, f"<i>couldn't describe photo: {escape_html(str(exc))}</i>"
            )
            return None
        except Exception as exc:
            logger.warning("Vision adapter raised %s: %s", type(exc).__name__, exc)
            return None
        return f"[photo description] {description.strip()}"

    def persist_attachment(self, name: str, data: bytes) -> Path:
        """Write into `<project>/.veles/tmp/<uuid8>-<safe_name>`. The
        UUID prefix guarantees no collision even if the user sends two
        files with the same name in one session."""
        gw = self._gw
        assert gw.attachment_dir is not None
        gw.attachment_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{uuid.uuid4().hex[:8]}-{_safe_filename(name)}"
        target = gw.attachment_dir / fname
        target.write_bytes(data)
        return target

    async def save_telegram_document(self, chat_id: int, document: dict[str, Any]) -> Path | None:
        """Validate → ack → download → persist for one document. Returns
        the saved Path on success, None on reject/error (the user has
        already been told what happened via send/edit messages)."""
        gw = self._gw
        name = str(document.get("file_name") or "file")
        mime = str(document.get("mime_type") or "")
        size = int(document.get("file_size") or 0)
        file_id = document.get("file_id")
        if not isinstance(file_id, str):
            return None
        reason = _reject_reason(name, mime, size)
        if reason is not None:
            await gw._send_message(chat_id, reason)
            return None
        if gw.attachment_dir is None:
            await gw._send_message(chat_id, "📎 Attachments are not configured.")
            return None
        ack = await gw._send_message(chat_id, f"📎 Saving <code>{escape_html(name)}</code>…")
        ack_id = ack.get("message_id") if isinstance(ack, dict) else None
        try:
            data = await gw._download_telegram_file(file_id, size)
        except Exception as exc:
            logger.warning("telegram document download failed: %s", exc)
            if isinstance(ack_id, int):
                await gw._edit_message(
                    chat_id,
                    ack_id,
                    f"📎 <b>Download failed:</b> {escape_html(str(exc))}",
                )
            return None
        saved = gw._persist_attachment(name, data)
        if isinstance(ack_id, int):
            await gw._edit_message(
                chat_id,
                ack_id,
                f"📎 Saved <code>{escape_html(name)}</code> · asking agent…",
            )
        return saved
