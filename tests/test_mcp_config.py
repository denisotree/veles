"""Unit tests for build_mcp_config (its location: tests/test_delegate_dir.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from veles.adapters.cli.mcp_config import build_mcp_config
from veles.core.project import init_project


def test_build_mcp_config_uses_sys_executable(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    path = build_mcp_config(project)
    config = json.loads(path.read_text(encoding="utf-8"))
    cmd = config["mcpServers"]["veles"]["command"]
    assert cmd == sys.executable


def test_build_mcp_config_passes_project_root_in_args(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    path = build_mcp_config(project)
    config = json.loads(path.read_text(encoding="utf-8"))
    args = config["mcpServers"]["veles"]["args"]
    assert "-m" in args
    assert "veles.adapters.cli.mcp_server" in args
    assert "--project-root" in args
    pr_idx = args.index("--project-root")
    assert args[pr_idx + 1] == str(tmp_path.resolve())
