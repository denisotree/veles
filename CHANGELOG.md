# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.20.0] — 2026-07-07

Supersedes the internal-only 0.10.0 bump; this is the first release cut since 0.9.0.

### Added

- **Project memory is alive in the default REPL (M191).** Every turn injects
  relevant recall and runs the learning loop (insight extraction + curation)
  after the turn — the "never forgets" promise now holds in the main interface,
  not only in batch `veles curate`.
- **Embedding-backed semantic recall (M192).** Insights are recalled by meaning
  through an on-device embedding backend (Ollama), with **no cloud egress** of
  your content; it self-initialises on first use and degrades cleanly to
  keyword search when no local embedder is present.
- **Content-aware ingestion (M203).** `veles add` extracts the distinct topics
  a source is *about* and routes each to a topical wiki page via
  find-or-create-or-patch — no more 1:1 file→page dumps named by filename or
  date. One file can yield several topic pages, and a related source patches the
  existing page instead of duplicating it. `veles add <dir> --recursive` walks a
  whole folder.
- **Human-approval gate for self-authored tools (M199).** Tools the agent writes
  to `.veles/tools/` must be reviewed with `veles tool approve` before they run;
  the approval store lives outside the agent's write sandbox, so a dropped file
  cannot self-approve.
- **Fail-loud config validation (M201).** `veles doctor` and `veles daemon
  start` flag unknown keys in the security-relevant config sections
  (channels / daemon / mcp) instead of silently ignoring a typo.
- **Layout-declared behaviour prompts (M188–M190)** with opt-in writable zones
  (M189); the default llm-wiki layout uses them for migration + log-patch
  behaviour.

### Changed

- **The bare `veles` chat is now the inline prompt_toolkit REPL (M187).** The
  full-screen Textual chat was retired so native terminal selection/copy work;
  the first-run + project setup wizards and the `veles daemon` control panel
  remain interactive Textual TUIs.
- Internal hardening: `veles.core` decoupled from the cli/daemon/channels layers
  with a CI invariant (M194); the REPL was decomposed from a single 2600-line
  module into focused mixins (M195).

### Security

- **Untrusted-content egress gate (M198).** A tool call that would send data to
  a destination named in untrusted content read during the run is gated (hard
  confirm; fail-closed when unattended), and runs *before* the autopilot policy
  so an autopilot window cannot bypass it.
- **Autopilot network egress is journaled (M200)** to the project log.
- **`veles add` hardened against prompt-injection in ingested files.** The
  ingest agent has no network-egress tool; a URL source is fetched by the CLI
  (wrapped as untrusted) and handed to the agent inline, so injected
  instructions inside a source document have no exfiltration channel.
- **Delegated workers cannot exceed their parent's tools** — `delegate`
  intersects the requested toolset with the running agent's scoped tools.

### Fixed

- **Memory recall no longer goes silent (M193).** A broken full-text index
  surfaces via `veles doctor` (repairable with `veles doctor --fix`) instead of
  silently returning nothing; un-distilled recent turns survive until the first
  curation.
- **Semantic recall is no longer dormant** on the first REPL turn or in a
  single-shot `veles run` (the embedding backend self-initialises on first use).
- **`veles daemon` no longer hangs when piped / non-interactive** — it falls
  back to printing the daemon list.
- **Documentation honesty (M196 + docs sweep).** The CLI reference and all 14
  README translations were corrected: accurate first-run wizard steps, complete
  command tables (`tool approve`, `organize`, `browse`, `schema`, `self-doc`,
  `layout`, full channel subcommands), and no phantom environment variables.

## [0.9.0] — 2026-07-04

### Added

- **Veles now answers "how do I do X in Veles" from its own documentation
  (M186).** A framework-global knowledge source lets the agent answer usage
  questions accurately — even on weak or local models — instead of guessing
  from priors. It pairs a live capability skeleton derived straight from the
  CLI (commands, flags, builtin skills and tools, so it can never go stale)
  with curated how-to notes shipped in the package. Relevant docs surface
  automatically in recall when you ask a how-to question, and stay out of
  ordinary coding turns (the retrieval gate keys on curated topics, not
  incidental prose). A new `veles_help` tool provides on-demand deep lookups,
  and a freshness test keeps the notes honest — a note can never reference a
  command, flag, skill, or tool that no longer exists. This is layout-
  independent: it works in every project layout, separate from and
  complementary to the per-project `self-doc` state snapshot.

## [0.8.3] — 2026-06-30

### Fixed

- **Goal mode no longer gets stuck before it can act (M185).** At the CONFIRM
  step the agent only accepted `yes/да/ok/ага` as confirmation, so a natural
  "Продолжи" / "Вперёд" / "continue" reply was read as *edits* and bounced back
  to the interview — the goal could never reach its execute phase. The
  confirmation parser now understands common bilingual "proceed" replies, and
  the "how to confirm" hint is shown the moment the agent asks for confirmation
  (previously it was only emitted on a turn that never happens in the TUI).
- **Planning mode now tells you how to leave it (M185).** When a change was
  blocked in planning mode, the agent invented a non-existent `veles mode
  standard` command. The planning prompt and the block message now point to the
  real action — `/mode writing` (or Shift+Tab) — and the model is told not to
  invent commands.
- **Copy behaviour in the TUI (M185).** A plain drag-select no longer copies on
  its own. Copying the selection is bound to **⌘C** (macOS) and **Ctrl+Shift+C**
  (Linux/Windows) and confirms with "copied to clipboard". Whether ⌘C reaches
  the app depends on the terminal (default iTerm2/Terminal.app keep ⌘C for their
  own Copy); Ctrl+Shift+C works almost everywhere, and `VELES_TUI_MOUSE=0`
  restores native terminal selection + native ⌘C.

## [0.8.2] — 2026-06-30

### Fixed

- **Daemon/channel runs never curated — wiki pages stayed empty (M184).** A
  wiki-llm Telegram diary bot accumulated sessions in `memory.db` but produced
  zero curated wiki pages. The continuous-curator eligibility gate keyed off the
  raw `args.provider`, but `daemon start` defaults `provider=None` (the provider
  flows from project/user config), so the gate returned `False` on every
  post-turn hook and the curator body never ran. `daemon start` now writes the
  resolved provider back into `args.provider` before building the post-turn hook
  (which every channel reuses), and the gate now keys off `has_api_key(provider)`
  instead of `PROVIDER_API_KEY_ENVS` membership — which also makes the curator
  eligible on local providers (`ollama`/`llamacpp`/`openai-compat`) while
  cli-delegate providers stay ineligible. (On a local provider, emitting pages
  also needs `VELES_LOCAL_TOOLS=1` with a tool-capable model, since the curator
  persists via tool calls.)
- **TUI: text selection / copy in the output, and keyboard focus stays on the
  input (M183b).** Two follow-ups to the M182 mouse-on default:
  - The final (sealed) assistant reply could not be selected or copied. It was
    a `Static` carrying a `rich.markdown.Markdown` renderable — which renders
    nicely but whose text Textual's selection cannot extract. Sealed replies are
    now rendered with a Textual `Markdown` *widget*, which composes selectable
    child widgets, so drag-select works on the formatted output. `Ctrl+C` now
    copies the active mouse selection (via the native clipboard — pbcopy/xclip,
    no OSC52 needed) when there is one, falling back to the last-reply copy /
    double-tap-exit otherwise.
  - Keyboard focus no longer switches to the output pane. `ChatLog` is now
    non-focusable (`can_focus = False`), so a mouse click on the output can't
    steal focus from the input line; the Composer is the only focusable widget.
    On iTerm2/macOS, `Option+drag` then `⌘C` also works (native terminal
    select+copy); plain drag uses `Ctrl+C`.

## [0.8.1] — 2026-06-29

### Internal

- **Release workflow is now idempotent on a re-run / re-pushed tag.** The
  `github-release` job ran `gh release create` unconditionally, so re-pushing a
  tag (or re-running the job) failed with "a release with the same tag name
  already exists"; it now updates the existing release in place (`gh release
  edit` + `gh release upload --clobber`). The PyPI publish step gained
  `skip-existing: true` so an already-published version no longer fails the
  re-run.

## [0.8.0] — 2026-06-29

### Changed

- **TUI scrolls with the mouse wheel / trackpad (M182).** Mouse-reporting is now on by default,
  so the wheel / trackpad scrolls the chat directly (scrolling back to the bottom re-arms
  auto-follow). Native drag-select is preserved via the terminal's standard modifier-bypass —
  **Shift+drag** on most terminals, **Option(⌥)+drag** on iTerm2/macOS — then **⌘C** copies;
  **⌘V / Ctrl+V** paste is unchanged. Where a terminal's modifier-bypass is weak (e.g. macOS
  Terminal.app), the in-app Textual selection → OSC52 fallback (`super+c` / `ctrl+shift+c`)
  remains. Set `VELES_TUI_MOUSE=0` to keep mouse-reporting off for pure unmodified terminal
  select (no wheel scrolling).

### Fixed

- **Calling a tool that isn't in the active mode no longer dead-ends in a cryptic
  error (M183).** When the model called a tool absent from the current mode's
  toolset (e.g. `create_plan`, which is planning-only, while in writing/direct
  mode), dispatch let `registry.dispatch` raise `KeyError` and fed the model a
  bare `<error: KeyError: unknown tool 'X'>` — which it couldn't recover from and
  tended to "explain" with a fabricated rationale. `_dispatch` now short-circuits
  on an unknown tool with a recovery-oriented refusal: it distinguishes a tool
  that exists but is gated to another mode from one that doesn't exist at all,
  lists the tools available now, and tells the model to switch modes or proceed
  without it. A `decision="deny", rule="unknown_tool"` event is recorded for
  audit. The tool's handler is never invoked.

### Removed

- **TUI read mode and keyboard scrolling (M182, supersedes M176/M179).** Removed the **Ctrl+O**
  focus toggle and the **PageUp / PageDown / Ctrl+Home / Ctrl+End** scroll bindings; chat
  scrollback is now the mouse wheel / trackpad. **Esc** still returns focus to the input after a
  mouse click lands on the chat pane.

## [0.7.2] — 2026-06-27

### Fixed

- **`veles init` heals a directory copied from another project (M181).** Root cause of the
  "agent answered about the wrong (deleted) project" report: `cp -R old new && cd new && veles
  init` carried `old`'s `.veles/` — its stale default AGENTS.md titled `# old` and its
  `memory.db` — and init silently kept both, so the system prompt named the wrong project and
  recall surfaced the wrong history. Now init **regenerates** an AGENTS.md that is still the
  unmodified scaffold default whose title ≠ the new project name (a customised AGENTS.md is
  always preserved), and **warns** when it completes a `.veles/` that carries a prior project's
  `memory.db` (pointing at `veles curate` / removing the file for a clean slate).

### Added

- **`veles doctor` catches stale/cloned project state (M181).** Two new checks for the same
  class of confusion (catch files that pre-date the init fix or were copied in after init):
  `agents_md_identity` warns when AGENTS.md is still the unmodified scaffold default but its
  `# ` title names a *different* project; `registry_paths` warns about project-registry entries
  whose directory no longer exists, with a `veles project remove <slug>` fix hint.

## [0.7.1] — 2026-06-27

### Added

- **TUI read mode (M179).** Switch keyboard focus from the input field into the output pane
  and navigate it with the arrow keys. **Ctrl+O** toggles focus between the input and the
  output (the primary, Mac-friendly entry — Mac laptops have no PageUp/Home keys); the focused
  pane shows an accent left edge and auto-follow pauses. Once in the output, **↑/↓** move
  through it; **Esc** returns to the input. PageUp / Ctrl+End still work where those keys
  exist (Ctrl+End also jumps to the bottom and resumes auto-scroll).

### Changed

- **`/wiki` is hidden on non-wiki layouts (M180).** The slash command is now registered only
  when the active layout enables the wiki engine, so it no longer appears in `/help` or
  completion on `bare`/`notes` projects; `/help` and the `/save` hint adapt to the layout.

### Fixed

- **Removed wiki artifacts from core (M180).** `veles schema fix`'s fallback AGENTS.md template
  no longer references the removed `veles ingest`/`query`/`lint` commands or assume the wiki
  directory layout; `subproject_proposer.detect_clusters` is gated on the wiki engine (so
  `veles subproject suggest` no longer tries to build a Wiki on a non-wiki project); the
  TUI `/save` wiki import moved inside its engine-gated branch.

## [0.7.0] — 2026-06-26

### Added

- **`veles organize` — layout-driven project tidy-up (M175).** Reorganizes a project's
  content the way its active layout dictates (cluster wiki pages into
  `concepts`/`entities`/`sources`, repair `[[wikilinks]]` and INDEX, dedup; sort a `notes/`
  tree; a `bare` project has no organize step). **Propose-then-apply:** the default run writes
  a reorganization plan to `.veles/memory/proposals/organize-<ts>.md` and changes nothing;
  `--apply` executes it. Ships as a built-in module (`modules/organize/`), not core. Reorg
  primitives are path-guarded: `move_file` and `wiki_rename_page` (move + back-reference
  repair). Batch onboarding: `veles add <dir> --recursive [--glob PATTERN]` ingests a whole
  directory.
- **TUI chat scrollback (M176).** Scroll the chat to re-read earlier output with
  `PageUp`/`PageDown` and `Ctrl+Home`/`Ctrl+End`. Streaming no longer yanks the view to the
  bottom while you're scrolled up (follow-mode resumes on `End` or a new turn). Opt into
  mouse-wheel scrolling with `VELES_TUI_MOUSE=1` (trades native drag-select for in-app
  selection + OSC52 copy).
- **Cache-hit indicator (M178).** The TUI status bar shows a green `cache <N>` chip with the
  last turn's cache-read tokens, so prompt caching is visible.

### Changed

- **Prompt caching now caches the conversation, not just the system prompt (M178).** A rolling
  `cache_control` breakpoint is placed on the most-recent user message, so each turn reads the
  prior conversation from cache instead of re-sending it at full price (the dominant cost in
  agentic loops). Local backends (ollama/llama.cpp/openai-compat) no longer leak the cache
  sentinel into their prompts and cache off the clean prefix automatically.
- **Context-window meter shows live occupancy (M177).** The `ctx` status chip (and `/context`)
  now render the current request's prompt size against the model's real context window
  (per-model registry: Haiku 200k, Sonnet/Opus 4.6+ and Fable 1M) — it no longer conflated
  cumulative run usage with a hardcoded 200k and could show >100%.

### Fixed

- **Context overflow without compression (M177).** The TUI agent now carries a model-derived
  `hard_ceiling_tokens`, so the emergency-truncation guard runs (parity with the daemon path);
  a long session can't send an over-window request.
- **Non-wiki layouts no longer get wiki machinery (M174).** `veles doctor` stops warning about
  missing `INDEX.md`/`LOG.md`, the subproject proposer no-ops, and TUI `/save` falls back to a
  memory insight — on `bare`/`notes` layouts where the wiki engine is off.

## [0.6.5] — 2026-06-22

### Changed

- **Unified channel-setup wizards (M172).** Connecting a chat channel (Telegram) now
  follows the same flow everywhere — `veles channel add`, the `veles daemon` control
  panel (key `c`), and the project setup wizard inside `veles daemon start`: first pick a
  channel *type* from the platform registry, then fill that channel's fields (token,
  whitelist). The project wizards previously hardcoded a Telegram-specific prompt;
  they're now registry-driven, so adding a channel platform needs zero wizard code.
- **`veles daemon start` connects a channel on existing projects too (M173).** In a fresh
  directory the setup wizard already offers a channel; on an already-initialised project
  with none configured, `daemon start` now asks once and runs the same channel wizard
  before the daemon comes up (interactive only; skipped with `--no-wizard`).

### Fixed

- **`veles daemon start` honours the configured port (M173).** The unnamed daemon ignored
  the `[daemon] host`/`port` written by the setup wizard and always bound `127.0.0.1:8765`.
  It now applies the cascade explicit `--host`/`--port` > config > the default.

### Internal

- Removed the dead `ApprovalScreen` / `TrustScreen` modal overlays
  (`tui/screens/approval_screen.py`) and their tests. The inline `ComposerPrompt`
  (above the Composer) has been the only approval/trust surface since M115; the
  modals were never instantiated. No user-facing change.
- Refreshed the README demo GIFs: the TUI launches with bare `veles`, and the daemon
  flow is shown by two new clips (`veles daemon start` wizard + the `veles daemon`
  control panel), replacing the old `/daemon`-in-TUI clip.

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

[Unreleased]: https://github.com/denisotree/veles/compare/v0.8.1...HEAD
[0.8.1]: https://github.com/denisotree/veles/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/denisotree/veles/compare/v0.7.2...v0.8.0
[0.3.2]: https://github.com/denisotree/veles/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/denisotree/veles/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/denisotree/veles/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/denisotree/veles/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/denisotree/veles/releases/tag/v0.1.0
