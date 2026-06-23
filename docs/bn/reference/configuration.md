# কনফিগারেশন রেফারেন্স

> 🌐 **ভাষা:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · **বাংলা** · [Tiếng Việt](../../vi/reference/configuration.md)

Veles দুটি TOML ফাইল এবং কয়েকটি স্টেট ডিরেক্টরি দিয়ে কনফিগার করা হয়। সিক্রেট
(API কী, বট টোকেন) **কখনোই** এই ফাইলগুলোতে লেখা হয় না — সেগুলো OS
keychain বা এনভায়রনমেন্ট ভ্যারিয়েবলে থাকে (দেখুন [এনভায়রনমেন্ট ভ্যারিয়েবল](environment-variables.md))।

## স্টেট কোথায় থাকে

| পাথ | স্কোপ | বিষয়বস্তু |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, trust গ্রান্ট, ক্রস-প্রজেক্ট skills/tools, মডেল ক্যাশ, locales, registry |
| `<project>/.veles/` | Project-local | `project.toml`, `config.toml`, `memory.db`, প্রজেক্ট skills/tools, plans, রানটাইম আর্টিফ্যাক্ট |
| `<project>/AGENTS.md` | Project | এজেন্টে ইনজেক্ট করা কনটেক্সট ফাইল (`CLAUDE.md` / `GEMINI.md`-এ symlink করা) |
| `<project>/wiki/`, `sources/` | Project | ইউজার কন্টেন্ট (ডিফল্ট LLM-Wiki লেআউট) |

`VELES_USER_HOME` `~` রিডাইরেক্ট করে (ফলে ইউজার স্টেট `<override>/.veles/`-এ যায়)।
সম্পূর্ণ ট্রির জন্য দেখুন [প্রজেক্ট লেআউট](project-layout.md)।

---

## ইউজার কনফিগ — `~/.veles/config.toml`

প্রথম-রানের উইজার্ড লেখে; হাতে সম্পাদনা করা নিরাপদ।

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

| কী | টাইপ | উদ্দেশ্য |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI স্ট্রিং-এর জন্য locale (`VELES_LOCALE` দিয়ে ওভাররাইডযোগ্য) |
| `[user] default_provider` | string | কোনোটি না দিলে যে প্রোভাইডার ব্যবহৃত হয় |
| `[user] default_model` | string | কোনোটি না দিলে যে মডেল ব্যবহৃত হয় |
| `[user] tui_theme` | string | ডিফল্ট TUI কালার থিম |
| `[permissions] <tool>` | policy | পার-টুল পারমিশন পলিসি (দেখুন [trust ও sandbox](../explanation/trust-and-sandbox.md)) |

---

## প্রজেক্ট কনফিগ — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter"                               # provider name for the main agent + routing base
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

### সেকশনসমূহ

| সেকশন | উদ্দেশ্য |
|---|---|
| `[provider]` | মূল এজেন্ট এবং রাউটিং ক্যাসকেডের জন্য বেস প্রোভাইডার (`default` = provider name) + মডেল (`model` = model id) |
| `[routing.tasks]` | পার-টাস্ক `provider:model` ওভাররাইড — দেখুন [পার-টাস্ক রাউটিং](../how-to/per-task-routing.md) |
| `[permissions]` | পার-টুল পারমিশন পলিসি (প্রজেক্ট স্কোপ) |
| `[daemon]` | unnamed/"default" ডিমনের bind + autostart |
| `[daemon.<name>]` | একটি নামকৃত ডিমন সেশন (নিজস্ব model/provider/host/port/mode) |
| `[channels.<type>]` | unnamed ডিমন দ্বারা পরিবেশিত একটি চ্যানেল (যেমন `telegram`) |
| `[daemon.<name>.channels.<type>]` | একটি নামকৃত ডিমন সেশনে বাইন্ড করা একটি চ্যানেল |
| `[mcp.servers.<name>]` | একটি এক্সটার্নাল MCP সার্ভার (টুল সোর্স) |

`[routing.tasks]`-এর টাস্ক টাইপ: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`।

> `AGENTS.md`-এর ন্যাচারাল-ল্যাঙ্গুয়েজ রাউটিং হিন্ট একটি অটো-জেনারেটেড
> `routing.nl.toml`-এ পার্স হয়; স্পষ্ট `[routing.tasks]` এন্ট্রি সর্বদা জেতে। পুনরায়
> পার্স করতে `veles route refresh` চালান। দেখুন [পার-টাস্ক রাউটিং](../how-to/per-task-routing.md)।

### `project.toml`

`<project>/.veles/project.toml` অপরিবর্তনীয় প্রজেক্ট মেটাডেটা ধারণ করে (`name`,
`created_at`, `schema_version`, `layout`)। সাধারণত আপনি এটি হাতে সম্পাদনা করবেন না।

---

## AGENTS.md

প্রজেক্ট রুটে থাকা প্রজেক্ট কনটেক্সট ফাইল। এটি স্টার্টআপে এজেন্টের সিস্টেম প্রম্পটে
ইনজেক্ট করা হয় এবং `CLAUDE.md` ও `GEMINI.md`-এ symlink করা হয় যাতে ডিরেক্টরিতে চালু
করা একটি `claude` বা `gemini` CLI একই কনটেক্সট তুলে নেয়।

এটি ছোট রাখুন — সহায়ক `.md` ফাইল (যেমন `wiki/INDEX.md`) প্রয়োজনে লোড হয়।
`veles schema validate` দিয়ে প্রয়োজনীয় সেকশনগুলো যাচাই করুন। দেখুন
[লেআউট প্যাক ও LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)।
