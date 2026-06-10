"""M157 — McpClientManager integration test against a real stdio MCP server.

Spawns `tests/fixtures/fake_mcp_server.py` (official SDK FastMCP, one
`echo` tool) as a child process and drives connect → list → call through
the synchronous manager facade. Skipped when the child process cannot be
spawned (CI sandboxes without subprocess support) — it must pass locally.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from veles.mcp.client import McpClientManager, McpServerUnavailable
from veles.mcp.config import McpServerConfig
from veles.mcp.registry_adapter import result_to_text

_FIXTURE = Path(__file__).parent / "fixtures" / "fake_mcp_server.py"


@pytest.fixture()
def manager():
    mgr = McpClientManager()
    yield mgr
    mgr.close()


def _fake_server_cfg(**kw) -> McpServerConfig:
    defaults = dict(
        name="fake",
        transport="stdio",
        command=sys.executable,
        args=[str(_FIXTURE)],
        connect_timeout_s=30.0,
        timeout_s=30.0,
    )
    defaults.update(kw)
    return McpServerConfig(**defaults)


def _connect_or_skip(manager: McpClientManager, cfg: McpServerConfig) -> None:
    manager.connect_all({cfg.name: cfg})
    status = manager.status()[cfg.name]
    if status.state != "connected":
        pytest.skip(f"could not spawn fake MCP server in this environment: {status.error}")


def test_connect_list_call_roundtrip(manager: McpClientManager) -> None:
    cfg = _fake_server_cfg()
    _connect_or_skip(manager, cfg)

    tools = manager.list_tools("fake")
    names = [t.name for t in tools]
    assert "echo" in names

    result = manager.call_tool("fake", "echo", {"text": "hi"})
    assert "echo: hi" in result_to_text(result)


def test_connect_failure_is_recorded_not_raised(manager: McpClientManager) -> None:
    cfg = McpServerConfig(
        name="ghost",
        transport="stdio",
        command="/nonexistent/veles-m157-no-such-binary",
        connect_timeout_s=10.0,
    )
    manager.connect_all({"ghost": cfg})  # must not raise
    status = manager.status()["ghost"]
    assert status.state == "failed"
    assert status.error


def test_call_tool_on_unconnected_server_raises(manager: McpClientManager) -> None:
    with pytest.raises(McpServerUnavailable):
        manager.call_tool("never-connected", "echo", {})


def test_close_is_idempotent(manager: McpClientManager) -> None:
    cfg = _fake_server_cfg()
    _connect_or_skip(manager, cfg)
    manager.close()
    manager.close()  # second close must be a no-op
    with pytest.raises(McpServerUnavailable):
        manager.call_tool("fake", "echo", {"text": "x"})


def test_mount_mcp_tools_end_to_end(tmp_path: Path) -> None:
    """Full wiring: project config → mount_mcp_tools → registry dispatch."""
    from veles.core.project import init_project
    from veles.core.tools.registry import Registry
    from veles.mcp import runtime

    project = init_project(tmp_path / "demo", name="demo")
    (project.state_dir / "config.toml").write_text(
        "[mcp.servers.fake]\n"
        f'command = "{sys.executable}"\n'
        f'args = ["{_FIXTURE}"]\n'
        "connect_timeout_s = 30\n",
        encoding="utf-8",
    )
    reg = Registry()
    try:
        names = runtime.mount_mcp_tools(reg, project)
        if not names:
            status = runtime.get_manager().status().get("fake")
            pytest.skip(
                "could not spawn fake MCP server in this environment: "
                f"{status.error if status else 'unknown'}"
            )
        assert names == ["mcp_fake_echo"]
        entry = reg.get("mcp_fake_echo")
        assert entry.risk_class is not None  # permission engine sees metadata
        out = reg.dispatch("mcp_fake_echo", {"text": "ping"})
        assert "echo: ping" in out
    finally:
        runtime.shutdown_mcp()
