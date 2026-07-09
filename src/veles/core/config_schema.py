"""M201 — validation for security-relevant `config.toml` sections.

`config.toml` is free-form TOML read through `get_section` (no schema), so a
mistyped key is silently ignored. In a *security* section that's dangerous: a
`[channels.telegram] whitlist = […]` typo leaves `whitelist` unset, and an empty
whitelist means "allow every chat". This module declares the known keys for the
sections that gate access and reports unknown ones so `veles doctor` (and the
channel-run path) can fail loud instead of failing open.

Scope is deliberately the access-gating sections — channels, daemon sessions,
and MCP servers. Content sections (`[engine]`, `[routing]`, wiki, …) are left
free-form; a typo there is a functional bug, not a silent security hole.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from veles.core.project_config import get_section

# Keys valid under `[daemon]` (flat legacy scalars) and `[daemon.<name>]`.
_DAEMON_KNOWN = frozenset(
    {"enabled", "host", "port", "autostart", "provider", "model", "mode", "channels"}
)
# Keys valid under `[mcp.servers.<name>]` — mirrors `McpServerConfig` fields.
_MCP_SERVER_KNOWN = frozenset(
    {"transport", "command", "args", "env", "url", "timeout_s", "connect_timeout_s", "enabled"}
)
# Channel keys common to every platform; per-platform cred fields are added on
# top (from the platform registry), so new platforms need no change here.
_CHANNEL_BASE_KEYS = frozenset({"enabled", "chat_id"})


@dataclass(slots=True, frozen=True)
class ConfigFinding:
    """One unknown key in a security-relevant config section."""

    section: str
    key: str
    known: tuple[str, ...]


def _channel_known_keys(platform: str) -> frozenset[str]:
    from veles.channels.platform_registry import ensure_builtins_registered, get_platform

    try:
        # `daemon start` validates the config before anything imports a channel
        # module — bootstrap the builtin registry here, or `get_platform` raises
        # on an empty registry and the validator degrades to base keys, falsely
        # flagging legitimate per-platform keys like `whitelist` (live 2026-07-09).
        ensure_builtins_registered()
        entry = get_platform(platform)
    except Exception:
        # Unknown platform (possibly itself a typo) — validate only base keys
        # rather than crash; the missing gateway surfaces elsewhere.
        return _CHANNEL_BASE_KEYS
    return _CHANNEL_BASE_KEYS | {f.key for f in entry.cred_fields}


def _check(section: str, cfg: dict[str, Any], known: frozenset[str]) -> list[ConfigFinding]:
    return [
        ConfigFinding(section=section, key=key, known=tuple(sorted(known)))
        for key in cfg
        if key not in known
    ]


def _check_channels(prefix: str, channels: dict[str, Any]) -> list[ConfigFinding]:
    out: list[ConfigFinding] = []
    for platform, pcfg in channels.items():
        if isinstance(pcfg, dict):
            out += _check(f"{prefix}{platform}", pcfg, _channel_known_keys(platform))
    return out


def validate_config(cfg: dict[str, Any]) -> list[ConfigFinding]:
    """Return unknown-key findings across the access-gating config sections.
    Empty list means every key in those sections is recognised."""
    findings: list[ConfigFinding] = []

    findings += _check_channels("channels.", get_section(cfg, "channels"))

    daemon = get_section(cfg, "daemon")
    for name, value in daemon.items():
        if isinstance(value, dict):
            # A named `[daemon.<name>]` session (its own scalar keys + channels).
            findings += _check(f"daemon.{name}", value, _DAEMON_KNOWN)
            sub = value.get("channels")
            if isinstance(sub, dict):
                findings += _check_channels(f"daemon.{name}.channels.", sub)
        elif name not in _DAEMON_KNOWN:
            # A flat scalar directly under `[daemon]` that isn't a legacy key.
            findings.append(
                ConfigFinding(section="daemon", key=name, known=tuple(sorted(_DAEMON_KNOWN)))
            )

    for name, scfg in get_section(cfg, "mcp", "servers").items():
        if isinstance(scfg, dict):
            findings += _check(f"mcp.servers.{name}", scfg, _MCP_SERVER_KNOWN)

    return findings
