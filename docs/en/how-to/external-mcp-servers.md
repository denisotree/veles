# How to connect external MCP servers

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/external-mcp-servers.md)

Veles is an [MCP](https://modelcontextprotocol.io/) **client**: it can connect to
external MCP servers and expose their tools to the agent as if they were built in
(GitHub, web search, your own services, …).

## Configure a server

Add a `[mcp.servers.<name>]` block to `<project>/.veles/config.toml` (or the
user-global `~/.veles/config.toml`). Three transports are supported: `stdio`,
`http`, `sse`.

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx -y @modelcontextprotocol/server-github"
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
enabled = true

[mcp.servers.search]
transport = "http"
url = "http://localhost:3000/mcp"
```

To hide specific tools from a server, use `[mcp] disabled_tools = ["..."]`.

## Inspect and test

```bash
veles mcp list                  # configured servers, connection status, tool counts
veles mcp test github           # connect to one server and list its tools
```

## How the tools appear

Connected server tools enter the normal tool registry as
`mcp_<server>_<tool>` and are callable by the agent like any builtin. Their
schemas are sanitised (name/length limits, control-char stripping) so an untrusted
server can't inject into the prompt. Tool hints map to the trust ladder:
destructive tools always confirm, read-only tools are unprompted, others go
through the usual [trust](security-and-permissions.md) flow.

## Failure handling

A server that fails to connect is logged as a warning and skipped — it never
blocks startup or the agent. Re-run `veles mcp list` to see status.
