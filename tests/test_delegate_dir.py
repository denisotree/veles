"""Release E: a CLI delegate's MCP config and budget live in a directory of their
own per process, under .veles/tmp, gone when the process ends."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from veles.core.project import init_project


def test_each_process_gets_its_own_delegate_dir(tmp_path: Path) -> None:
    from veles.core.delegate_dir import delegate_dir

    project = init_project(tmp_path, name="p")
    mine = delegate_dir(project)
    assert mine == project.tmp_dir / f"delegate-{os.getpid()}" and mine.is_dir()
    assert delegate_dir(project) == mine
    other = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from veles.core.project import load_project; "
            "from veles.core.delegate_dir import delegate_dir; "
            f"print(delegate_dir(load_project(Path({str(tmp_path)!r}))))",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert other != str(mine) and not Path(other).exists()  # removed at its exit


def test_a_dead_processes_dir_is_swept(tmp_path: Path) -> None:
    from veles.core import delegate_dir as mod

    project = init_project(tmp_path, name="p")
    dead = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getpid())"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    stale = project.tmp_dir / f"delegate-{dead}"
    stale.mkdir(parents=True)
    alive = project.tmp_dir / f"delegate-{os.getppid()}"
    alive.mkdir(parents=True)
    mod._registered.clear()
    mod.delegate_dir(project)
    assert not stale.exists() and alive.exists()


def test_mcp_config_lives_in_the_delegate_dir(tmp_path: Path) -> None:
    from veles.adapters.cli.mcp_config import build_mcp_config
    from veles.core.delegate_dir import delegate_budget_file, delegate_dir

    project = init_project(tmp_path, name="p")
    path = build_mcp_config(project)
    assert path == delegate_dir(project) / "mcp.json"
    args = json.loads(path.read_text(encoding="utf-8"))["mcpServers"]["veles"]["args"]
    assert args[args.index("--budget-file") + 1] == str(delegate_budget_file(project))
    assert "--skill-model" not in args
    assert not (project.state_dir / "mcp.json").exists()


def test_export_skips_veles_tmp(tmp_path: Path) -> None:
    from veles.core.delegate_dir import delegate_dir
    from veles.core.export import _is_excluded

    project = init_project(tmp_path, name="p")
    rel = (delegate_dir(project) / "mcp.json").relative_to(project.root).as_posix()
    assert _is_excluded(rel, "mcp.json", mode="full")


def test_claude_tool_aware_comes_from_the_catalogue(tmp_path: Path) -> None:
    from veles.core.delegate_dir import delegate_dir
    from veles.runtime.registry import make_tool_aware_provider

    project = init_project(tmp_path, name="p")
    prov = make_tool_aware_provider("claude-cli", project)
    assert prov.supports_tools and prov._mcp_config_path == delegate_dir(project) / "mcp.json"
    assert prov.qualify_prompt("use read_file", ("read_file",)) == "use mcp__veles__read_file"
