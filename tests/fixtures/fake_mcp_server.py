"""Tiny stdio MCP server used by the M157 integration tests.

Exposes one `echo` tool via the official SDK's FastMCP server API.
Spawned as a child process by `tests/test_mcp_client_integration.py`
(and by the CLI tests that need a real connectable server).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

server = FastMCP("fake-veles-test-server")


@server.tool()
def echo(text: str) -> str:
    """Echo the input text back, prefixed."""
    return f"echo: {text}"


if __name__ == "__main__":
    server.run()  # stdio transport by default
