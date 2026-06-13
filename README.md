# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

**A minimal CLI agent framework that gets smarter with every session.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles TUI — ask a question, get an answer grounded in the project's own memory" width="800">
</p>

Unlike chat tools that start fresh every time, Veles maintains **structured project memory** — insights, rules, and curated knowledge that accumulate across sessions and make the agent more useful the longer you use it. How your *content* is organised is pluggable: a Karpathy-style LLM wiki by default, flat notes, or no structure at all for code repos. Built clean: no god-files, no vendor lock-in, no cloud sync.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles tui   # interactive REPL
```

---

## Why Veles?

**Compounding memory** — Every session is distilled by the Curator into per-project memory (insights, behavioral rules, session digests in `.veles/`). The agent recalls relevant facts and past decisions automatically — you stop re-explaining the same context. Memory works under *any* content layout.

**Pluggable content layouts** — `veles init` scaffolds a Karpathy-style LLM wiki by default; `--layout notes` gives a flat notes directory; `--layout bare` adds no structure at all (ideal for code repos). Custom layout packs are a single TOML file in `~/.veles/layouts/`.

**Provider-agnostic routing** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp, or your `claude`/`gemini` CLI subscription. Different task types (planning, compression, insights) can route to different models.

**Skills that accumulate** — Reusable prompt-blocks become agent tools. Promote a skill from a project to user-global and it's available everywhere. Built-in dedup finds near-duplicate skills before they drift.

**Local-first + sandboxed** — No telemetry, no cloud sync. The agent sees only the active project directory. Trust ladder prompts for every sensitive tool call; pre-grant for CI.

**Modular, not monolithic** — Minimal core (memory, agent loop, provider protocol, tool registry). Everything else — TUI, daemon, Telegram gateway, deep research, job scheduler — is an optional, loadable module.

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

Open the interactive TUI instead:

```bash
veles tui
```

On first run, a setup wizard will ask for your preferred language, provider, and project name.

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
veles job add "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

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

## TUI

```bash
veles tui                    # new session
veles tui --resume <id>      # continue a session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="Veles TUI — slash inspectors (/status, /context), mode switching, and the command palette" width="800">
</p>

Slash commands surface everything live — `/status`, `/tokens`, `/context`, `/mode`, `/help` — and `Shift+Tab` cycles modes (auto / planning / writing / goal).

| Key | Action |
|---|---|
| `Enter` | Send message |
| `Shift+Enter` | Newline in composer |
| `Ctrl+I` | Toggle tool-activity inspector |
| `Ctrl+R` | Session picker overlay |
| `Ctrl+G` | Open `$EDITOR` on current draft |
| `Tab` | Slash-command autocomplete |
| `Ctrl+D` | Quit |

Slash commands: `/help` · `/model` · `/save <slug>` · `/load` · `/wiki search <q>` · `/search <q>` · `/history` · `/theme` and more.

---

## Daemon + Telegram

Run Veles as a persistent daemon with an HTTP/WebSocket API:

```bash
veles daemon token add default            # create a bearer token (once)
veles daemon start                        # starts on 127.0.0.1:8765
veles daemon status
veles daemon list                         # daemons across all projects
```

API endpoints: `POST /v1/runs` to submit a prompt, `WS /v1/runs/{id}/events` to stream the response, `GET /v1/sessions` to list sessions. All except `GET /v1/health` require `Authorization: Bearer <token>`.

Connect a Telegram bot:

```bash
export TELEGRAM_BOT_TOKEN=<from @BotFather>
export VELES_DAEMON_URL=http://127.0.0.1:8765
export VELES_DAEMON_TOKEN=vd_...

veles channel run --channel telegram
```

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
| `veles tui` | Interactive TUI REPL |
| `veles add <file\|url>` | Ingest a source → wiki page |
| `veles research "<question>"` | Deep multi-angle research |
| `veles curate` | Consolidate sessions into the wiki |
| `veles sessions {list,show,delete,search}` | Session management |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | Skill management |
| `veles tool {list,show,promote}` | Tool management |
| `veles module {list,add,remove}` | Plugin management |
| `veles route {show,set,reset,refresh}` | Model routing |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Long-horizon goals |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Scheduled jobs |
| `veles dream` | Background memory-consolidation cycle |
| `veles project {list,add,remove,switch}` | Multi-project registry |
| `veles subproject {init,list,switch,remove,suggest}` | Child projects |
| `veles trust {list,set,revoke,clear}` | Trust grants |
| `veles autopilot {enable,disable,status}` | Temporary trust bypass |
| `veles secret {set,get,list,delete}` | OS-keychain secrets |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | HTTP/WS daemon |
| `veles channel {run,list-sessions,reset-session}` | External channel gateway |
| `veles mcp {list,test}` | External MCP servers |
| `veles models <provider>` | List provider models |
| `veles doctor` | Health checks |
| `veles export / import` | Project backup and transfer |

Every command has `--help`.

---

## Documentation

Full documentation — Diátaxis-organized (tutorials · how-to guides · reference · explanation):

- **English:** [`docs/en/index.md`](docs/en/index.md)
- **Русский:** [`docs/ru/index.md`](docs/ru/index.md)

---

## Contributing

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                    # install dev dependencies
pytest                     # run the test suite (3200+ tests)
VELES_LIVE_TESTS=1 pytest -m live   # opt-in live-API smoke tests
```

The codebase is deliberately decomposed — single responsibility throughout, no files exceeding a few hundred lines. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for project conventions before opening a PR.

Contributions welcome: provider adapters, skills for common workflows, module hooks (observability, logging, policy enforcement), and platform packaging.

---

## License

Apache 2.0 with patent grant — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
