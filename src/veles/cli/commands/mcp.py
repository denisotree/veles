"""`veles mcp {list,test,approve}` (M157) — inspect and approve external MCP servers.

Subcommands:

    veles mcp list             — every [mcp.servers.*] entry with its approval
                                 state and, for approved ones, a live connect
                                 probe (short timeout), status and tool count.
                                 rc 0 even when servers fail — this is an
                                 inspection verb, not a health gate.
    veles mcp test <server>    — connect to one approved server and print its
                                 tools with sanitized descriptions. rc 1 when
                                 the server is unapproved or the connect fails,
                                 rc 2 for an unknown name.
    veles mcp approve <server> — show the whole raw recipe (env values too) and
                                 record it as approved after `confirm_critical`.

A server spawns only once its exact raw recipe is approved
(`veles.mcp.approvals`); `list` and `test` never probe an unapproved one.

Both probing verbs use a *fresh* `McpClientManager` (not the process-global
agent one) and close it before returning, so a one-shot probe never leaves
stdio subprocesses behind.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys

from veles.core.project import Project
from veles.core.text import shown


def cmd_mcp(args: argparse.Namespace, project: Project) -> int:
    sub = args.mcp_command
    if sub == "list":
        return _list(args, project)
    if sub == "test":
        return _test(args, project)
    if sub == "approve":
        return _approve(args, project)
    print(f"error: unknown mcp subcommand: {sub!r}", file=sys.stderr)
    return 2


def _approve_hint(name: str) -> str:
    return (
        f"MCP server {shown(name)} is not approved (or changed since approval) — "
        f"review it, then `veles mcp approve {shown(name)}`"
    )


def _list(args: argparse.Namespace, project: Project) -> int:
    from veles.mcp.approvals import approval_state
    from veles.mcp.client import McpClientManager
    from veles.mcp.config import load_raw_mcp_servers, parse_servers

    raw = load_raw_mcp_servers(project)
    configs = parse_servers(raw)
    if not configs:
        print(
            "no MCP servers configured.\n"
            "Add [mcp.servers.<name>] sections to "
            f"{project.state_dir / 'config.toml'} to connect external tools."
        )
        return 0

    states = {name: approval_state(project.root, name, raw[name]) for name in configs}
    probe_budget = max(float(getattr(args, "connect_timeout", 10.0)), 0.1)
    to_probe = {
        name: dataclasses.replace(cfg, connect_timeout_s=min(cfg.connect_timeout_s, probe_budget))
        for name, cfg in configs.items()
        if cfg.enabled and states[name] == "yes"
    }

    manager = McpClientManager()
    try:
        manager.connect_all(to_probe)
        statuses = manager.status()
        print(f"  {'name':<20} {'via':<6} {'approved':<8} status")
        for name in sorted(configs):
            cfg = configs[name]
            head = f"  {shown(name):<20} {cfg.transport:<6} {states[name]:<8}"
            if not cfg.enabled:
                print(f"{head} disabled")
                continue
            if name not in to_probe:
                print(f"{head} not started — review it, then `veles mcp approve {shown(name)}`")
                continue
            st = statuses.get(name)
            if st is None or st.state != "connected":
                err = (st.error if st is not None else None) or "no connection attempt"
                print(f"{head} failed     {err}")
            else:
                print(f"{head} connected  {st.tool_count} tool(s)")
    finally:
        manager.close()
    return 0


def _test(args: argparse.Namespace, project: Project) -> int:
    from veles.mcp.approvals import approval_state
    from veles.mcp.client import McpClientManager
    from veles.mcp.config import load_raw_mcp_servers, parse_servers
    from veles.mcp.sanitize import normalize_tool_name, sanitize_text

    raw = load_raw_mcp_servers(project)
    configs = parse_servers(raw)
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
    if approval_state(project.root, args.server, raw[args.server]) != "yes":
        print(f"error: {_approve_hint(args.server)}", file=sys.stderr)
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
            shown_name = safe or f"(rejected name: {sanitize_text(raw_name, limit=64)})"
            desc = sanitize_text(getattr(tool, "description", "") or "")
            print(f"  {shown_name:<32} {desc}")
    finally:
        manager.close()
    return 0


def _approve(args: argparse.Namespace, project: Project) -> int:
    from veles.core.critical_ops import confirm_critical
    from veles.mcp.approvals import approval_hash, approve, describe_recipe, recipe_hash
    from veles.mcp.config import load_raw_mcp_servers

    name = args.server
    recipe = load_raw_mcp_servers(project).get(name)
    if not isinstance(recipe, dict):
        print(f"error: no MCP server named {shown(name)} in config", file=sys.stderr)
        return 2
    digest = recipe_hash(recipe)
    reviewed = approval_hash(project.root, recipe)  # includes the project files it runs
    if not confirm_critical(
        f"approve MCP server {shown(name)}", describe_recipe(name, recipe, project.root)
    ):
        print("aborted — nothing approved.", file=sys.stderr)
        return 1
    # The config may have changed while the user was reading: approve only what
    # was shown.
    again = load_raw_mcp_servers(project).get(name)
    if (
        not isinstance(again, dict)
        or recipe_hash(again) != digest
        or approval_hash(project.root, again) != reviewed
    ):
        print(
            f"error: [mcp.servers.{shown(name)}] changed during review — nothing approved; "
            "run the command again.",
            file=sys.stderr,
        )
        return 1
    approve(project.root, name, again)
    print(f"approved MCP server {shown(name)} (sha256 {digest[:12]})")
    return 0
