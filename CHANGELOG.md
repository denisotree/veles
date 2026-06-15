# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/denisotree/veles/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/denisotree/veles/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/denisotree/veles/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/denisotree/veles/releases/tag/v0.1.0
