"""M165b: MCP-driven project-tool provisioning (graphify rebuild)."""

from __future__ import annotations

from pathlib import Path

from veles.core.project import init_project
from veles.core.project_config import save_project_config
from veles.core.tools.loader import load_into_registry
from veles.core.tools.registry import Registry
from veles.mcp.provision import ensure_mcp_project_tools


def _graphify_project(tmp_path: Path):
    project = init_project(tmp_path, name=None, force=False)
    save_project_config(
        project,
        {"mcp": {"servers": {"graphify": {"command": "graphify-mcp", "args": ["graph.json"]}}}},
    )
    return project


def test_provisions_graphify_tool_when_configured(tmp_path: Path) -> None:
    project = _graphify_project(tmp_path)
    assert ensure_mcp_project_tools(project) == ["graphify_rebuild.py"]
    assert (project.state_dir / "tools" / "graphify_rebuild.py").is_file()


def test_provision_is_idempotent_and_preserves_edits(tmp_path: Path) -> None:
    project = _graphify_project(tmp_path)
    assert ensure_mcp_project_tools(project) == ["graphify_rebuild.py"]
    dst = project.state_dir / "tools" / "graphify_rebuild.py"
    dst.write_text("# user edit\n", encoding="utf-8")
    # Second call must not overwrite an existing tool file.
    assert ensure_mcp_project_tools(project) == []
    assert dst.read_text(encoding="utf-8") == "# user edit\n"


def test_no_provision_without_graphify_mcp(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    assert ensure_mcp_project_tools(project) == []
    assert not (project.state_dir / "tools" / "graphify_rebuild.py").exists()


def test_provisioned_tool_loads_into_registry(tmp_path: Path) -> None:
    """The copied template is a valid file-based tool the loader picks up."""
    project = _graphify_project(tmp_path)
    ensure_mcp_project_tools(project)
    reg = Registry()
    report = load_into_registry(reg, project_tools_dir=project.state_dir / "tools")
    assert "graphify_rebuild" in [lt.entry.name for lt in report.loaded]
    assert "graphify_rebuild" in reg.list_names()
    assert not report.errors
