"""M201 — validation for security-relevant `config.toml` sections.

`config.toml` is free-form TOML read through `get_section` (no schema), so a
mistyped key is silently ignored. In a *security* section that's dangerous: a
`[channels.telegram] whitlist = […]` typo leaves `whitelist` unset, and an empty
whitelist means "allow every chat". This module declares the known keys for the
sections that gate access and reports unknown ones so `veles doctor` (and the
channel-run path) can fail loud instead of failing open.

Scope was originally the access-gating sections — channels, daemon sessions,
and MCP servers — on the argument that a typo elsewhere is "a functional bug,
not a silent security hole".

**M255 extends that to `[engine]`**, because M250 put a *reproducibility* knob
there and the argument inverts: a mistyped `[engine.request.openrotuer]` is
dropped silently, the run proceeds unpinned, and the measurement it was meant to
stabilise is quietly invalid — the failure the knob exists to prevent. Config is
written by hand, so it is wrong sometimes; an explicit error beats an implicit
fallback.

Validation stops at the provider-name level. What a provider's own subsection
contains is a verbatim passthrough that Veles deliberately does not model (see
`openai_wire.request_body_overrides`), and the upstream rejects its own typos
anyway — OpenRouter answers `400 provider: Unrecognized key: "quantization"`
(verified 2026-09-18).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
# Keys valid under `[engine]` (M255). Verified against every consumer:
# `model_resolver.resolve_effective_provider/model`, `routing/ensemble.py`, and
# `tui_state.persist_model_choice` read `provider`/`model` and nothing else;
# `request` is the M250 passthrough table.
_ENGINE_KNOWN = frozenset({"provider", "model", "request"})


class ConfigError(ValueError):
    """A config mistake that would otherwise be absorbed silently.

    Mirrors `LayoutManifestError`: carries the file path, because the only
    useful thing to say about a bad config value is which file to edit."""

    def __init__(self, message: str, *, path: Path) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


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


def validate_engine(cfg: dict[str, Any]) -> list[ConfigFinding]:
    """Unknown keys in `[engine]` and `[engine.request]` — the two typo shapes
    that both end in an unpinned run, reported together so one raise covers both.

        [engine.request.openrotuer.provider]   # wrong provider: section exists,
                                               # name matches no Provider.name
        [engine.reqest.openrouter.provider]    # wrong path: `[engine.request]`
                                               # is then simply absent

    The second is invisible to the reader — "no `[engine.request]`" is also the
    normal state of every project without a pin — so it can only be caught here,
    one level up, as an unknown key under `[engine]`."""
    from veles.core.providers import PROVIDER_VALUES

    findings = _check("engine", get_section(cfg, "engine"), _ENGINE_KNOWN)
    findings += [
        ConfigFinding(section="engine.request", key=key, known=PROVIDER_VALUES)
        for key in sorted(get_section(cfg, "engine", "request"))
        if key not in PROVIDER_VALUES
    ]
    return findings


def validate_config(cfg: dict[str, Any]) -> list[ConfigFinding]:
    """Return unknown-key findings across the validated config sections.
    Empty list means every key in those sections is recognised."""
    findings: list[ConfigFinding] = []

    findings += validate_engine(cfg)
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
