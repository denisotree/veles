"""`veles mcp {list,test}` (M157) — inspect configured external MCP servers.

Subcommands:

    veles mcp list           — every [mcp.servers.*] entry with a live
                               connect probe (short timeout), status and
                               tool count. rc 0 even when servers fail —
                               this is an inspection verb, not a health gate.
    veles mcp test <server>  — connect to one server and print its tools
                               with sanitized descriptions. rc 1 when the
                               connect fails, rc 2 for an unknown name.

Both verbs use a *fresh* `McpClientManager` (not the process-global agent
one) and close it before returning, so a one-shot probe never leaves
stdio subprocesses behind.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys

from veles.core.project import Project


def cmd_mcp(args: argparse.Namespace, project: Project) -> int:
    sub = args.mcp_command
    if sub == "list":
        return _list(args, project)
    if sub == "test":
        return _test(args, project)
    print(f"error: unknown mcp subcommand: {sub!r}", file=sys.stderr)
    return 2


def _list(args: argparse.Namespace, project: Project) -> int:
    from veles.mcp.client import McpClientManager
    from veles.mcp.config import load_mcp_config

    configs = load_mcp_config(project)
    if not configs:
        print(
            "no MCP servers configured.\n"
            "Add [mcp.servers.<name>] sections to "
            f"{project.state_dir / 'config.toml'} to connect external tools."
        )
        return 0

    probe_budget = max(float(getattr(args, "connect_timeout", 10.0)), 0.1)
    to_probe = {
        name: dataclasses.replace(
            cfg, connect_timeout_s=min(cfg.connect_timeout_s, probe_budget)
        )
        for name, cfg in configs.items()
        if cfg.enabled
    }

    manager = McpClientManager()
    try:
        manager.connect_all(to_probe)
        statuses = manager.status()
        for name in sorted(configs):
            cfg = configs[name]
            if not cfg.enabled:
                print(f"  {name:<20} {cfg.transport:<6} disabled")
                continue
            st = statuses.get(name)
            if st is None or st.state != "connected":
                err = (st.error if st is not None else None) or "no connection attempt"
                print(f"  {name:<20} {cfg.transport:<6} failed     {err}")
            else:
                print(f"  {name:<20} {cfg.transport:<6} connected  {st.tool_count} tool(s)")
    finally:
        manager.close()
    return 0


def _test(args: argparse.Namespace, project: Project) -> int:
    from veles.mcp.client import McpClientManager
    from veles.mcp.config import load_mcp_config
    from veles.mcp.sanitize import normalize_tool_name, sanitize_text

    configs = load_mcp_config(project)
    cfg = configs.get(args.server)
    if cfg is None:
        known = ", ".join(sorted(configs)) or "(none)"
        print(
            f"error: no MCP server named {args.server!r} in config (known: {known})",
            file=sys.stderr,
        )
        return 2
    if not cfg.enabled:
        print(f"error: MCP server {args.server!r} is disabled in config", file=sys.stderr)
        return 1

    manager = McpClientManager()
    try:
        manager.connect_all({args.server: cfg})
        st = manager.status().get(args.server)
        if st is None or st.state != "connected":
            err = (st.error if st is not None else None) or "unknown error"
            print(f"error: could not connect to {args.server!r}: {err}", file=sys.stderr)
            return 1
        tools = manager.list_tools(args.server)
        print(f"{args.server}: connected ({cfg.transport}), {len(tools)} tool(s)")
        for tool in tools:
            raw_name = getattr(tool, "name", None)
            safe = normalize_tool_name(raw_name) if raw_name is not None else None
            shown = safe or f"(rejected name: {sanitize_text(raw_name, limit=64)})"
            desc = sanitize_text(getattr(tool, "description", "") or "")
            print(f"  {shown:<32} {desc}")
    finally:
        manager.close()
    return 0
