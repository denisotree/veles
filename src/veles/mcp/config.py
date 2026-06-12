"""`[mcp.servers.*]` config parsing for the MCP client (M157).

Schema (in `<project>/.veles/config.toml`):

    [mcp.servers.github]
    transport = "stdio"          # "stdio" (default) | "http" | "sse"
    command   = "npx"            # required for stdio
    args      = ["-y", "@modelcontextprotocol/server-github"]
    env       = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
    timeout_s = 120              # per-tool-call budget (default 120)
    connect_timeout_s = 30       # per-server connect budget (default 30)
    enabled   = true             # default true

    [mcp.servers.docs]
    transport = "http"           # streamable HTTP
    url       = "http://localhost:8000/mcp"

    [mcp]
    disabled_tools = { github = ["delete_repository"] }

String values (`command`, `args` items, `env` values, `url`) support
`${VAR}` interpolation from `os.environ`; an unset variable resolves to
the empty string with a warning. Invalid entries (unknown transport,
stdio without command, http/sse without url, malformed names) are
logged as warnings and skipped — MCP config errors never break startup.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from veles.core.project import Project
from veles.core.project_config import get_section, load_project_config

logger = logging.getLogger(__name__)

VALID_TRANSPORTS = frozenset({"stdio", "http", "sse"})

DEFAULT_TIMEOUT_S = 120.0
DEFAULT_CONNECT_TIMEOUT_S = 30.0

# Server names become part of registry tool names (`mcp_<server>_<tool>`),
# so they must stay identifier-shaped.
_SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(slots=True)
class McpServerConfig:
    """One `[mcp.servers.<name>]` entry, validated and env-interpolated."""

    name: str
    transport: str = "stdio"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    timeout_s: float = DEFAULT_TIMEOUT_S
    connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S
    enabled: bool = True


def interpolate_env(value: str) -> str:
    """Expand `${VAR}` references from `os.environ`.

    An unset variable expands to the empty string — with a warning, so a
    missing token doesn't silently produce a server that auth-fails."""

    def _sub(match: re.Match[str]) -> str:
        var = match.group(1)
        resolved = os.environ.get(var)
        if resolved is None:
            logger.warning(
                "MCP config: environment variable %r is not set; using empty string", var
            )
            return ""
        return resolved

    return _ENV_VAR_RE.sub(_sub, value)


def _coerce_float(raw: Any, default: float, *, server: str, key: str) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning("MCP server %r: ignoring non-numeric %s=%r", server, key, raw)
        return default
    if value <= 0:
        logger.warning("MCP server %r: ignoring non-positive %s=%r", server, key, raw)
        return default
    return value


def _parse_server(name: str, raw: dict[str, Any]) -> McpServerConfig | None:
    """Validate one `[mcp.servers.<name>]` table. None means skip (warned)."""
    transport = raw.get("transport", "stdio")
    if transport not in VALID_TRANSPORTS:
        logger.warning(
            "MCP server %r: unknown transport %r (expected one of %s); skipping",
            name,
            transport,
            ", ".join(sorted(VALID_TRANSPORTS)),
        )
        return None

    command_raw = raw.get("command")
    command = interpolate_env(command_raw) if isinstance(command_raw, str) else None
    url_raw = raw.get("url")
    url = interpolate_env(url_raw) if isinstance(url_raw, str) else None

    if transport == "stdio" and not command:
        logger.warning("MCP server %r: stdio transport requires `command`; skipping", name)
        return None
    if transport in {"http", "sse"} and not url:
        logger.warning("MCP server %r: %s transport requires `url`; skipping", name, transport)
        return None

    args_raw = raw.get("args", [])
    args: list[str] = []
    if isinstance(args_raw, list):
        for item in args_raw:
            if isinstance(item, str):
                args.append(interpolate_env(item))
            else:
                args.append(str(item))
    elif args_raw:
        logger.warning("MCP server %r: `args` must be a list; ignoring %r", name, args_raw)

    env_raw = raw.get("env", {})
    env: dict[str, str] = {}
    if isinstance(env_raw, dict):
        for key, value in env_raw.items():
            env[str(key)] = interpolate_env(value) if isinstance(value, str) else str(value)
    elif env_raw:
        logger.warning("MCP server %r: `env` must be a table; ignoring %r", name, env_raw)

    return McpServerConfig(
        name=name,
        transport=transport,
        command=command,
        args=args,
        env=env,
        url=url,
        timeout_s=_coerce_float(
            raw.get("timeout_s"), DEFAULT_TIMEOUT_S, server=name, key="timeout_s"
        ),
        connect_timeout_s=_coerce_float(
            raw.get("connect_timeout_s"),
            DEFAULT_CONNECT_TIMEOUT_S,
            server=name,
            key="connect_timeout_s",
        ),
        enabled=bool(raw.get("enabled", True)),
    )


def load_mcp_config(project: Project) -> dict[str, McpServerConfig]:
    """Parse `[mcp.servers.*]` from the project config.

    Returns `{}` when the section is absent. Disabled servers are kept in
    the result (with `enabled=False`) so `veles mcp list` can show them;
    the connect path skips them."""
    servers = get_section(load_project_config(project), "mcp", "servers")
    out: dict[str, McpServerConfig] = {}
    for name, raw in servers.items():
        if not isinstance(raw, dict):
            logger.warning("MCP server %r: entry is not a table; skipping", name)
            continue
        if not _SERVER_NAME_RE.match(name):
            logger.warning(
                "MCP server %r: name must match %s; skipping",
                name,
                _SERVER_NAME_RE.pattern,
            )
            continue
        cfg = _parse_server(name, raw)
        if cfg is not None:
            out[name] = cfg
    return out


def load_disabled_tools(project: Project) -> dict[str, list[str]]:
    """Parse `[mcp] disabled_tools` — server name → tool names to skip."""
    section = get_section(load_project_config(project), "mcp")
    raw = section.get("disabled_tools")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for server, tools in raw.items():
        if isinstance(tools, list):
            out[str(server)] = [str(t) for t in tools]
        else:
            logger.warning("MCP disabled_tools for %r must be a list; ignoring %r", server, tools)
    return out


__all__ = [
    "DEFAULT_CONNECT_TIMEOUT_S",
    "DEFAULT_TIMEOUT_S",
    "VALID_TRANSPORTS",
    "McpServerConfig",
    "interpolate_env",
    "load_disabled_tools",
    "load_mcp_config",
]
