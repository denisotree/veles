# How to connect external MCP servers

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/how-to/external-mcp-servers.md) · [繁體中文](../../zh-TW/how-to/external-mcp-servers.md) · [日本語](../../ja/how-to/external-mcp-servers.md) · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · [Français](../../fr/how-to/external-mcp-servers.md) · [Italiano](../../it/how-to/external-mcp-servers.md) · [Português (BR)](../../pt-BR/how-to/external-mcp-servers.md) · [Português (PT)](../../pt-PT/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · [العربية](../../ar/how-to/external-mcp-servers.md) · [हिन्दी](../../hi/how-to/external-mcp-servers.md) · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

Veles is an [MCP](https://modelcontextprotocol.io/) **client**: it can connect to
external MCP servers and expose their tools to the agent as if they were built in
(GitHub, library docs, web search, your own services, …).

## Configure a server

Add a `[mcp.servers.<name>]` block to `<project>/.veles/config.toml` (or the
user-global `~/.veles/config.toml`). The `<name>` must match
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` — it becomes part of each tool's name. Three
transports are supported: `stdio` (default), `http`, `sse`.

| Key | Transport | Default | Purpose |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (required) | — | the executable to launch — **the program only, not its arguments** |
| `args` | stdio | `[]` | argument list, one token per item |
| `env` | stdio | `{}` | extra environment for the subprocess (merged over the inherited env) |
| `url` | http/sse (required) | — | the server endpoint |
| `timeout_s` | — | `120` | budget for a single tool call |
| `connect_timeout_s` | — | `30` | budget for the initial connection |
| `enabled` | — | `true` | set `false` to keep the entry but skip connecting |

String values in `command`, `args`, `env`, and `url` interpolate `${VAR}` from the
environment (an unset variable becomes an empty string with a warning) — keep
secrets out of the file.

> **`command` vs `args`.** Veles runs the program directly (no shell), so the
> executable and its arguments are **separate** fields. Write
> `command = "npx"`, `args = ["-y", "pkg"]` — **not** `command = "npx -y pkg"`.

### stdio (local subprocess)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

A server you run yourself works the same way — point `command`/`args` at it:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### A server that needs an API key (context7)

[Context7](https://context7.com) serves up-to-date library documentation. Pass the
key as an argument so `${VAR}` keeps it out of the file:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse (remote)

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **No custom headers (yet).** The `http`/`sse` transports send only the `url` —
> Veles cannot attach an `Authorization` header. For a remote server that needs a
> key, prefer its `stdio` (e.g. `npx`) variant with the key in `args`/`env`, or an
> endpoint that accepts the key in the URL.

## Hide specific tools

Set `[mcp] disabled_tools` — a table mapping each server to the tool names to skip:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## Inspect and test

```bash
veles mcp list              # every configured server: transport, status, tool count
veles mcp test github       # connect to one server and list its tools
```

`veles mcp list` always exits 0 — it's an inspector, not a health gate.
`veles mcp test` exits 1 when the connection fails and 2 for an unknown server name.

## How the tools appear

Once configured, servers are mounted **automatically** on the next `veles run` /
TUI / daemon start — there is no separate "enable MCP" flag, the presence of the
config is the switch. Each tool enters the normal registry as `mcp_<server>_<tool>`
and is callable by the agent like any builtin. Schemas are sanitised (name/length
limits, control-char stripping) so an untrusted server can't inject into the prompt.
Tool hints map to the trust ladder: destructive tools always confirm, read-only
tools are unprompted, everything else goes through the usual
[trust](security-and-permissions.md) flow — grant standing approval with
`veles trust set` if you don't want to be asked each time.

## Failure handling

A server that fails to connect — a missing `command`, a bad `url`, or any invalid
entry — is logged as a warning and skipped. It never blocks startup or the agent.
Re-run `veles mcp list` to see the status and the error.
