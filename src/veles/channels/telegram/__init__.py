"""Telegram channel — the gateway plus its helpers, split across private
submodules; `register(api)` contributes the `telegram` platform."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from veles.sdk.channels import ChannelCaps, ChannelContext, CredField, PlatformSpec

from ._gateway import TelegramGateway

logger = logging.getLogger(__name__)

TELEGRAM_CRED_FIELDS = (
    CredField(
        "bot_token",
        "Telegram bot token (from @BotFather)",
        secret=True,
        required=True,
        env="TELEGRAM_BOT_TOKEN",
    ),
    CredField(
        "whitelist",
        "Allowed chat IDs, comma-separated (blank = allow all)",
        list_value=True,
    ),
)


def _float_setting(cfg: Mapping[str, Any], key: str) -> float | None:
    """An optional numeric setting. A typo warns and falls back to the code
    default rather than failing the channel."""
    raw = cfg.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning("[channels.telegram] %s=%r is not a number — using the default", key, raw)
        return None


def _build(ctx: ChannelContext) -> TelegramGateway:
    raw = ctx.config.get("whitelist") or []
    if isinstance(raw, str):
        raw = [raw]
    whitelist = tuple(str(x) for x in raw if str(x).strip())
    # The old stdin wizard wrote a single allowed peer as `chat_id`; honour it.
    legacy_chat_id = ctx.config.get("chat_id")
    if legacy_chat_id and not whitelist:
        whitelist = (str(legacy_chat_id),)
    gateway = TelegramGateway(
        bot_token=ctx.secrets["bot_token"],
        daemon_client=ctx.backend,
        session_map=ctx.session_map,
        whitelist=whitelist,
        attachment_dir=ctx.project.tmp_dir if ctx.project is not None else None,
        project_root=ctx.project.root if ctx.project is not None else None,
        debounce_seconds=_float_setting(ctx.config, "debounce_seconds"),
        forward_debounce_seconds=_float_setting(ctx.config, "forward_debounce_seconds"),
    )
    logger.info("telegram channel built (whitelist: %d entries)", len(whitelist))
    return gateway


TELEGRAM_SPEC = PlatformSpec(
    build=_build,
    caps=ChannelCaps(asks_questions=True),
    cred_fields=TELEGRAM_CRED_FIELDS,
    config_keys=frozenset({"chat_id", "debounce_seconds", "forward_debounce_seconds"}),
)


def register(api) -> None:
    api.contribute("platform", "telegram", TELEGRAM_SPEC)


__all__ = ["TELEGRAM_CRED_FIELDS", "TELEGRAM_SPEC", "TelegramGateway", "register"]
