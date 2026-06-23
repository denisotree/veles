# Configuration reference

> 🌐 **Languages:** [English](../../en/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · **বাংলা**

Veles দুটি TOML ফাইল ও একগুচ্ছ state ডিরেক্টরি দিয়ে কনফিগার করা হয়। Secrets
(API key, bot token) **কখনোই** এই ফাইলগুলোতে লেখা হয় না — সেগুলো থাকে OS
keychain বা environment variable-এ (দেখুন [environment variables](environment-variables.md))।

## State কোথায় থাকে

| Path | Scope | Contents |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, trust grants, cross-project skills/tools, model cache, locales, registry |
| `<project>/.veles/` | Project-local | `project.toml`, `config.toml`, `memory.db`, project skills/tools, plans, runtime artefacts |
| `<project>/AGENTS.md` | Project | agent-এ inject হওয়া context ফাইল (`CLAUDE.md` / `GEMINI.md`-তে symlink করা) |
| `<project>/wiki/`, `sources/` | Project | ব্যবহারকারীর কন্টেন্ট (ডিফল্ট LLM-Wiki layout) |

`VELES_USER_HOME` `~`-কে redirect করে (ফলে user state `<override>/.veles/`-এ যায়)।
সম্পূর্ণ tree-র জন্য দেখুন [project layout](project-layout.md)।

---

## User config — `~/.veles/config.toml`

first-run wizard এটি লেখে; হাতে সম্পাদনা করা নিরাপদ।

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

| Key | Type | Purpose |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI string-এর locale (`VELES_LOCALE` দিয়ে override করা যায়) |
| `[user] default_provider` | string | কোনোটি না দিলে যে provider ব্যবহৃত হয় |
| `[user] default_model` | string | কোনোটি না দিলে যে model ব্যবহৃত হয় |
| `[user] tui_theme` | string | ডিফল্ট TUI color theme |
| `[permissions] <tool>` | policy | per-tool permission policy (দেখুন [trust ও sandbox](../explanation/trust-and-sandbox.md)) |

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

| Section | Purpose |
|---|---|
| `[provider]` | main agent ও routing cascade-এর base provider/model |
| `[routing.tasks]` | per-task `provider:model` override — দেখুন [per-task routing](../how-to/per-task-routing.md) |
| `[permissions]` | per-tool permission policy (project scope) |
| `[daemon]` | unnamed/"default" daemon-এর bind + autostart |
| `[daemon.<name>]` | একটি named daemon session (নিজস্ব model/provider/host/port/mode) |
| `[channels.<type>]` | unnamed daemon দ্বারা পরিবেশিত একটি channel (যেমন `telegram`) |
| `[daemon.<name>.channels.<type>]` | একটি named daemon session-এ bound channel |
| `[mcp.servers.<name>]` | একটি external MCP server (tool source) |

`[routing.tasks]`-এর task type: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`।

> `AGENTS.md`-এর natural-language routing hint গুলো একটি auto-generated
> `routing.nl.toml`-এ parse করা হয়; স্পষ্ট `[routing.tasks]` entry সবসময় জেতে।
> পুনরায় parse করতে `veles route refresh` চালান। দেখুন [per-task routing](../how-to/per-task-routing.md)।

### `project.toml`

`<project>/.veles/project.toml` অপরিবর্তনীয় project metadata ধারণ করে (`name`,
`created_at`, `schema_version`, `layout`)। সাধারণত আপনি এটি হাতে সম্পাদনা করেন না।

---

## AGENTS.md

project root-এ থাকা project context ফাইল। startup-এ এটি agent-এর
system prompt-এ inject করা হয় এবং `CLAUDE.md` ও `GEMINI.md`-তে symlink করা হয়, যাতে
ওই ডিরেক্টরিতে চালু করা একটি `claude` বা `gemini` CLI একই context তুলে নেয়।

এটি ছোট রাখুন — auxiliary `.md` ফাইলগুলো (যেমন `wiki/INDEX.md`) প্রয়োজনমতো load হয়।
আবশ্যক section-গুলো `veles schema validate` দিয়ে validate করুন। দেখুন
[layout pack ও LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)।
