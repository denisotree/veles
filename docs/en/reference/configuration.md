# Configuration reference

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

Veles is configured by two TOML files and a set of state directories. Secrets
(API keys, bot tokens) are **never** written to these files — they live in the OS
keychain or environment variables (see [environment variables](environment-variables.md)).

## Where state lives

| Path | Scope | Contents |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, trust grants, cross-project skills/tools, model cache, locales, registry |
| `<project>/.veles/` | Project-local | `project.toml`, `config.toml`, `memory.db`, project skills/tools, plans, runtime artefacts |
| `<project>/AGENTS.md` | Project | The context file injected into the agent (symlinked to `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Project | User content (the default LLM-Wiki layout) |

`VELES_USER_HOME` redirects `~` (so user state lands at `<override>/.veles/`).
See [project layout](project-layout.md) for the full tree.

---

## User config — `~/.veles/config.toml`

Written by the first-run wizard; safe to edit by hand.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Key | Type | Purpose |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale for UI strings (overridable via `VELES_LOCALE`) |
| `[user] default_provider` | string | Provider used when none is given |
| `[user] default_model` | string | Model used when none is given |
| `[user] tui_theme` | string | Default TUI color theme |
| `[permissions] <tool>` | policy | Per-tool permission policy (see [trust & sandbox](../explanation/trust-and-sandbox.md)) |

---

## Project config — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                              # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### Sections

| Section | Purpose |
|---|---|
| `[engine]` | Base provider (`provider` = provider name) + model (`model` = model id) for the main agent and the routing cascade |
| `[routing.tasks]` | Per-task `provider:model` overrides — see [per-task routing](../how-to/per-task-routing.md) |
| `[permissions]` | Per-tool permission policy (project scope) |
| `[daemon]` | The unnamed/"default" daemon's bind + autostart |
| `[daemon.<name>]` | A named daemon session (own model/provider/host/port/mode) |
| `[channels.<type>]` | A channel served by the unnamed daemon (e.g. `telegram`) |
| `[daemon.<name>.channels.<type>]` | A channel bound to a named daemon session |
| `[mcp.servers.<name>]` | An external MCP server (tool source) |

Task types for `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> Natural-language routing hints in `AGENTS.md` are parsed into an auto-generated
> `routing.nl.toml`; explicit `[routing.tasks]` entries always win. Run
> `veles route refresh` to re-parse. See [per-task routing](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` holds immutable project metadata (`name`,
`created_at`, `schema_version`, `layout`). You normally don't edit it by hand.

---

## AGENTS.md

The project context file in the project root. It is injected into the agent's
system prompt at startup and symlinked to `CLAUDE.md` and `GEMINI.md` so a
`claude` or `gemini` CLI launched in the directory picks up the same context.

Keep it small — auxiliary `.md` files (e.g. `wiki/INDEX.md`) load on demand.
Validate the required sections with `veles schema validate`. See
[layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
