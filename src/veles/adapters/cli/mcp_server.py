"""MCP server entrypoint — exposes Veles builtin tools and project skills.

Run as:
    python -m veles.adapters.cli.mcp_server --project-root <path> [--skill-model <id>]

Speaks JSON-RPC 2.0 on stdin/stdout, implements the Model Context Protocol
methods we need: `initialize`, `tools/list`, `tools/call`, plus the no-op
`notifications/initialized`. Logs go to stderr so they never collide with
the response stream.

Skills (M19): per-project skills under `<project>/.veles/skills/<name>/`
are exposed as MCP tools when `OPENROUTER_API_KEY` is set. The skill
sub-agent runs through OpenRouter inside this process, so the parent CLI
delegate (claude/gemini) does not need to bridge an LLM back into Veles.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import IO, Any

from veles.core.budget_state import BudgetSnapshot, save_atomic
from veles.core.budget_state import load as load_budget_snapshot
from veles.core.context import (
    TokenBudget,
    current_budget,
    set_active_project,
    set_budget,
)
from veles.core.project import Project, load_project
from veles.core.tools import registry  # importing also triggers builtin registration
from veles.core.tools.registry import Registry

_PROTOCOL_VERSION = "2024-11-05"
_SERVER_NAME = "veles"
_SERVER_VERSION = "0.1"
_DEFAULT_SKILL_MODEL = "anthropic/claude-sonnet-4.6"

_MCP_TOOLS: tuple[str, ...] = (
    "read_file",
    "write_file",
    "run_shell",
    "fetch_url",
    "wiki_list_pages",
    "wiki_read_page",
    "wiki_search",
    "wiki_write_page",
    "wiki_append_log",
)


class MCPServer:
    def __init__(
        self,
        registry: Registry,
        tool_names: list[str],
        *,
        budget_path: Path | None = None,
    ) -> None:
        self._registry = registry
        self._tool_names = tool_names
        self._budget_path = budget_path

    def serve(self, *, stdin: IO[str], stdout: IO[str]) -> int:
        for raw_line in stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                _log(f"invalid JSON-RPC: {exc}")
                continue
            response = self.handle(request)
            if response is not None:
                stdout.write(json.dumps(response) + "\n")
                stdout.flush()
        return 0

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        if method == "notifications/initialized":
            return None  # MCP spec: notifications never get a response
        if method == "initialize":
            return self._handle_initialize(request)
        if method == "tools/list":
            return self._handle_tools_list(request)
        if method == "tools/call":
            return self._handle_tools_call(request)
        return _error(request.get("id"), -32601, f"unknown method: {method!r}")

    def _handle_initialize(self, req: dict[str, Any]) -> dict[str, Any]:
        return _success(
            req.get("id"),
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": _SERVER_NAME, "version": _SERVER_VERSION},
            },
        )

    def _handle_tools_list(self, req: dict[str, Any]) -> dict[str, Any]:
        out: list[dict[str, Any]] = []
        for name in self._tool_names:
            try:
                entry = self._registry.get(name)
            except KeyError:
                continue
            out.append(
                {
                    "name": entry.name,
                    "description": entry.description,
                    "inputSchema": entry.parameter_schema,
                }
            )
        return _success(req.get("id"), {"tools": out})

    def _handle_tools_call(self, req: dict[str, Any]) -> dict[str, Any]:
        params = req.get("params") or {}
        name = params.get("name") or ""
        arguments = params.get("arguments") or {}
        if name not in self._tool_names:
            return _error(req.get("id"), -32602, f"tool {name!r} not exposed")
        try:
            output = self._registry.dispatch(name, arguments)
        except Exception as exc:
            return _success(
                req.get("id"),
                {
                    "content": [{"type": "text", "text": f"<error: {type(exc).__name__}: {exc}>"}],
                    "isError": True,
                },
            )
        self._persist_budget()
        return _success(
            req.get("id"),
            {"content": [{"type": "text", "text": str(output)}]},
        )

    def _persist_budget(self) -> None:
        if self._budget_path is None:
            return
        budget = current_budget()
        if budget is None:
            return
        try:
            save_atomic(
                self._budget_path,
                BudgetSnapshot(limit=budget.limit, consumed=budget.consumed),
            )
        except OSError as exc:
            _log(f"failed to persist budget snapshot: {exc}")


def _success(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _log(message: str) -> None:
    print(f"[veles-mcp] {message}", file=sys.stderr, flush=True)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="veles-mcp-server")
    parser.add_argument(
        "--project-root",
        required=True,
        help="Project root whose .veles/project.toml is loaded as the active project.",
    )
    parser.add_argument(
        "--skill-model",
        default=_DEFAULT_SKILL_MODEL,
        help=f"OpenRouter model used to execute project skills (default: {_DEFAULT_SKILL_MODEL}).",
    )
    parser.add_argument(
        "--budget-file",
        default=None,
        help="Path to BudgetSnapshot JSON for cross-process token-budget propagation.",
    )
    return parser.parse_args(argv)


def _register_project_skills(registry_obj: Registry, project: Project, model: str) -> list[str]:
    """Register every project skill into `registry_obj`. Returns added names."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        _log("OPENROUTER_API_KEY missing — skill tools disabled")
        return []
    from veles.adapters.openrouter import OpenRouterProvider
    from veles.core.skills import discover_skills, make_skill_tool

    skills = discover_skills(project)
    if not skills:
        return []
    provider = OpenRouterProvider()
    out: list[str] = []
    for skill in skills:
        try:
            entry = make_skill_tool(
                skill, provider=provider, model=model, base_registry=registry_obj
            )
            registry_obj.register(entry)
            out.append(skill.name)
        except Exception as exc:
            _log(f"failed to register skill {skill.name!r}: {exc}")
    return out


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project = load_project(Path(args.project_root))
    set_active_project(project)
    budget_path = Path(args.budget_file) if args.budget_file else None
    if budget_path is not None:
        snap = load_budget_snapshot(budget_path)
        if snap is not None:
            set_budget(TokenBudget(limit=snap.limit, consumed=snap.consumed))
    composite = registry.subset(registry.list_names())
    skill_names = _register_project_skills(composite, project, args.skill_model)
    server = MCPServer(composite, list(_MCP_TOOLS) + skill_names, budget_path=budget_path)
    return server.serve(stdin=sys.stdin, stdout=sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
