"""Telegram channel package — gateway + helpers split across submodules.

Public surface stays the same as the legacy single-file `telegram.py`:
the gateway is reachable as `from veles.channels.telegram import
TelegramGateway`, and the private helpers/dataclasses tests rely on
are re-exported too (single-source-of-truth lives in the submodules)."""

from __future__ import annotations

from veles.channels.platform_registry import CredField, register_platform
from veles.channels.telegram._attachments import (
    _MAX_ATTACHMENT_BYTES,
    _SAFE_FILENAME_RE,
    _TEXTUAL_EXTENSIONS,
    _TEXTUAL_MIME_LITERALS,
    _TEXTUAL_MIME_PREFIXES,
    _is_textual,
    _reject_reason,
    _safe_filename,
)
from veles.channels.telegram._buffer import (
    _BUFFER_HARD_CAP,
    _DEBOUNCE_SECONDS,
    _ChatBuffer,
    _classify,
    _Kind,
)
from veles.channels.telegram._delivery import _TurnOutcome
from veles.channels.telegram._forwarded import (
    _FORWARD_KEYS,
    _forward_source,
    _has_forward,
    _render_forwarded,
)
from veles.channels.telegram._gateway import (
    TelegramGateway,
    logger,
)
from veles.channels.telegram._helpers import (
    _LONG_POLL_TIMEOUT,
    _PLACEHOLDER_TEXT,
    _TELEGRAM_API,
    _TELEGRAM_TIER,
    _build_combined_prompt,
    _html_to_plain,
    _is_parse_error,
    _truncate,
)
from veles.channels.telegram._prompts import (
    _APPROVAL_SHORT_BY_KEY,
    _TRUST_SHORT_BY_KEY,
    _build_buttons,
    _format_prompt_body,
    _PendingTelegramPrompt,
    _render_prompt_args,
)

__all__ = [
    # private names intentionally re-exported — existing tests import them
    "_APPROVAL_SHORT_BY_KEY",
    "_BUFFER_HARD_CAP",
    "_DEBOUNCE_SECONDS",
    "_FORWARD_KEYS",
    "_LONG_POLL_TIMEOUT",
    "_MAX_ATTACHMENT_BYTES",
    "_PLACEHOLDER_TEXT",
    "_SAFE_FILENAME_RE",
    "_TELEGRAM_API",
    "_TELEGRAM_TIER",
    "_TEXTUAL_EXTENSIONS",
    "_TEXTUAL_MIME_LITERALS",
    "_TEXTUAL_MIME_PREFIXES",
    "_TRUST_SHORT_BY_KEY",
    "TelegramGateway",
    "_ChatBuffer",
    "_Kind",
    "_PendingTelegramPrompt",
    "_TurnOutcome",
    "_build_buttons",
    "_build_combined_prompt",
    "_classify",
    "_format_prompt_body",
    "_forward_source",
    "_has_forward",
    "_html_to_plain",
    "_is_parse_error",
    "_is_textual",
    "_reject_reason",
    "_render_forwarded",
    "_render_prompt_args",
    "_safe_filename",
    "_truncate",
    "logger",
]

TELEGRAM_CRED_FIELDS = (
    CredField("bot_token", "Telegram bot token (from @BotFather)", secret=True, required=True),
    CredField(
        "whitelist",
        "Allowed chat IDs, comma-separated (blank = allow all)",
        list_value=True,
    ),
)

register_platform("telegram", TelegramGateway, cred_fields=TELEGRAM_CRED_FIELDS)
