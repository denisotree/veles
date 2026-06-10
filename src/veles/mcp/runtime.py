"""Process-global MCP manager lifecycle + agent-registry mounting (M157).

The agent loop builds its tool Registry in `cli/_runtime._load_skills`;
`mount_mcp_tools` is the single hook it calls. Design:

  - Lazy: the manager (and the `mcp` SDK) is only created when the
    project actually declares `[mcp.servers.*]`.
  - One manager per process, shared across agent constructions, so a
    long-lived TUI/daemon doesn't respawn stdio subprocesses per turn —
    `connect_all` skips servers that are already connected.
  - Closed at process exit via `atexit`; `shutdown_mcp()` is the manual
    hook (tests use it to avoid leaking the loop thread between cases).
"""

from __future__ import annotations

import atexit
import logging
import threading

from veles.core.project import Project
from veles.core.tools.registry import Registry

logger = logging.getLogger(__name__)

_manager = None
_manager_lock = threading.Lock()


def get_manager():
    """Return the process-global `McpClientManager`, creating it lazily."""
    global _manager
    with _manager_lock:
        if _manager is None:
            from veles.mcp.client import McpClientManager

            _manager = McpClientManager()
            atexit.register(shutdown_mcp)
        return _manager


def shutdown_mcp() -> None:
    """Close the process-global manager (idempotent; safe with no manager)."""
    global _manager
    with _manager_lock:
        manager, _manager = _manager, None
    if manager is not None:
        try:
            manager.close()
        except Exception as exc:
            logger.warning("MCP manager close failed: %s", exc)


def mount_mcp_tools(registry: Registry, project: Project) -> list[str]:
    """Connect configured MCP servers and register their tools.

    Returns the registered tool names (``mcp_<server>_<tool>``), or `[]`
    when the project declares no `[mcp.servers.*]`. Never raises — MCP
    problems are logged warnings, not startup failures."""
    from veles.mcp.config import load_disabled_tools, load_mcp_config

    configs = load_mcp_config(project)
    if not any(cfg.enabled for cfg in configs.values()):
        return []
    try:
        manager = get_manager()
        manager.connect_all(configs)
        from veles.mcp.registry_adapter import register_mcp_tools

        return register_mcp_tools(
            registry,
            manager,
            configs,
            disabled_tools=load_disabled_tools(project),
        )
    except Exception as exc:
        logger.warning("MCP tools unavailable: %s", exc)
        return []


__all__ = ["get_manager", "mount_mcp_tools", "shutdown_mcp"]
