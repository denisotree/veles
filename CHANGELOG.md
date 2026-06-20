# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Internal

- Removed the dead `ApprovalScreen` / `TrustScreen` modal overlays
  (`tui/screens/approval_screen.py`) and their tests. The inline `ComposerPrompt`
  (above the Composer) has been the only approval/trust surface since M115; the
  modals were never instantiated. No user-facing change.

## [0.6.4] — 2026-06-20

### Fixed

- **TUI approval prompt: controls no longer scroll off-screen.** When a sensitive
  tool's approval/trust prompt carried a long body (e.g. a big `run_shell` command or
  file-content arguments), the body grew unbounded and pushed the option list and the
  key hint below the visible area, making it impossible to approve or deny. The body is
  now confined to a bounded, scrollable region so the controls stay visible at all times;
  the full text remains reachable by scrolling.

## [0.6.3] — 2026-06-20

### Changed

- **The agent can now edit `AGENTS.md`.** Veles generates the project's `AGENTS.md`
  context file for every layout, but its own `write_file` / `edit_file` tools refused
  to touch it under content layouts (e.g. the default LLM-wiki, whose writable zones
  are `wiki/` + `sources/`). `AGENTS.md` now sits in the always-writable set alongside
  `.veles/`, so the agent maintains it like any other file it generates. Matched by
  exact name, so lookalikes (`AGENTS.md.bak`) and arbitrary root files (`README.md`)
  stay protected; shell writes (`run_shell`) are unchanged.

## [0.6.2] — 2026-06-19

### Changed

- **Verify → escalate now also covers manager-orchestrated runs.** Previously the
  advisor judge-and-escalate pass ran only on direct agent turns; when a run was
  decomposed across manager/worker agents (`--manager`), the synthesised answer
  skipped verification. Now the two compose: with verify enabled, the manager's
  final answer is judged and, on a confident failure, escalated to the stronger
  model — exactly like a direct run. No new flags (opt-in stays `--verify` /
  `[verify] enabled` / `VELES_VERIFY_MODE=1`).

### Internal

- Audit-remediation pass over the 0.4.0–0.6.1 work: removed dead config left by
  the wiki-to-module move, deduplicated two small helpers into shared homes, and
  added the optional vector-search backends (numpy / sqlite-vec) to the dev/test
  matrix so their tests run instead of skipping. No user-facing behaviour change.

## [0.6.1] — 2026-06-19

### Changed

- **Internal:** the LLM-wiki is now a pluggable content-engine module
  (`veles.modules.wiki`) instead of living in the core. The core no longer
  imports or privileges the wiki — it loads only when a project's layout
  enables the wiki engine. No user-facing behaviour change: wiki tools and the
  `llm-wiki` layout work exactly as before. This keeps the core minimal and
  makes room for other content patterns (e.g. an Obsidian connector) as peer
  modules.

## [0.6.0] — 2026-06-18

### Added

- **Human-readable recurring schedules** — cron is no longer the way you set up
  a recurring job. Use `daily@09:00`, `weekdays@18:00`, `weekend@10:00`,
  `weekly:mon,fri@09:00`, `every:2h`, or `once:2026-07-01 18:00`. In chat the
  bot understands plain language ("каждый будний день в 18:00") and translates
  it for you. Times are in the project's timezone — the host's by default, or
  set `[schedule] timezone = "Europe/Moscow"` in config.toml to override; they
  stay correct across daylight-saving changes. (Raw cron still works but is no
  longer documented.)
- **The bot can schedule recurring work from chat** — `job_add` (plus
  `job_list` / `job_remove`) lets it set up a daily digest or a periodic
  monitoring check itself. Because a recurring job runs autonomously with full
  tools, creating one asks for your confirmation first.
- **`memory_query`** — the agent can read back its own recorded insights,
  rules, telemetry, tasks, and session log with a read-only SQL `SELECT`
  (previously it could only write to memory, never read it).

## [0.5.0] — 2026-06-18

### Added

- **Personal tasks with proactive reminders.** The agent can keep a personal
  todo list with optional reminders: `task_add` (with a due time like `+2h`,
  `+1d`, or an ISO timestamp), plus `task_list`, `task_done`, and `task_snooze`.
  When a reminder is due, a running daemon pushes it to the chat the task came
  from — so "remind me to review the PR at 18:00" in Telegram pings *that* chat
  at 18:00. Tasks are distinct from scheduled jobs (which run prompts): a task
  is "remind me about X at time T". Reminders fire only while a daemon is
  running.

### Fixed

- Co-hosted channel turns (the daemon's own Telegram bot) now run the
  `--verify` → escalate pass too. Previously verification only applied to
  external HTTP clients, so the bot most users run didn't get the
  hallucination fallback.

## [0.4.0] — 2026-06-18

### Added

- Scheduled jobs can now **deliver their output to a channel**. A job created
  with `--deliver-to telegram:<chat-id>` (or `deliver_to` via the API) posts its
  result to that chat when it runs — previously the target was recorded but
  never used, so a job only wrote a file under `.veles/jobs/`. Delivery is
  best-effort: a failing channel is logged on the run but never wedges the
  schedule. This is the foundation for proactive reminders and monitoring
  alerts.
- New **`edit_file`** tool for surgical edits: the agent replaces an exact
  string in an existing file instead of rewriting the whole file. The match
  must be unique unless `replace_all` is set, so it can't silently edit the
  wrong occurrence. Useful for correcting scripts, data models, or queries.
- **Verify → escalate** (`veles run --verify`, the `[verify] enabled` daemon
  config, or `VELES_VERIFY_MODE=1`): after a run, the routed advisor model judges
  the answer against the evidence the agent gathered; on a confident failure it
  re-runs the prompt on that stronger model (which may be a `claude`/`gemini` CLI)
  and returns the corrected answer — a fallback for hallucinations on cheap/local
  models. Works for `veles run` and for daemon/channel turns (e.g. Telegram), where
  escalation preserves the chat's session so history isn't lost. Off by default.

## [0.3.2] — 2026-06-15

### Fixed

- `veles daemon` picker: the interactive `tui` session row is now shown only
  while its REPL is actually alive. A clean exit, and especially a crash /
  SIGKILL (which leaves the reused row stuck at `running` with a now-dead pid),
  used to leave a phantom `tui` entry that displayed a nonexistent pid and could
  not be removed (the row is reused and never deleted). Stopped/orphaned tui rows
  are filtered out of the tree; a live REPL still appears beside the daemons.

## [0.3.1] — 2026-06-15

### Fixed

- TUI: the active project (and module registry) is now re-installed inside
  the per-turn worker thread. `veles tui` runs each turn on a Textual
  `run_worker(thread=True)` executor, which — unlike the daemon's
  `asyncio.to_thread` — does not propagate `ContextVar`s, so the agent loop
  saw `current_project() == None`. Tools that hard-require a project
  (`wiki_search`, `wiki_list_pages`, `wiki_read_page`, `memory_save`) then
  failed every call with "no active Veles project"; path-sandboxed tools
  silently fell back to the cwd. Both vars are now captured on the main
  thread and set on the worker thread for the duration of the turn.

## [0.3.0] — 2026-06-15

### Changed

- **Breaking (niche):** routing no longer has *any* hardcoded cloud default —
  the `embedding` task (used by `veles skill dedup`) now resolves only from an
  explicit `[routing.tasks].embedding`, matching the other tasks. `--mode auto`
  still degrades to TF-IDF when unset; `--mode embedding` errors clearly instead
  of silently using `openai:text-embedding-3-small`.

### Fixed

- Daemon event streams now deliver a run's terminal `completed`/`error` event
  before closing: it was appended asynchronously while the run was marked done
  synchronously, so a subscriber streaming a fast run could miss the completion
  event.
- The release workflow now creates the GitHub Release on a version tag
  (previously it only published to PyPI; the Release page was manual).

## [0.2.0] — 2026-06-14

### Added

- Automatic tool-call detection for local providers: `ollama` / `llamacpp` /
  `openai-compat` enable tool calling when the chosen model advertises it
  (Ollama `/api/show` `capabilities`), with no `VELES_LOCAL_TOOLS` flag.
- `graphify_rebuild` project tool, auto-provisioned into `<project>/.veles/tools/`
  when a `graphify` MCP server is configured — resolves the project's provider
  and rebuilds the knowledge graph on the configured backend.
- File-based project/user tools (`<project>/.veles/tools/`, `~/.veles/tools/`)
  are now loaded into the agent's registry at runtime.

### Changed

- **Breaking:** there is no hardcoded default model. The effective model
  resolves from `--model`, the project `[provider] model`, or the user
  `default_model`; when none is configured, veles raises a clear "no model
  configured" error instead of silently using a cloud model. `veles run`,
  `veles job`, and the daemon now resolve provider+model through the same config
  cascade as the TUI.
- **Breaking:** routing has no cloud fallback for chat tasks. Sub-agent tasks
  (compressor, advisor, insights, vision, curator, dream) resolve from
  `[routing.tasks]`, the `[provider]` base, or user defaults; when unconfigured
  the feature degrades (turns off) instead of silently routing to
  `openrouter:claude-*`. `veles route show` displays `(unconfigured)`. The
  `embedding` task keeps its default (a distinct model type).
- `VELES_LOCAL_TOOLS` is now an explicit on/off override rather than the only
  way to enable local tool calling.

### Fixed

- MCP server configuration: documented that `command` and its arguments are
  separate fields (`command = "npx"`, `args = [...]`), not a single string —
  the previous docs example could not launch a stdio server.

## [0.1.0] — 2026-06-12

Initial public release.

### Added

- Agent loop with structured per-project memory: insights, behavioral rules,
  session digests, and a Curator that distills each session into memory.
- Pluggable content layouts: Karpathy-style LLM wiki (default), flat notes,
  bare; custom layout packs via a single TOML file in `~/.veles/layouts/`.
- Provider adapters: OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llama.cpp,
  any OpenAI-compatible endpoint, plus `claude` / `gemini` CLI subprocess
  delegation.
- Per-task model routing (`veles route`): planning, compression, and insight
  extraction can each use a different model.
- Skills and tools that accumulate: project-level and user-level registries,
  promotion between them, inheritance (`extends:`), near-duplicate detection.
- Multi-project and subproject management in a single agent loop.
- Interactive TUI REPL (`veles tui`) with slash-command inspectors.
- HTTP/WS daemon and a Telegram channel gateway.
- MCP client: external MCP servers as tool sources (`veles mcp`).
- Trust ladder and path sandbox; autopilot with bounded standing approval.
- Hierarchical multi-agent orchestration (manager/worker), explicit opt-in.
- Export/import of full projects and templates.
- i18n: English (default) and Russian locales, user-extensible.

[Unreleased]: https://github.com/denisotree/veles/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/denisotree/veles/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/denisotree/veles/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/denisotree/veles/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/denisotree/veles/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/denisotree/veles/releases/tag/v0.1.0
