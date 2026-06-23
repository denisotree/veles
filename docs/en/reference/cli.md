# CLI reference

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/reference/cli.md) · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · [Español](../../es/reference/cli.md) · [Français](../../fr/reference/cli.md) · [Italiano](../../it/reference/cli.md) · [Português (BR)](../../pt-BR/reference/cli.md) · [Português (PT)](../../pt-PT/reference/cli.md) · [Русский](../../ru/reference/cli.md) · [العربية](../../ar/reference/cli.md) · [हिन्दी](../../hi/reference/cli.md) · [বাংলা](../../bn/reference/cli.md) · [Tiếng Việt](../../vi/reference/cli.md)

Every Veles command, subcommand, and flag. Run `veles <command> --help` for the
authoritative, always-current signature — this page mirrors the argument parsers
in `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — skip the first-run setup wizard even if `~/.veles/config.toml`
  is missing (also gated on a TTY and on `VELES_NO_WIZARD=1`).
- With no arguments, `veles` launches the interactive [TUI](tui.md).

Most agent commands accept the [shared agent-loop flags](#shared-agent-loop-flags)
and the [provider names](#provider-names) listed at the bottom.

---

## Project lifecycle

### `veles init [name]`
Create a new Veles project in the current directory (a `.veles/` state directory
+ `AGENTS.md` + the content scaffold of the chosen layout pack).

| Flag | Default | Purpose |
|---|---|---|
| `name` (positional) | cwd basename | Project name |
| `--layout <name>` | `llm-wiki` | Layout pack for the content scaffold (`llm-wiki`, `notes`, `bare`, or a custom pack from `~/.veles/layouts/`) |
| `--force` | off | Recreate `.veles/` even if it already exists |

### `veles schema {validate,edit,fix}`
Validate or edit `AGENTS.md` (the project context file).

- `validate` — check for the required H2 sections.
- `edit` — open `AGENTS.md` in `$EDITOR` (default `vi`), validate on exit.
- `fix` — interactively add missing sections via an LLM wizard.

### `veles self-doc [refresh|show]`
Generate and display project self-documentation (`wiki/self-doc/overview.md`).
Bare `veles self-doc` shows the current page; `refresh` regenerates it.

### `veles doctor`
Run health checks over user-global state and the active project. Works with or
without an active project.

| Flag | Default | Purpose |
|---|---|---|
| `--json` | off | Emit a JSON report |
| `--strict` | off | Exit non-zero on any warning (CI gating) |

### `veles export {full,template} <path>`
Pack the project into a `.tar.gz` bundle. See [Back up and share](../how-to/backup-and-share.md).

- `full <path>` — entire project (`.veles/` + `AGENTS.md`), minus runtime ephemera.
- `template <path>` — sanitised subset (schema + skills + modules + non-session
  wiki pages); strips `memory.db`, `sources/`, `sessions/`, `trust` grants, and
  PII-redacts text.

### `veles import <path>`
Restore a bundle created by `veles export`.

| Flag | Default | Purpose |
|---|---|---|
| `path` (positional) | — | Bundle path (`.tar.gz`) |
| `--into <dir>` | cwd | Target directory |
| `--force` | off | Overwrite an existing `.veles/` at the target |

---

## Running the agent

### `veles run "<prompt>"`
Run a single prompt end-to-end with memory persistence and the curator/learning
triggers. Accepts all [shared agent-loop flags](#shared-agent-loop-flags) plus:

| Flag | Default | Purpose |
|---|---|---|
| `--resume <session_id>` | new session | Continue an existing session |
| `--manager` | off | Decompose via the multi-agent manager (also `VELES_MANAGER_MODE=1`) |
| `--verify` | off | After the run, the routed advisor judges the answer; on a confident failure, re-run on the stronger model (also `VELES_VERIFY_MODE=1`) |
| `--plan` | off | Planning mode: read/search/draft allowed, mutations blocked |
| `--no-agents-md` | off | Don't inject `AGENTS.md` into the system prompt |
| `--no-index` | off | Don't inject `wiki/INDEX.md` |
| `--no-compress` | off | Disable sliding-window context compression |
| `--no-curator` | off | Disable curator triggers for this run |
| `--no-insights` | off | Disable post-run insight extraction |
| `--no-proposer` | off | Disable the subproject proposer auto-trigger |
| `--no-route-refresh` | off | Disable NL routing refresh from `AGENTS.md` |
| `--no-suggest-promote` | off | Disable the auto-promote suggester |
| `--compressor-model <id>` | routed | Override the compression model |
| `--compress-threshold-tokens <n>` | `50000` | History size that triggers compression |

### `veles tui`
Open the interactive REPL. See [TUI reference](tui.md). Accepts the shared
agent-loop flags, `--resume`, the `--no-*` injection/compression flags above, and:

| Flag | Default | Purpose |
|---|---|---|
| `--theme <name>` | config or `everforest` | Color theme (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
Read a source (a local file or `http(s)://` URL) and synthesise it into a wiki
page. Accepts the shared agent-loop flags.

### `veles curate`
Run one curator pass: compact unprocessed sessions into `wiki/sessions/` pages.

| Flag | Default | Purpose |
|---|---|---|
| `--limit <n>` | a small default | Max sessions to process this run |

Plus the shared agent-loop flags.

### `veles research "<question>"`
Deep research: decompose into subquestions → explore the web in parallel →
synthesise a cited report.

| Flag | Default | Purpose |
|---|---|---|
| `--max-subquestions <n>` | `4` | Parallel research angles |

Plus the shared agent-loop flags.

### `veles dream`
Run one background memory-consolidation cycle (insights → skill dedup → promote
suggestions → wiki lint, optionally LLM consolidation).

| Flag | Default | Purpose |
|---|---|---|
| `--include-consolidation` | off | Run the expensive LLM consolidation (needs an API key) |
| `--dry-run` | off | Run all steps but skip `wiki/state` writes |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | Skip individual steps |
| `--consolidation-model <id>` | routed (falls back to `anthropic/claude-haiku-4.5`) | Override the consolidation model |
| `--provider <name>` | routed | Provider for the consolidation sub-agent (omit to use the project's routed provider) |
| `--project-root <path>` | discover | Project override |

---

## Knowledge: skills, tools, modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcommand | Purpose |
|---|---|
| `list` | List skills in the active project (with telemetry) |
| `show <name>` | Print a skill's `SKILL.md` |
| `add <source> [--name N] [--scope project\|user] [-y]` | Install from a git URL or local path |
| `remove <name> [--scope project\|user] [-y]` | Delete an installed skill |
| `promote <name> [--keep-telemetry]` | Copy a project skill to user scope (`~/.veles/skills/`) |
| `demote <name> [-y]` | Copy a user skill into the active project |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Find near-duplicate skills |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | List skills that meet the auto-promote bar |

### `veles tool {list,show,promote}`

| Subcommand | Purpose |
|---|---|
| `list` | List tools catalogued in this project's `memory.db` |
| `show <name>` | Print a tool's manifest + telemetry |
| `promote <name> [-y]` | Move a project tool to `~/.veles/tools/` (cross-project) |

### `veles module {list,show,add,remove}`

| Subcommand | Purpose |
|---|---|
| `list` | List installed modules |
| `show <name>` | Print a module's manifest |
| `add <source> [--name N] [-y]` | Install a module from a git URL or local path |
| `remove <name> [-y]` | Delete an installed module |

### `veles browse {modules,skills} [query]`
Browse the curated registries.

| Flag | Default | Purpose |
|---|---|---|
| `query` (positional) | `""` | Substring filter |
| `--source <url>` | canonical | Override the registry source |
| `--json` | off | Emit JSON |

---

## Sessions & memory

### `veles sessions {list,show,delete,search}`

| Subcommand | Purpose |
|---|---|
| `list [--limit n]` | List recent sessions (default 20) |
| `show <session_id>` | Print a session's full turn history |
| `delete <session_id>` | Delete a session and its turns |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Full-text (FTS5) search over turn content |

---

## Multi-project

### `veles project {list,add,remove,switch}`

| Subcommand | Purpose |
|---|---|
| `list` | List registered projects, most-recent first |
| `add <path> [--slug S]` | Register an existing project directory |
| `remove <slug>` | Unregister a project (files untouched) |
| `switch <slug>` | Print the project's absolute path (use `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcommand | Purpose |
|---|---|
| `init <subdir> [--name N] [--description D]` | Create + register a subproject |
| `list` | List subprojects of the active project |
| `switch <slug>` | Print a subproject's absolute path |
| `remove <slug>` | Unregister a subproject |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Detect thematic clusters and propose subprojects |

---

## Routing & models

### `veles route {show,set,reset,refresh}`
Per-task ensemble routing — which `provider:model` handles each task type
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`). See [per-task routing](../how-to/per-task-routing.md).

| Subcommand | Purpose |
|---|---|
| `show` | Print the resolved routing table for the active project |
| `set <task> <provider:model>` | Pin a task to a spec |
| `reset [task]` | Reset one task (or all) to defaults |
| `refresh [--force]` | Re-parse natural-language routing hints from `AGENTS.md` |

### `veles models <provider>`
List models for a provider. Cloud providers (openrouter/openai/gemini) are cached
24h; local providers are always live.

| Flag | Default | Purpose |
|---|---|---|
| `provider` (positional) | — | One of the [provider names](#provider-names) |
| `--refresh` | off | Bypass the disk cache (cloud only) |
| `--json` | off | Emit `{provider, source, models}` as JSON |

---

## Long-running tasks

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Long-horizon objectives with budgets and checkpoints.

| Subcommand | Purpose |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | List goals |
| `show <id> [--json]` | Show one goal |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | Create a goal |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | Append progress |
| `pause <id>` / `resume <id>` | Pause / resume |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Finish / cancel |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Scheduled agent jobs.

| Subcommand | Purpose |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | Create a job (schedule = cron, `<N><s\|m\|h\|d>`, or ISO timestamp) |
| `list [--json]` / `show <id>` | Inspect jobs |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Lifecycle |
| `history <id> [--limit n]` | Recent runs |
| `tick` | Synchronously run all due jobs once (no daemon needed; takes agent-loop flags) |

---

## Security & access control

### `veles trust {list,set,revoke,clear}`
Persisted grants for sensitive tools (`run_shell`, `write_file`, `fetch_url`, …).
See [security](../how-to/security-and-permissions.md).

| Subcommand | Purpose |
|---|---|
| `list` | Show grants (user + project scope) |
| `set <tool> [--scope project\|user]` | Grant a tool |
| `revoke <tool> [--scope project\|user\|both]` | Remove a grant |
| `clear [--scope project\|user\|all]` | Wipe grants in a scope |

### `veles autopilot {enable,disable,status}`
A time-boxed window where trust-ladder prompts auto-allow.

| Subcommand | Purpose |
|---|---|
| `enable --until <DUR>` | Open a window (`+30m`, `+2h`, `+1d`, or ISO `2026-05-12T18:00:00Z`) |
| `disable` | Close the window now |
| `status` | Report whether autopilot is active |

### `veles secret {set,get,list,delete}`
OS-keychain-backed secrets (API keys, bot tokens).

| Subcommand | Purpose |
|---|---|
| `set <name> [value]` | Store (omit value for interactive / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Look up (env fallback by default) |
| `list` | Show which canonical secrets are configured |
| `delete <name>` | Remove a secret |

---

## Daemon & channels

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Run/control the HTTP+WS daemon. Bare `veles daemon` opens the **daemon picker**
TUI (project → daemons → channels). See [run as a daemon](../how-to/run-as-daemon.md).

| Subcommand | Purpose |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Start a daemon (detaches by default) |
| `stop [--name N]` / `status [--name N]` | Stop / inspect |
| `list` | List daemons across all projects |
| `restart [target] [--name N]` | Stop + respawn on the same host/port |
| `delete <target> [-y]` | Stop + remove from the registry |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Declare a named daemon session |
| `session list [--all]` / `session delete <name>` | Manage named sessions |
| `token add <name>` / `token list` / `token remove <name>` | Bearer-token CRUD |

`start` also accepts the shared agent-loop flags; for the daemon, `--model` /
`--provider` default to the project config and are fixed for the daemon's lifetime.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
External chat gateways (Telegram, …) that talk to a daemon. See
[connect Telegram](../how-to/connect-telegram.md).

| Subcommand | Purpose |
|---|---|
| `list` | List registered channel platforms + session counts |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | Start a gateway in the foreground |
| `list-sessions [--channel C]` | Show `chat_id → session_id` mappings |
| `reset-session <chat_id> [--channel C]` | Forget a mapping (next message starts fresh) |
| `add [--channel C] [--session S]` | Attach a channel to a daemon (wizard; creds → keychain) |
| `remove <channel> [--session S]` | Remove a channel binding |

---

## MCP (external tool servers)

### `veles mcp {list,test}`
Inspect external MCP servers configured under `[mcp.servers.*]`. See
[external MCP servers](../how-to/external-mcp-servers.md).

| Subcommand | Purpose |
|---|---|
| `list [--connect-timeout f]` | Show configured servers, connection status, tool counts |
| `test <server>` | Connect to one server and list its tools |

---

## Shared agent-loop flags

Accepted by `run`, `add`, `tui`, `curate`, `research`, `job tick`, and `daemon
start`:

| Flag | Default | Purpose |
|---|---|---|
| `--model <id>` | resolved from project `[provider]` model → user `default_model` (no hardcoded default) | Model ID |
| `--provider <name>` | `openrouter` | Provider (see below) |
| `--max-tokens-total <n>` | `100000` | Cumulative token budget; `0` disables |
| `--max-iterations <n>` | `30` | Max tool-calling iterations per turn |
| `--stream` | off | Stream the response token-by-token |
| `--verbose` / `-v` | off | Per-turn progress to stderr |
| `--project-root <path>` | discover from cwd | Operate on a project elsewhere |

## Provider names

`openrouter` (default) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Local providers (`ollama`, `llamacpp`, `openai-compat`) need no API key. See the
[providers reference](providers.md) and [configure providers](../how-to/configure-providers.md).
