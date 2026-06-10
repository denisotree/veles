"""Unit tests for build_mcp_config."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from veles.adapters.cli.mcp_config import build_mcp_config
from veles.core.project import init_project


def test_build_mcp_config_writes_file_at_state_dir(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    path = build_mcp_config(project)
    assert path == tmp_path / ".veles" / "mcp.json"
    assert path.is_file()


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


def test_build_mcp_config_overwrites_existing(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    first = build_mcp_config(project)
    first.write_text("stale", encoding="utf-8")
    second = build_mcp_config(project)
    body = second.read_text(encoding="utf-8")
    assert "stale" not in body
    assert json.loads(body)["mcpServers"]["veles"]["command"] == sys.executable


# ---------- gemini settings ----------


from veles.adapters.cli.mcp_config import build_gemini_mcp_settings  # noqa: E402


def test_build_gemini_mcp_settings_writes_to_dot_gemini_dir(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    path = build_gemini_mcp_settings(project)
    assert path == tmp_path / ".gemini" / "settings.json"
    assert path.is_file()


def test_build_gemini_mcp_settings_uses_sys_executable(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    path = build_gemini_mcp_settings(project)
    settings = json.loads(path.read_text(encoding="utf-8"))
    assert settings["mcpServers"]["veles"]["command"] == sys.executable


def test_build_gemini_mcp_settings_passes_project_root(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    path = build_gemini_mcp_settings(project)
    settings = json.loads(path.read_text(encoding="utf-8"))
    args = settings["mcpServers"]["veles"]["args"]
    assert "--project-root" in args
    assert args[args.index("--project-root") + 1] == str(tmp_path.resolve())


def test_build_gemini_mcp_settings_overwrites_existing(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    first = build_gemini_mcp_settings(project)
    first.write_text("stale", encoding="utf-8")
    second = build_gemini_mcp_settings(project)
    body = second.read_text(encoding="utf-8")
    assert "stale" not in body
    assert json.loads(body)["mcpServers"]["veles"]["command"] == sys.executable


def test_build_mcp_config_passes_budget_file(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    path = build_mcp_config(project)
    config = json.loads(path.read_text(encoding="utf-8"))
    args = config["mcpServers"]["veles"]["args"]
    assert "--budget-file" in args
    expected = str((tmp_path / ".veles" / "budget.state.json").resolve())
    assert args[args.index("--budget-file") + 1] == expected


def test_build_gemini_mcp_settings_passes_budget_file(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    path = build_gemini_mcp_settings(project)
    settings = json.loads(path.read_text(encoding="utf-8"))
    args = settings["mcpServers"]["veles"]["args"]
    assert "--budget-file" in args
    expected = str((tmp_path / ".veles" / "budget.state.json").resolve())
    assert args[args.index("--budget-file") + 1] == expected
