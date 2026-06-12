# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/denisotree/veles/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/denisotree/veles/releases/tag/v0.1.0
