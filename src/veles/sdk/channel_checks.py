"""Checks a channel module's own tests call against its platform spec.

Plain functions that raise `AssertionError` — no pytest here: `veles.sdk` is
imported by a running Veles, where pytest isn't installed."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from veles.core.chat_sessions import SessionMap
from veles.core.platforms import ChannelContext, ChannelGateway, PlatformSpec

PROBE_TEXT = "veles channel check"


class _NoBackend:
    """Building a gateway must not talk to the daemon yet."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"building a gateway must not call the backend ({name})")


def check_builds_from_config(
    spec: PlatformSpec,
    *,
    config: Mapping[str, Any],
    secrets: Mapping[str, str],
    session_dir: Path,
    name: str = "check",
) -> ChannelGateway:
    """The spec builds a gateway from a channel block and its secrets, without
    the daemon; the gateway has start/stop/deliver. `session_dir`: the caller's
    own temp dir (its pytest `tmp_path`)."""
    ctx = ChannelContext(
        name=name,
        config=config,
        secrets=secrets,
        backend=_NoBackend(),  # type: ignore[arg-type]
        session_map=SessionMap.load(session_dir / "sessions.json"),
        project=None,
    )
    gateway = spec.build(ctx)
    for method in ("start", "stop", "deliver"):
        assert callable(getattr(gateway, method, None)), f"the gateway has no {method}()"
    return gateway


def check_config_keys(spec: PlatformSpec, config: Mapping[str, Any]) -> None:
    """Every key in a channel block is one the platform declares (its cred
    fields or `config_keys`) — else `veles daemon start` reports it as a typo."""
    from veles.core.config_schema import platform_keys

    unknown = sorted(set(config) - platform_keys(spec))
    assert not unknown, f"config keys the platform does not declare: {unknown}"


async def check_delivers(gateway: ChannelGateway, chat_id: str) -> None:
    """`deliver` takes a chat id and a text and returns without error."""
    await gateway.deliver(chat_id, PROBE_TEXT)


__all__ = ["PROBE_TEXT", "check_builds_from_config", "check_config_keys", "check_delivers"]
