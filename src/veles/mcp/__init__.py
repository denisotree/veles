"""MCP *client* support (M157).

Connects to external MCP servers declared in `<project>/.veles/config.toml`
under `[mcp.servers.<name>]` and exposes their tools to the agent loop
through the standard tool `Registry`, so the Permission Engine / trust
ladder sees them like any builtin tool.

Not to be confused with `veles.adapters.cli.mcp_server`, which is the MCP
*server* side (exposing Veles tools to claude-cli / gemini-cli).

Modules:
  config.py            — `[mcp.servers.*]` parsing + ${VAR} interpolation.
  sanitize.py          — untrusted-schema caps (names, descriptions, params).
  client.py            — `McpClientManager`: sync facade over the asyncio
                         SDK via a background event loop in a daemon thread.
  registry_adapter.py  — `register_mcp_tools(...)`: ToolEntry construction
                         + risk-class mapping (readOnlyHint / destructiveHint).
  runtime.py           — process-global lazy manager + `mount_mcp_tools`.

Callers import from the submodules; the package itself exports nothing, so
importing it stays free of the MCP SDK.
"""
