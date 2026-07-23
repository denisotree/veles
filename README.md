# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <b>English</b> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.zh-CN.md">简体中文</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.zh-TW.md">繁體中文</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.ja.md">日本語</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.ko.md">한국어</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.es.md">Español</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.fr.md">Français</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.it.md">Italiano</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.pt-BR.md">Português (BR)</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.pt-PT.md">Português (PT)</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.ru.md">Русский</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.ar.md">العربية</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.hi.md">हिन्दी</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.bn.md">বাংলা</a> ·
  <a href="https://github.com/denisotree/veles/blob/main/README.vi.md">Tiếng Việt</a>
</p>

**A minimal CLI agent framework that gets smarter with every session.**

<p align="center">
  <img src="https://raw.githubusercontent.com/denisotree/veles/main/docs/assets/tui-hero.gif" alt="Veles REPL — ask a question, get an answer grounded in the project's own memory" width="800">
</p>

Unlike chat tools that start fresh every time, Veles maintains **structured project memory** — insights, rules, and curated knowledge that accumulate across sessions and make the agent more useful the longer you use it. How your *content* is organised is pluggable: a Karpathy-style LLM wiki by default, flat notes, or no structure at all for code repos. Built clean: no god-files, no vendor lock-in, no cloud sync.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (just run `veles` with no subcommand)
```

---

## Why Veles?

**Compounding memory** — Every session is distilled by the Curator into per-project memory (insights, behavioral rules, session digests in `.veles/`). The agent recalls relevant facts and past decisions automatically — you stop re-explaining the same context. Memory works under *any* content layout.

**Pluggable content layouts** — `veles init` scaffolds a Karpathy-style LLM wiki by default; `--layout notes` gives a flat notes directory; `--layout bare` adds no structure at all (ideal for code repos). Custom layout packs are a single TOML file in `~/.veles/layouts/`.

**Provider-agnostic routing** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp, or your `claude`/`gemini` CLI subscription. Different task types (planning, compression, insights) can route to different models.

**Skills that accumulate** — Reusable prompt-blocks become agent tools. Promote a skill from a project to user-global and it's available everywhere. Built-in dedup finds near-duplicate skills before they drift.

**Local-first + sandboxed** — No telemetry, no cloud sync. The agent sees only the active project directory. Trust ladder prompts for every sensitive tool call; pre-grant for CI.

**Modular, not monolithic** — Minimal core (memory, agent loop, provider protocol, tool registry). Everything else — daemon, Telegram gateway, deep research, job scheduler — is an optional, loadable module.

---

## Quick Start

**Requirements:** Python 3.13+, macOS / Linux (Windows best-effort). Install [uv](https://docs.astral.sh/uv/) first.

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

Open the interactive REPL instead (bare `veles` does the same):

```bash
veles
```

On first run, a setup wizard walks you through your preferred language, LLM provider, API key, default model, colour theme, and whether to initialise a project in the current directory.

---

## Providers

| Provider | Env var | Notes |
|---|---|---|
| **OpenRouter** *(recommended)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — one key, hundreds of models |
| Anthropic | `ANTHROPIC_API_KEY` | Direct API |
| OpenAI | `OPENAI_API_KEY` | Direct API |
| Gemini | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Direct API |
| `claude` CLI | — | Uses your Claude subscription; no API key needed |
| `gemini` CLI | — | Uses your Gemini subscription; no API key needed |
| Ollama | — | Local models, `http://localhost:11434/v1` |
| llamacpp | — | Local models, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | Any OpenAI-compatible endpoint |

Override per-run:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

Store API keys in the OS keychain instead of environment variables:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## Core Workflow

### Pick a content layout

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

The agent's own memory (insights, rules, session digests in `.veles/`) works identically under every layout. Custom packs are one `layout.toml` in `~/.veles/layouts/<name>/`.

### Build a knowledge base (llm-wiki layout)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="https://raw.githubusercontent.com/denisotree/veles/main/docs/assets/kb-ingest.gif" alt="Veles knowledge base — ingest a source into a wiki page, then ask a question and get an answer that cites it" width="800">
</p>

The Curator runs automatically after sessions. Insight extraction catches phrases like "always prefer X" or "never do Y" and writes them as persistent project insights.

### Deep research

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

Decomposes the question into parallel sub-questions, explores each, and synthesises a structured report.

### Long-running goals

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### Scheduled jobs

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## Memory

Veles' memory is a **structured, self-contained artefact** — separate from your content, versioned per project under `.veles/`. It is a complete retrieval system on its own: **no external graph database, vector service, or plugin is required** — everything below ships in the core.

```
.veles/
├── memory.db                 SQLite: the source of truth
│   ├── insights              distilled facts, each with a confidence score
│   ├── rules                 behavioural rules the agent follows (do/don't/format/preference)
│   ├── sessions / turns      full conversation history (FTS-indexed)
│   ├── project_tree          cached file/dir map + semantic tags (for "which files to read")
│   ├── tools / skills        registries + per-use telemetry (success rate, latency)
│   └── embeddings_blob       vectors for semantic recall
└── memory/
    ├── LOG.md                append-only ops journal
    ├── insights/<slug>.md    human-readable views (regenerable from the DB)
    ├── sessions/<id>.md      compaction summaries
    └── proposals/<slug>.md   subproject suggestions
```

**How recall works.** On every turn Veles pulls the few most relevant items into context — no dump, no manual search:

1. **Full-text search** (SQLite FTS5, BM25) over insights, turns, and the wiki.
2. **Semantic search** — a 3-tier embedding backend (numpy → pure-Python, auto-detected) surfaces items that mean the same thing without sharing keywords. This is why a knowledge graph adds nothing here: *semantic relatedness is already covered by the vectors.*
3. **Reranking** blends **relevance + recency + confidence** so curated knowledge leads, fresh facts beat stale ones, and low-trust inferences sink (the lowest are dropped before they reach the prompt).

**Why no graph plugin.** A code/knowledge graph indexes *content structure*; Veles memory stores *learned experience* (insights, decisions, telemetry) with confidence and recency built in. The recall block is small and bounded, and semantic links are handled by embeddings — so the full learning-loop works out of the box. (You can still register an external graph as an [external MCP server](docs/en/how-to/external-mcp-servers.md) if you want structural code queries, but nothing in the memory loop depends on it.)

Memory works under **any** content layout — wiki, notes, or bare.

---

## Model Routing (Ensembles)

Route different task types to different models — set it once and forget it.

**Via CLI:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**Via natural language in `AGENTS.md`:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## Skills and Modules

**Skills** are reusable prompt-blocks (`SKILL.md`) that become agent tools automatically.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**Modules** are Python plugins that can hook into the agent lifecycle (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) and veto tool dispatches.

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## Interactive session (REPL)

```bash
veles                        # new session (bare `veles` launches the interactive REPL)
veles -c                     # continue the most recent session in this project
veles --resume <id>          # resume a specific session
```

<p align="center">
  <img src="https://raw.githubusercontent.com/denisotree/veles/main/docs/assets/tui-tour.gif" alt="Veles REPL — slash inspectors (/status, /context), mode switching, and the command palette" width="800">
</p>

Slash commands surface everything live — `/status`, `/tokens`, `/context`, `/mode`, `/help` — and `Shift+Tab` cycles modes (auto / planning / writing / goal).

| Key | Action |
|---|---|
| `Enter` | Send message |
| `Shift+Enter` | Newline in composer |
| `Ctrl+I` | Toggle tool-activity inspector |
| `Ctrl+R` | Session picker overlay |
| `Ctrl+X Ctrl+E` | Open `$EDITOR` on current draft |
| `Tab` | Slash-command autocomplete |
| `Ctrl+D` | Quit |

Slash commands: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` and more.

---

## Daemon + Telegram

Run Veles as a persistent daemon with an HTTP/WebSocket API. In a fresh project directory, `veles daemon start` walks you through the setup — initialize the project, enable the daemon, and **connect a channel**: first pick a channel *type* (Telegram is the only platform today, but the picker is the seam new channels register on), then fill that channel's fields (bot token, whitelist). No need to open the TUI first.

<p align="center">
  <img src="https://raw.githubusercontent.com/denisotree/veles/main/docs/assets/daemon-setup.gif" alt="veles daemon start — wizard that brings up the daemon and connects a Telegram channel (channel type first, then its token and whitelist)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765 (next free port if taken)
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

Bare `veles daemon` opens a live control panel — a tree of project → daemons → channels. Start, stop, restart, or delete daemons, and add/remove channels (the same channel-type-first flow, key `c`) across every project, all from the keyboard:

<p align="center">
  <img src="https://raw.githubusercontent.com/denisotree/veles/main/docs/assets/daemon-panel.gif" alt="veles daemon — control-panel TUI: a project → daemons → channels tree with start/stop/restart/delete and inline channel management" width="800">
</p>

The same channel wizard is also available standalone (`veles channel add`) on an already-running project.

API endpoints: `POST /v1/runs` to submit a prompt, `WS /v1/runs/{id}/events` to stream the response, `GET /v1/sessions` to list sessions. All except `GET /v1/health` require `Authorization: Bearer <token>` (mint one with `veles daemon token add <name>`).

Each Telegram user gets a persistent session. Use `veles channel list-sessions` / `reset-session` to manage mappings.

---

## Multi-project

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## Trust and Safety

Every sensitive tool call (shell execution, file writes, URL fetches) prompts:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

Pre-grant for CI or extended autonomous runs:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

The agent sees only the active project directory — other projects, symlink escapes, and `..` traversal are blocked.

---

## Export / Import

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## CLI Reference

| Command | Purpose |
|---|---|
| `veles init [name]` | Create a new project |
| `veles run "<prompt>"` | Single-turn agent run |
| `veles` | Interactive REPL (no subcommand) |
| `veles add <file\|url>` | Ingest a source → topical wiki pages (llm-wiki layout) |
| `veles organize` | Reorganize project content per the active layout (propose-then-apply) |
| `veles research "<question>"` | Deep multi-angle research |
| `veles curate` | Distil sessions into project memory (`.veles/`, any layout) |
| `veles sessions {list,show,delete,search}` | Session management |
| `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}` | Skill management |
| `veles tool {list,show,promote,approve}` | Tool management (`approve` gates self-authored tools) |
| `veles module {list,add,remove}` | Plugin management |
| `veles browse {modules,skills}` | Search the curated module / skill registries |
| `veles route {show,set,reset,refresh}` | Model routing |
| `veles schema {validate,edit}` | Validate / edit AGENTS.md |
| `veles self-doc` | Generate project self-documentation |
| `veles layout {sync}` | Layout-pack maintenance |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Long-horizon goals |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Scheduled jobs |
| `veles dream` | Background memory-consolidation cycle |
| `veles project {list,add,remove,switch}` | Multi-project registry |
| `veles subproject {init,list,switch,remove,suggest}` | Child projects |
| `veles trust {list,set,revoke,clear}` | Trust grants |
| `veles autopilot {enable,disable,status}` | Temporary trust bypass |
| `veles secret {set,get,list,delete}` | OS-keychain secrets |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | HTTP/WS daemon |
| `veles channel {list,run,list-sessions,reset-session,add,remove}` | External channel gateway |
| `veles mcp {list,test}` | External MCP servers |
| `veles models <provider>` | List provider models |
| `veles doctor` | Health checks |
| `veles export / import` | Project backup and transfer |

Every command has `--help`.

---

## Documentation

Full documentation — Diátaxis-organized (tutorials · how-to guides · reference · explanation):

- **English:** [`docs/en/index.md`](docs/en/index.md)

Other languages: use the 🌐 switcher at the top of any documentation page.

---

## Contributing

Contributions are very welcome — Veles is **built to be extended**. The core stays small (agent loop + project memory + provider protocol); almost everything else is a pluggable extension point, so adding a capability rarely means touching the core:

- **Provider adapters** (`src/veles/adapters/`) — wire up a new model backend.
- **Skills** — reusable prompt-blocks and tools with `extends:` inheritance, promotable from a project to user-global.
- **Tools** — typed Python the agent writes and reuses, under `<project>/.veles/tools/`.
- **Layout packs** — a single `layout.toml` in `~/.veles/layouts/<name>/` defines a whole content layout.
- **Module hooks** — observability, logging, and policy via `pre_turn` / `post_turn` hooks (`src/veles/core/modules.py`).
- **Channels & MCP servers** — new gateways and external tool sources.
- **Locales** — translations in `src/veles/locales/`.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

The codebase is deliberately decomposed — single responsibility, no god-files. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for conventions and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) before opening a PR. Good first contributions: provider adapters, workflow skills, module hooks, and locale files.

---

## License

Apache 2.0 with patent grant — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
