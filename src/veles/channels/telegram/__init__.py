"""Telegram channel package — the gateway plus its helpers, split across
private submodules. Only `TelegramGateway` is public; importing the package
registers the `telegram` platform."""

from __future__ import annotations

from veles.channels.platform_registry import CredField, register_platform
from veles.channels.telegram._gateway import TelegramGateway

__all__ = ["TELEGRAM_CRED_FIELDS", "TelegramGateway"]

TELEGRAM_CRED_FIELDS = (
    CredField("bot_token", "Telegram bot token (from @BotFather)", secret=True, required=True),
    CredField(
        "whitelist",
        "Allowed chat IDs, comma-separated (blank = allow all)",
        list_value=True,
    ),
)

register_platform("telegram", TelegramGateway, cred_fields=TELEGRAM_CRED_FIELDS)
