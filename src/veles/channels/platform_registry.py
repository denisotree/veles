"""Platform registry (M74) — lookup of channel gateway factories by name.

A channel module registers its gateway factory at import time:

    from veles.channels.platform_registry import register_platform
    register_platform("telegram", TelegramGateway, validate=_validate_telegram_config)

Consumers (`veles channel run`, `DeliveryRouter`, `/v1/channels`) resolve the
adapter via `get_platform(name)`. No global side-effects beyond a process-local
dict; the registry is mutated only at import time.

Why a registry instead of hardcoded dispatch: hardcoding platforms in a single
config module is fine until you want a third-party Slack adapter.
The registry is intentionally tiny (≤120 LOC) — it owns name→factory mapping,
nothing else. No plugin discovery (deferred); to wire a new platform, import
its module so its `register_platform` call runs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


# Channel gateway factory: any callable (function or class) producing a
# gateway with `start()` / `stop()`. Kept as `Any` instead of a strict
# Protocol because dataclass `__init__` signatures don't match a `**kwargs`
# Protocol — Pyright rejects passing a frozen-dataclass class as the
# factory under that protocol.
ChannelGatewayFactory = Any


@dataclass(slots=True, frozen=True)
class CredField:
    """One field the add-channel wizard (M137) collects for a platform.

    `secret=True` → stored in the keychain via `set_provider_key(platform, …)`
    (e.g. a bot token); otherwise written to the channel's config block.
    `list_value=True` → the prompt's comma-separated answer is split into a
    list (e.g. a whitelist of chat IDs)."""

    key: str
    label: str
    secret: bool = False
    list_value: bool = False
    required: bool = False


@dataclass(slots=True, frozen=True)
class PlatformEntry:
    """One registered platform: name + factory + optional config validator."""

    name: str
    factory: ChannelGatewayFactory
    validate_config: Callable[[dict[str, Any]], list[str]] | None = None
    """Returns a list of error strings; empty list = config OK."""
    cred_fields: tuple[CredField, ...] = ()
    """Fields the add-channel wizard collects (M137); empty = no wizard creds."""


_REGISTRY: dict[str, PlatformEntry] = {}


def register_platform(
    name: str,
    factory: ChannelGatewayFactory,
    *,
    validate: Callable[[dict[str, Any]], list[str]] | None = None,
    cred_fields: tuple[CredField, ...] = (),
    overwrite: bool = False,
) -> PlatformEntry:
    """Register a channel gateway factory under `name`.

    Raises ValueError if a different factory is already registered for `name`
    unless `overwrite=True`. Re-registering the same factory is a no-op
    (idempotent on repeated module imports). `cred_fields` drives the M137
    add-channel wizard.
    """
    if not name or not name.strip():
        raise ValueError("platform name must be a non-empty string")
    existing = _REGISTRY.get(name)
    if existing is not None and not overwrite and existing.factory is not factory:
        raise ValueError(
            f"platform {name!r} already registered with a different factory; "
            "pass overwrite=True to replace"
        )
    entry = PlatformEntry(
        name=name, factory=factory, validate_config=validate, cred_fields=cred_fields
    )
    _REGISTRY[name] = entry
    return entry


def unregister_platform(name: str) -> bool:
    """Remove a registration (mostly for tests). Returns True if found."""
    return _REGISTRY.pop(name, None) is not None


def get_platform(name: str) -> PlatformEntry:
    """Look up a registered platform; raise KeyError with a helpful message."""
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"no channel platform registered for {name!r}; available: {available}")
    return _REGISTRY[name]


def list_platforms() -> list[str]:
    """Return registered platform names, sorted."""
    return sorted(_REGISTRY)


def _reset_registry_for_tests() -> None:
    """Test-only escape hatch: wipe the registry. Production code never calls."""
    _REGISTRY.clear()


def _register_builtins() -> None:
    """Register platforms that ship inside Veles. Importing telegram has a
    side effect (its own `register_platform` call) for compatibility with
    callers that import the module directly, but we also register
    explicitly here so a previously-imported module re-registers cleanly
    after `_reset_registry_for_tests()`.
    """
    from veles.channels.telegram import TELEGRAM_CRED_FIELDS, TelegramGateway

    register_platform(
        "telegram", TelegramGateway, cred_fields=TELEGRAM_CRED_FIELDS, overwrite=True
    )


def ensure_builtins_registered() -> None:
    """Idempotent: register built-in platforms if not yet present."""
    if "telegram" not in _REGISTRY:
        _register_builtins()


__all__ = [
    "ChannelGatewayFactory",
    "CredField",
    "PlatformEntry",
    "ensure_builtins_registered",
    "get_platform",
    "list_platforms",
    "register_platform",
    "unregister_platform",
]
