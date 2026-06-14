"""Provision MCP-driven project tools (M165b).

Some external MCP servers have an out-of-band build step the agent should be
able to drive — e.g. graphify's `graphify-mcp` only *reads* `graph.json`, so
rebuilding it is a separate `graphify .` invocation. When a project declares
such a server, we copy a matching helper tool template into
`<project>/.veles/tools/`, where the M120 file-based tool loader picks it up.

Idempotent: an existing tool file is never overwritten (so user edits survive).
Never raises — provisioning problems are logged warnings, not startup failures.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from veles.core.project import Project

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# `[mcp.servers.<name>]` server name -> tool template filename under templates/.
_MCP_TOOL_TEMPLATES: dict[str, str] = {
    "graphify": "graphify_rebuild.py",
}


def ensure_mcp_project_tools(project: Project) -> list[str]:
    """Copy tool templates for the project's configured MCP servers into
    `<project>/.veles/tools/`. Returns the filenames newly provisioned this
    call (empty when nothing was configured or everything already existed)."""
    try:
        from veles.mcp.config import load_mcp_config

        configs = load_mcp_config(project)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("MCP tool provisioning skipped: %s", exc)
        return []
    if not configs:
        return []

    tools_dir = project.state_dir / "tools"
    provisioned: list[str] = []
    for server, template_name in _MCP_TOOL_TEMPLATES.items():
        if server not in configs:
            continue
        src = _TEMPLATES_DIR / template_name
        dst = tools_dir / template_name
        if dst.exists() or not src.is_file():
            continue
        try:
            tools_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            provisioned.append(template_name)
            logger.info("provisioned MCP tool %s -> %s", template_name, dst)
        except OSError as exc:
            logger.warning("failed to provision MCP tool %s: %s", template_name, exc)
    return provisioned


__all__ = ["ensure_mcp_project_tools"]
