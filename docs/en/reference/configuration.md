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

[engine.request.openrouter.provider]   # forwarded into the request body as-is
order = ["GMICloud"]                   # pin one backend (see "Pinning a backend" below)
allow_fallbacks = false

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

[vision]                         # how images sent to a channel are read
mode = "model"                   # model (default) | ocr | ocr+model | off
model = "openrouter:z-ai/glm-4.6v"   # optional pin; omit to use [routing.tasks].vision → [engine]
ocr_lang = "rus+eng"             # Tesseract language packs, for the ocr modes

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]
debounce_seconds = 3.0           # how long a burst of messages coalesces into one turn
forward_debounce_seconds = 12.0  # wider window once a forward / album lands

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
| `[engine.request.<provider>]` | Extra keys sent verbatim in that provider's request body — backend pinning, reasoning controls |
| `[routing.tasks]` | Per-task `provider:model` overrides — see [per-task routing](../how-to/per-task-routing.md) |
| `[permissions]` | Per-tool permission policy (project scope) |
| `[vision]` | How incoming images are read: the routed model, Tesseract OCR, both, or nothing |
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

### Pinning a backend, and other request-body keys

`[engine.request.<provider>]` is forwarded into that provider's request body
**verbatim**. Veles does not model the upstream's schema, so anything the
provider accepts works without waiting for Veles to learn about it:

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

The section is keyed by **provider name** (`openrouter`, `anthropic`, `openai`,
`gemini`, `ollama`, `llamacpp`, `openai-compat`) so one project config survives a
backend switch: an OpenRouter `provider` block sent to llama.cpp would be a 400,
so each backend reads only its own subsection. With no section declared, requests
are byte-for-byte what they were before.

**When you need this: reproducible measurement runs.** A relay like OpenRouter
fans one model out across many backends at different quantizations, so two runs
of the same input can differ for reasons that have nothing to do with the input.
`session_id` sticky routing keeps a single conversation on one backend, but says
nothing about *which*.

Pin by `order`, not by `quantizations`. As of 2026-09-18 `z-ai/glm-5.3-flash` has
29 endpoints: 16 at `fp8`, 3 at `fp4`, one at `nvfp4`, **9 that declare no
quantization at all**, and none at `bf16`. So `quantizations = ["fp8"]` still
leaves 16 candidates with context windows from 262144 to 1310720 tokens, while a
single-element `order` plus `allow_fallbacks = false` determines the backend
outright. List a model's endpoints with:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

Keep the pin in the measurement project only — production wants sticky routing,
which preserves availability and fallback.

**Verifying it held.** Each model call records both the intent and the outcome in
`.veles/traces.jsonl`: `request_extra` is what was sent, `upstream_provider` is
the backend that answered. One line per run tells you whether the pin survived:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

More than one line means the run mixed backends. The same records carry
`reasoning_tokens` (how much of the completion budget went to thinking) and
`est_cost_usd` (the upstream's own billed cost, when it reports one).

**Mistakes are loud, on purpose.** A misspelt provider name or a typo in the
section path (`[engine.reqest.…]`) aborts the run with a `ConfigError` naming the
file and the known providers — a pin that silently never reached the wire would
invalidate the measurement it was written for. Keys *inside* a provider's
subsection are not checked by Veles, because the upstream checks them: OpenRouter
answers `400 provider: Unrecognized key: "quantization"` for a bad key and
`404 No endpoints found …` for a value nothing matches.

### How long transcripts are kept

**Nothing is deleted unless you ask for it.** `turn_retention_days` defaults to
`0`, which keeps every conversation turn forever. Set it to a number of days to
put a ceiling on `memory.db`:

```toml
[memory]
turn_retention_days = 90   # 0 (the default) keeps everything
```

With it on, raw conversation turns older than that are deleted; the **insights**
and rules extracted from them are kept forever regardless. The transcript is the
raw material, the insights are what it was read for.

Two conditions must both hold before a transcript is dropped: it is older than
the window, **and** the curator has already swept that session. A session the
curator has not reached is never pruned, whatever its age — otherwise the
transcript would be destroyed before anything was learned from it.

The cost of turning it on: `veles sessions search` only finds text inside the
window. `veles sessions list` still shows older runs, because session rows (id,
title, timestamps) are kept — only the message bodies go. Pruning runs during
`veles dream`, after insight extraction.

### Log rotation

`traces.jsonl` and `events.jsonl` rotate at 50 MB to `<name>.<unix_ts>`, and the
newest **10** rotations are kept — older ones are deleted when the next rotation
happens. Before this they were kept forever.

Nothing needs configuring at ordinary volume: at ~530 bytes per trace record and
~1.1 KB of events per agent turn, a first rotation is years away. The setting
exists because unbounded growth with no policy is a leak whoever inherits the
box has to discover.

### Images

A photo sent to a channel is described before the turn starts, using the model
`[routing.tasks].vision` points at — which, with no explicit route, is your
`[engine]` model. A multimodal engine therefore needs no configuration at all.

`[vision] mode` picks the pipeline:

- `model` (default) — the vision model describes the image.
- `ocr` — Tesseract only. Local, free, no LLM call; good for scans of text.
- `ocr+model` — verbatim text first, then the model's description.
- `off` — nothing is read; the file is still saved and the agent can call
  `image_describe` / `image_ocr` itself if it wants to.

Set `[vision] model` when the engine is text-only. Any vision-capable provider
works, including a local server: `ollama:llava`, `llamacpp:…`, `openai-compat:…`.

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
