---
title: Connect external MCP servers
topics: [mcp, server, tool, external, config]
related: ["cmd:mcp"]
---

Configure external MCP servers under `[mcp.servers.<name>]` in
`config.toml` (command + args for a stdio server); Veles mounts their tools
alongside builtins.

Use `veles mcp list` to see configured servers with connection status and
tool counts, and `veles mcp test <name>` to connect to one server and list
the tools it offers.

Example: `veles mcp test graphify`.
