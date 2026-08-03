"""Per-chat message buffer + kind classification for the Telegram channel.

Forwarded posts and documents typically arrive a half-second before the
user's comment that references them. Flushing each update immediately
splits the intent across two LLM turns; debouncing merges them."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from veles.channels.telegram._forwarded import _has_forward

# Debounce window. 1.5s covered only near-simultaneous updates (a forward
# burst); a human who types a comment, switches chats and forwards a post
# needs a few seconds more, so the default is 3s. Override per install with
# `[channels.telegram] debounce_seconds` in `.veles/config.toml`.
_DEBOUNCE_SECONDS = 3.0
_BUFFER_HARD_CAP = 5


@dataclass(slots=True)
class _ChatBuffer:
    """Per-chat aggregation buffer. Forwarded posts and documents
    typically arrive a half-second before the user's comment that
    references them — flushing each update immediately splits the
    intent across two LLM turns. We debounce by `_DEBOUNCE_SECONDS`,
    flushing earlier if the buffer reaches `_BUFFER_HARD_CAP`."""

    chat_id: int
    chat_key: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    timer: asyncio.TimerHandle | None = None

    def cancel_timer(self) -> None:
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None


class _Kind(Enum):
    TEXT = "text"
    DOCUMENT = "document"
    FORWARD = "forward"
    VOICE = "voice"  # M-multimodal: STT adapter required
    PHOTO = "photo"  # M-multimodal: Vision adapter required
    IGNORED = "ignored"


def _classify(message: dict[str, Any]) -> _Kind:
    """Decide what flavour of update this is. Priority order:
    document > voice/photo (multimodal) > forward > text.
    Voice/photo are recognised here; the actual transcription /
    description happens later in `TelegramMedia` — voice needs an STT
    adapter (no adapter → a polite "not configured" notice), photo
    falls back to saving the file and letting the agent call
    `image_describe`."""
    if isinstance(message.get("document"), dict):
        return _Kind.DOCUMENT
    if isinstance(message.get("voice"), dict) or isinstance(message.get("audio"), dict):
        return _Kind.VOICE
    if isinstance(message.get("photo"), list) and message.get("photo"):
        return _Kind.PHOTO
    if _has_forward(message):
        return _Kind.FORWARD
    if (message.get("text") or "").strip():
        return _Kind.TEXT
    return _Kind.IGNORED
