# Architecture overview

> 🌐 **Languages:** **English** · [Русский](../../ru/explanation/architecture.md)

This page explains what Veles *is* and how its parts fit together, so the rest of
the docs make sense. For the authoritative product vision see `VISION.md` in the
repo root.

## The design intent

Veles is deliberately **minimalist and cleanly decomposed** — single-responsibility
modules, no god-files. It is **local-first**: you run it against a directory on
your machine, and it keeps its own structured memory there.

## The five pillars (the core)

Everything in the core serves one of five jobs:

1. **Project memory** — a structured artefact (separate from your content) holding
   the session log, learned rules/insights, a project file map, and skill/tool
   registries with telemetry. See [project memory & the learning loop](project-memory-and-learning-loop.md).
2. **The learning loop** — the curator, insight extractor, and dreaming that keep
   memory fresh and turn experience into reusable rules.
3. **Multi-agent orchestration** — a manager that decomposes a task and spawns
   specialised workers. See [multi-agent orchestration](multi-agent-orchestration.md).
4. **A provider protocol** — one interface over many LLM backends (cloud, local,
   CLI delegation). See [providers](../reference/providers.md).
5. **Minimal tools & skills** — a small bootstrap set that **accumulates** as Veles
   writes its own tools and formalises repeating processes into skills. See
   [skills & tools](skills-and-tools.md).

## Everything else is an optional module

Gateways/channels, the daemon, the scheduler, the TUI, vision/STT — all are
**pluggable** and load only when used. Veles boots with the minimum and expands on
demand, so a simple `veles run` stays simple.

## How a turn flows

```
your prompt
   │
   ▼
context: AGENTS.md (small) + on-demand recall from project memory
   │
   ▼
agent loop  ──►  provider (routed per task)  ──►  tool calls
   │                                               │
   │            (trust ladder gates sensitive tools)
   ▼
response  ──►  saved to memory  ──►  learning triggers (insights, curator)
```

The context file (`AGENTS.md`) is kept small on purpose; auxiliary knowledge
(wiki pages, the project file map, relevant past turns) is pulled in **on demand**
rather than dumped in up front.

## Where state lives

- `<project>/.veles/` — this project's memory, config, local skills/tools.
- `~/.veles/` — user-global config, cross-project skills/tools, caches, trust.
- `<project>/AGENTS.md`, `wiki/`, `sources/` — your content (the LLM-Wiki layout).

See [project layout](../reference/project-layout.md).

## Multi-project in one loop

One agent loop serves many projects. Each project gets its own directory with its
own context and memory; `AGENTS.md` is symlinked to `CLAUDE.md`/`GEMINI.md` so an
external CLI launched there sees the same context. See
[multiple projects](../how-to/multi-project-and-subprojects.md).

## The surfaces

- **CLI** (`veles run`, `veles add`, …) — one-shot and scripted use.
- **TUI** (`veles tui`) — interactive REPL with [run modes](modes.md).
- **Daemon + channels** — headless API, Telegram, scheduled jobs.

All three drive the same core agent loop.
