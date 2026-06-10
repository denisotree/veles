"""Parser for `veles mcp {list,test}` (M157)."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    mcp = sub.add_parser(
        "mcp",
        help="Inspect external MCP servers configured in [mcp.servers.*].",
    )
    add_project_root_flag(mcp)
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)

    mcp_list = mcp_sub.add_parser(
        "list",
        help="Show configured MCP servers with connection status and tool counts.",
    )
    mcp_list.add_argument(
        "--connect-timeout",
        type=float,
        default=10.0,
        help="Per-server connect budget in seconds for the status probe (default: 10).",
    )

    mcp_test = mcp_sub.add_parser(
        "test",
        help="Connect to one MCP server and list its tools.",
    )
    mcp_test.add_argument("server", help="Server name (key under [mcp.servers.*]).")
