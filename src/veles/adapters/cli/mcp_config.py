"""The MCP config a CLI delegate reads to reach Veles' tools.

Written atomically into the process's delegate directory
(`core/delegate_dir.py`), never into the shared `.veles/`. A module delegate
(antigravity) builds its own config file around `veles_mcp_server`."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from veles.core.delegate_dir import delegate_budget_file, delegate_dir
from veles.core.io_utils import atomic_write_text
from veles.core.project import Project


def veles_mcp_server(project: Project) -> dict[str, Any]:
    """The stdio server entry: Veles' MCP server for `project`, charging the
    process's delegate budget."""
    return {
        "command": sys.executable,
        "args": [
            "-m",
            "veles.adapters.cli.mcp_server",
            "--project-root",
            str(project.root),
            "--budget-file",
            str(delegate_budget_file(project)),
        ],
    }


def build_mcp_config(project: Project) -> Path:
    """`<delegate dir>/mcp.json` for claude `--mcp-config`."""
    path = delegate_dir(project) / "mcp.json"
    config = {"mcpServers": {"veles": veles_mcp_server(project)}}
    atomic_write_text(path, json.dumps(config, indent=2) + "\n")
    return path
