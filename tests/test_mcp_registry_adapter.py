"""M157 — register_mcp_tools tests with a fake manager (no real MCP)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from veles.core.risk import RiskClass
from veles.core.tools.registry import Registry
from veles.mcp.client import ServerStatus
from veles.mcp.config import McpServerConfig
from veles.mcp.registry_adapter import classify_risk, register_mcp_tools, result_to_text


def _tool(name: str, description: str = "does things", schema: Any = None, **hints: Any):
    return SimpleNamespace(
        name=name,
        description=description,
        inputSchema=schema if schema is not None else {"type": "object", "properties": {}},
        annotations=SimpleNamespace(**hints) if hints else None,
    )


def _text_result(*texts: str, is_error: bool = False):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=t) for t in texts],
        isError=is_error,
    )


class FakeManager:
    """Duck-typed stand-in for McpClientManager."""

    def __init__(self, tools_by_server: dict[str, list[Any]], *, failed: set[str] | None = None):
        self._tools = tools_by_server
        self._failed = failed or set()
        self.calls: list[tuple[str, str, dict[str, Any], float | None]] = []
        self.result: Any = _text_result("ok")

    def status(self) -> dict[str, ServerStatus]:
        return {
            name: ServerStatus(
                name=name,
                transport="stdio",
                state="failed" if name in self._failed else "connected",
                error="boom" if name in self._failed else None,
                tool_count=len(tools),
            )
            for name, tools in self._tools.items()
        }

    def list_tools(self, server: str) -> list[Any]:
        return self._tools[server]

    def call_tool(self, server, tool, arguments=None, *, timeout_s=None):
        self.calls.append((server, tool, arguments, timeout_s))
        return self.result


def _cfg(name: str, **kw: Any) -> McpServerConfig:
    return McpServerConfig(name=name, command="fake", **kw)


# ---- naming + registration ----


def test_tool_naming_and_registration() -> None:
    mgr = FakeManager({"gh": [_tool("list_issues"), _tool("create_issue")]})
    reg = Registry()
    names = register_mcp_tools(reg, mgr, {"gh": _cfg("gh")})
    assert names == ["mcp_gh_create_issue", "mcp_gh_list_issues"] or names == [
        "mcp_gh_list_issues",
        "mcp_gh_create_issue",
    ]
    assert set(reg.list_names()) == {"mcp_gh_list_issues", "mcp_gh_create_issue"}
    entry = reg.get("mcp_gh_list_issues")
    assert entry.description.startswith("[MCP:gh]")
    assert "mcp:gh" in entry.side_effects


def test_unsafe_tool_name_rejected() -> None:
    mgr = FakeManager({"gh": [_tool("rm -rf /"), _tool("good_tool")]})
    reg = Registry()
    names = register_mcp_tools(reg, mgr, {"gh": _cfg("gh")})
    assert names == ["mcp_gh_good_tool"]


def test_failed_server_contributes_nothing() -> None:
    mgr = FakeManager({"down": [_tool("x")]}, failed={"down"})
    reg = Registry()
    assert register_mcp_tools(reg, mgr, {"down": _cfg("down")}) == []


def test_disabled_server_skipped() -> None:
    mgr = FakeManager({"gh": [_tool("x")]})
    reg = Registry()
    assert register_mcp_tools(reg, mgr, {"gh": _cfg("gh", enabled=False)}) == []


def test_disabled_tools_filtered() -> None:
    mgr = FakeManager({"gh": [_tool("keep"), _tool("drop")]})
    reg = Registry()
    names = register_mcp_tools(reg, mgr, {"gh": _cfg("gh")}, disabled_tools={"gh": ["drop"]})
    assert names == ["mcp_gh_keep"]


def test_name_collision_warns_and_skips() -> None:
    mgr = FakeManager({"gh": [_tool("dup")]})
    reg = Registry()
    register_mcp_tools(reg, mgr, {"gh": _cfg("gh")})
    # Second registration of the same server/tool into the same registry
    names = register_mcp_tools(reg, mgr, {"gh": _cfg("gh")})
    assert names == []


# ---- handler behaviour ----


def test_handler_routes_args_and_returns_text() -> None:
    mgr = FakeManager({"gh": [_tool("echo")]})
    mgr.result = _text_result("hello", "world")
    reg = Registry()
    register_mcp_tools(reg, mgr, {"gh": _cfg("gh", timeout_s=42.0)})
    out = reg.dispatch("mcp_gh_echo", {"text": "hi", "n": 3})
    assert out == "hello\nworld"
    assert mgr.calls == [("gh", "echo", {"text": "hi", "n": 3}, 42.0)]


def test_handler_surfaces_manager_errors_as_text() -> None:
    class ExplodingManager(FakeManager):
        def call_tool(self, *a: Any, **kw: Any):
            raise RuntimeError("server went away")

    mgr = ExplodingManager({"gh": [_tool("echo")]})
    reg = Registry()
    register_mcp_tools(reg, mgr, {"gh": _cfg("gh")})
    out = reg.dispatch("mcp_gh_echo", {})
    assert "MCP call failed" in out
    assert "server went away" in out


def test_handler_schema_is_sanitized() -> None:
    big = {"properties": {f"p{i}": {"type": "string"} for i in range(99)}}
    mgr = FakeManager({"gh": [_tool("t", schema=big)]})
    reg = Registry()
    register_mcp_tools(reg, mgr, {"gh": _cfg("gh")})
    schema = reg.get("mcp_gh_t").parameter_schema
    assert len(schema["properties"]) == 16


# ---- risk-class mapping ----


def test_readonly_hint_maps_to_read_only() -> None:
    tool = _tool("get_page", readOnlyHint=True)
    assert classify_risk(tool) is RiskClass.READ_ONLY
    mgr = FakeManager({"s": [tool]})
    reg = Registry()
    register_mcp_tools(reg, mgr, {"s": _cfg("s")})
    entry = reg.get("mcp_s_get_page")
    assert entry.risk_class is RiskClass.READ_ONLY
    assert entry.sensitive is False


def test_destructive_hint_maps_to_destructive() -> None:
    tool = _tool("wipe_db", destructiveHint=True, readOnlyHint=False)
    assert classify_risk(tool) is RiskClass.DESTRUCTIVE
    mgr = FakeManager({"s": [tool]})
    reg = Registry()
    register_mcp_tools(reg, mgr, {"s": _cfg("s")})
    entry = reg.get("mcp_s_wipe_db")
    assert entry.risk_class is RiskClass.DESTRUCTIVE
    assert entry.sensitive is True


def test_destructive_wins_over_readonly_lie() -> None:
    # A hostile server claiming both hints must land on the hard gate.
    tool = _tool("trickster", destructiveHint=True, readOnlyHint=True)
    assert classify_risk(tool) is RiskClass.DESTRUCTIVE


def test_no_annotations_defaults_to_network_open_world() -> None:
    tool = _tool("mystery")
    assert classify_risk(tool) is RiskClass.NETWORK_OPEN_WORLD
    mgr = FakeManager({"s": [tool]})
    reg = Registry()
    register_mcp_tools(reg, mgr, {"s": _cfg("s")})
    entry = reg.get("mcp_s_mystery")
    assert entry.risk_class is RiskClass.NETWORK_OPEN_WORLD
    assert entry.sensitive is True  # approval via trust ladder


def test_dict_annotations_supported() -> None:
    tool = {"name": "t", "annotations": {"readOnlyHint": True}, "inputSchema": {}}
    assert classify_risk(tool) is RiskClass.READ_ONLY


# ---- result rendering ----


def test_result_to_text_concatenates_text_blocks() -> None:
    assert result_to_text(_text_result("a", "b")) == "a\nb"


def test_result_to_text_placeholder_for_non_text() -> None:
    result = SimpleNamespace(
        content=[
            SimpleNamespace(type="image", data="...", text=None),
            SimpleNamespace(type="text", text="caption"),
        ],
        isError=False,
    )
    assert result_to_text(result) == "[non-text content: image]\ncaption"


def test_result_to_text_error_prefix() -> None:
    out = result_to_text(_text_result("not found", is_error=True))
    assert out.startswith("MCP tool error:")
    assert "not found" in out


def test_result_to_text_empty() -> None:
    assert result_to_text(SimpleNamespace(content=[], isError=False)) == "(empty MCP result)"
