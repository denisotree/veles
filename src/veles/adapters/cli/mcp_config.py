"""Generate the MCP config a CLI delegate reads to bridge Veles tools.

`build_mcp_config(project)` → `<project>/.veles/mcp.json` (claude consumes it
via `--mcp-config`). It describes an MCP server descriptor: a child Python
process running `veles.adapters.cli.mcp_server`. The descriptor is regenerated
on every tool-using command so `sys.executable` always reflects the active venv.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from veles.core.project import Project

_VELES_CONFIG_FILENAME = "mcp.json"


DEFAULT_SKILL_MODEL = "anthropic/claude-sonnet-4.6"


def _mcp_server_descriptor(project: Project, *, skill_model: str) -> dict[str, Any]:
    return {
        "command": sys.executable,
        "args": [
            "-m",
            "veles.adapters.cli.mcp_server",
            "--project-root",
            str(project.root),
            "--skill-model",
            skill_model,
            "--budget-file",
            str(project.state_dir / "budget.state.json"),
        ],
    }


def build_mcp_config(project: Project, *, skill_model: str = DEFAULT_SKILL_MODEL) -> Path:
    """Write `<project>/.veles/mcp.json` for claude `--mcp-config`."""
    config = {"mcpServers": {"veles": _mcp_server_descriptor(project, skill_model=skill_model)}}
    project.state_dir.mkdir(parents=True, exist_ok=True)
    path = project.state_dir / _VELES_CONFIG_FILENAME
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path
