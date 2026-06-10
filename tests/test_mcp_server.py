"""Unit tests for the Veles MCP server JSON-RPC handlers."""

from __future__ import annotations

import io
import json
from pathlib import Path

from veles.adapters.cli.mcp_server import (
    _MCP_TOOLS,
    MCPServer,
    _parse_args,
    _register_project_skills,
    main,
)
from veles.core.budget_state import BudgetSnapshot, save_atomic
from veles.core.budget_state import load as load_budget_snapshot
from veles.core.context import (
    TokenBudget,
    current_budget,
    reset_budget,
    set_budget,
)
from veles.core.project import init_project
from veles.core.tools.registry import Registry, ToolEntry


def _make_server(extra_tools: list[ToolEntry] | None = None) -> MCPServer:
    reg = Registry()
    if extra_tools:
        for t in extra_tools:
            reg.register(t)
    return MCPServer(reg, [t.name for t in (extra_tools or [])])


def test_initialize_returns_protocol_version() -> None:
    server = _make_server()
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp is not None
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["protocolVersion"]
    assert resp["result"]["serverInfo"]["name"] == "veles"


def test_initialize_advertises_tools_capability() -> None:
    server = _make_server()
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp is not None
    assert "tools" in resp["result"]["capabilities"]


def test_tools_list_returns_registered_tools() -> None:
    entry = ToolEntry(
        name="echo",
        description="echoes",
        parameter_schema={"type": "object", "properties": {}},
        handler=lambda **_: "ok",
        is_async=False,
    )
    server = _make_server([entry])
    resp = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert resp is not None
    tools = resp["result"]["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "echo"
    assert tools[0]["inputSchema"]["type"] == "object"


def test_tools_list_skips_unregistered_names() -> None:
    # Server claims ["echo", "ghost"] but registry only has "echo".
    entry = ToolEntry(
        name="echo",
        description="e",
        parameter_schema={"type": "object", "properties": {}},
        handler=lambda **_: "ok",
        is_async=False,
    )
    reg = Registry()
    reg.register(entry)
    server = MCPServer(reg, ["echo", "ghost"])
    resp = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    assert resp is not None
    names = [t["name"] for t in resp["result"]["tools"]]
    assert names == ["echo"]


def test_tools_call_dispatches_to_registry() -> None:
    received: dict = {}

    def handler(**kwargs) -> str:
        received.update(kwargs)
        return "dispatched"

    entry = ToolEntry(
        name="echo",
        description="e",
        parameter_schema={"type": "object", "properties": {}},
        handler=handler,
        is_async=False,
    )
    server = _make_server([entry])
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"x": 1}},
        }
    )
    assert resp is not None
    assert received == {"x": 1}
    assert resp["result"]["content"][0]["text"] == "dispatched"


def test_tools_call_unknown_tool_returns_error() -> None:
    server = _make_server()
    resp = server.handle(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "nope"}}
    )
    assert resp is not None
    assert "error" in resp
    assert "not exposed" in resp["error"]["message"]


def test_tools_call_handler_exception_returns_is_error() -> None:
    def boom(**_kwargs) -> str:
        raise ValueError("kaboom")

    entry = ToolEntry(
        name="bad",
        description="b",
        parameter_schema={"type": "object", "properties": {}},
        handler=boom,
        is_async=False,
    )
    server = _make_server([entry])
    resp = server.handle(
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "bad"}}
    )
    assert resp is not None
    assert resp["result"]["isError"] is True
    assert "kaboom" in resp["result"]["content"][0]["text"]


def test_unknown_method_returns_method_not_found() -> None:
    server = _make_server()
    resp = server.handle({"jsonrpc": "2.0", "id": 7, "method": "wat/is/this"})
    assert resp is not None
    assert resp["error"]["code"] == -32601


def test_notifications_initialized_returns_none() -> None:
    server = _make_server()
    resp = server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert resp is None


def test_serve_reads_lines_and_writes_responses() -> None:
    entry = ToolEntry(
        name="echo",
        description="e",
        parameter_schema={"type": "object", "properties": {}},
        handler=lambda **_: "ack",
        is_async=False,
    )
    server = _make_server([entry])
    stdin = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        + "\n"
        + json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "echo"},
            }
        )
        + "\n"
    )
    stdout = io.StringIO()
    server.serve(stdin=stdin, stdout=stdout)
    lines = stdout.getvalue().strip().splitlines()
    assert len(lines) == 2
    r1 = json.loads(lines[0])
    r2 = json.loads(lines[1])
    assert r1["id"] == 1 and r1["result"]["tools"][0]["name"] == "echo"
    assert r2["id"] == 2 and r2["result"]["content"][0]["text"] == "ack"


def test_serve_skips_invalid_json_lines() -> None:
    server = _make_server()
    stdin = io.StringIO(
        "not json\n" + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n"
    )
    stdout = io.StringIO()
    server.serve(stdin=stdin, stdout=stdout)
    lines = stdout.getvalue().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == 1


def test_serve_handles_empty_lines() -> None:
    server = _make_server()
    stdin = io.StringIO(
        "\n\n" + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n\n"
    )
    stdout = io.StringIO()
    server.serve(stdin=stdin, stdout=stdout)
    lines = stdout.getvalue().strip().splitlines()
    assert len(lines) == 1


def test_mcp_tools_constant_is_non_empty() -> None:
    assert len(_MCP_TOOLS) >= 5
    assert "read_file" in _MCP_TOOLS
    assert "wiki_write_page" in _MCP_TOOLS


def test_parse_args_accepts_skill_model() -> None:
    args = _parse_args(["--project-root", "/tmp/x", "--skill-model", "openai/gpt-5-mini"])
    assert args.skill_model == "openai/gpt-5-mini"


def test_parse_args_skill_model_has_default() -> None:
    args = _parse_args(["--project-root", "/tmp/x"])
    assert "/" in args.skill_model  # provider/model format


def _write_skill(project_root: Path, name: str, body: str = "Echo input.") -> None:
    skill_dir = project_root / ".veles" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\ntools: []\nmax_iterations: 1\n---\n{body}\n",
        encoding="utf-8",
    )


def test_register_project_skills_no_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    project = init_project(tmp_path, name="t")
    _write_skill(tmp_path, "echo-skill")
    reg = Registry()
    added = _register_project_skills(reg, project, "anthropic/claude-sonnet-4.6")
    assert added == []


def test_register_project_skills_registers_when_key_present(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")
    project = init_project(tmp_path, name="t")
    _write_skill(tmp_path, "echo-skill")
    reg = Registry()
    added = _register_project_skills(reg, project, "anthropic/claude-sonnet-4.6")
    assert added == ["echo-skill"]
    entry = reg.get("echo-skill")
    assert entry.description == "test skill"
    assert "input" in entry.parameter_schema["properties"]


def test_register_project_skills_empty_when_no_skills(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")
    project = init_project(tmp_path, name="t")
    reg = Registry()
    added = _register_project_skills(reg, project, "anthropic/claude-sonnet-4.6")
    assert added == []


def test_parse_args_accepts_budget_file() -> None:
    args = _parse_args(["--project-root", "/tmp/x", "--budget-file", "/tmp/x/.veles/b.json"])
    assert args.budget_file == "/tmp/x/.veles/b.json"


def test_parse_args_budget_file_default_none() -> None:
    args = _parse_args(["--project-root", "/tmp/x"])
    assert args.budget_file is None


def test_main_loads_budget_snapshot_into_context(monkeypatch, tmp_path) -> None:
    project = init_project(tmp_path, name="t")
    snap_path = project.state_dir / "budget.state.json"
    save_atomic(snap_path, BudgetSnapshot(limit=50_000, consumed=1_111))

    captured: dict = {}

    class _StubServer:
        def __init__(self, *_args, **_kwargs) -> None:
            captured["budget"] = current_budget()

        def serve(self, **_kwargs) -> int:
            return 0

    monkeypatch.setattr("veles.adapters.cli.mcp_server.MCPServer", _StubServer)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    sentinel_token = set_budget(None)
    try:
        rc = main(
            [
                "--project-root",
                str(tmp_path),
                "--budget-file",
                str(snap_path),
            ]
        )
        assert rc == 0
        budget = captured["budget"]
        assert budget is not None
        assert budget.limit == 50_000
        assert budget.consumed == 1_111
    finally:
        reset_budget(sentinel_token)


def test_handle_tools_call_persists_budget_snapshot(tmp_path) -> None:
    snap_path = tmp_path / "budget.state.json"
    save_atomic(snap_path, BudgetSnapshot(limit=50_000, consumed=100))
    token = set_budget(TokenBudget(limit=50_000, consumed=100))

    def handler(**_kwargs) -> str:
        # Simulate a sub-agent that consumed extra tokens before returning.
        b = current_budget()
        assert b is not None
        b.consumed += 250
        return "ok"

    entry = ToolEntry(
        name="bumpy",
        description="b",
        parameter_schema={"type": "object", "properties": {}},
        handler=handler,
        is_async=False,
    )
    reg = Registry()
    reg.register(entry)
    server = MCPServer(reg, ["bumpy"], budget_path=snap_path)
    try:
        resp = server.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "bumpy"}}
        )
        assert resp is not None and "result" in resp
        loaded = load_budget_snapshot(snap_path)
        assert loaded == BudgetSnapshot(limit=50_000, consumed=350)
    finally:
        reset_budget(token)
