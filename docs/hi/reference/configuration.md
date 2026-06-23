# Configuration reference

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/reference/configuration.md)

Veles को दो TOML files और state directories के एक सेट से configure किया जाता है।
Secrets (API keys, bot tokens) इन files में **कभी** नहीं लिखे जाते — वे OS keychain
या environment variables में रहते हैं (देखें [environment variables](environment-variables.md))।

## State कहाँ रहता है

| Path | Scope | Contents |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, trust grants, cross-project skills/tools, model cache, locales, registry |
| `<project>/.veles/` | Project-local | `project.toml`, `config.toml`, `memory.db`, project skills/tools, plans, runtime artefacts |
| `<project>/AGENTS.md` | Project | Agent में inject की जाने वाली context file (`CLAUDE.md` / `GEMINI.md` से symlinked) |
| `<project>/wiki/`, `sources/` | Project | User content (default LLM-Wiki layout) |

`VELES_USER_HOME` `~` को redirect करता है (ताकि user state `<override>/.veles/` पर
आए)। पूरे tree के लिए देखें [project layout](project-layout.md)।

---

## User config — `~/.veles/config.toml`

पहली-बार चलने वाले wizard द्वारा लिखा जाता है; हाथ से edit करना सुरक्षित है।

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Key | Type | उद्देश्य |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI strings के लिए locale (`VELES_LOCALE` से overridable) |
| `[user] default_provider` | string | जब कोई न दिया हो तब इस्तेमाल होने वाला provider |
| `[user] default_model` | string | जब कोई न दिया हो तब इस्तेमाल होने वाला model |
| `[user] tui_theme` | string | Default TUI color theme |
| `[permissions] <tool>` | policy | Per-tool permission policy (देखें [trust & sandbox](../explanation/trust-and-sandbox.md)) |

---

## Project config — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base for the main agent + routing

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

| Section | उद्देश्य |
|---|---|
| `[provider]` | मुख्य agent और routing cascade के लिए base provider/model |
| `[routing.tasks]` | Per-task `provider:model` overrides — देखें [per-task routing](../how-to/per-task-routing.md) |
| `[permissions]` | Per-tool permission policy (project scope) |
| `[daemon]` | unnamed/"default" daemon का bind + autostart |
| `[daemon.<name>]` | एक named daemon session (अपना model/provider/host/port/mode) |
| `[channels.<type>]` | unnamed daemon द्वारा served एक channel (जैसे `telegram`) |
| `[daemon.<name>.channels.<type>]` | एक named daemon session से bound एक channel |
| `[mcp.servers.<name>]` | एक external MCP server (tool source) |

`[routing.tasks]` के लिए task types: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`।

> `AGENTS.md` में natural-language routing hints एक auto-generated
> `routing.nl.toml` में पार्स हो जाते हैं; स्पष्ट `[routing.tasks]` entries हमेशा
> जीतती हैं। दोबारा पार्स करने के लिए `veles route refresh` चलाएँ। देखें
> [per-task routing](../how-to/per-task-routing.md)।

### `project.toml`

`<project>/.veles/project.toml` में अपरिवर्तनीय project metadata (`name`,
`created_at`, `schema_version`, `layout`) होता है। आप सामान्यतः इसे हाथ से edit
नहीं करते।

---

## AGENTS.md

Project root में project context file। यह startup पर agent के system prompt में
inject की जाती है और `CLAUDE.md` व `GEMINI.md` से symlinked होती है ताकि directory
में लॉन्च किया गया `claude` या `gemini` CLI वही context उठा ले।

इसे छोटा रखें — auxiliary `.md` files (जैसे `wiki/INDEX.md`) माँग पर load होती हैं।
आवश्यक sections को `veles schema validate` से validate करें। देखें
[layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)।
