# Veles documentation

> 🌐 **Languages:** **English** · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles is a minimalist, local-first CLI agent framework. You point it at a project
directory; it keeps a structured **project memory**, **learns** from your
sessions, runs any LLM provider (cloud or local), and accumulates reusable
**skills** and **tools** as it works.

This documentation follows the [Diátaxis](https://diataxis.fr/) model. Pick the
quadrant that matches what you need right now.

## Start here

If you have never run Veles, do the two tutorials in order:

1. **[Getting started](tutorials/getting-started.md)** — install Veles, set an API
   key, create your first project, and run your first prompt.
2. **[Building a knowledge base](tutorials/building-a-knowledge-base.md)** — ingest
   sources into the LLM-Wiki, ask questions, and consolidate sessions.

## Tutorials — learn by doing

- [Getting started](tutorials/getting-started.md)
- [Building a knowledge base](tutorials/building-a-knowledge-base.md)

## How-to guides — accomplish a task

- [Configure providers (cloud & local)](how-to/configure-providers.md)
- [Route different tasks to different models](how-to/per-task-routing.md)
- [Run Veles as a daemon](how-to/run-as-daemon.md)
- [Connect a Telegram channel](how-to/connect-telegram.md)
- [Manage skills, tools, and modules](how-to/manage-skills-and-tools.md)
- [Work with multiple projects and subprojects](how-to/multi-project-and-subprojects.md)
- [Security: trust, autopilot, secrets](how-to/security-and-permissions.md)
- [Long-running tasks: goals, jobs, dreaming, research](how-to/long-running-tasks.md)
- [Connect external MCP servers](how-to/external-mcp-servers.md)
- [Back up and share a project](how-to/backup-and-share.md)

## Reference — look it up

- [CLI command reference](reference/cli.md)
- [Configuration (`config.toml`)](reference/configuration.md)
- [Environment variables](reference/environment-variables.md)
- [Providers](reference/providers.md)
- [TUI keybindings & slash commands](reference/tui.md)
- [Project layout & state](reference/project-layout.md)

## Explanation — understand the design

- [Architecture overview](explanation/architecture.md)
- [Project memory & the learning loop](explanation/project-memory-and-learning-loop.md)
- [Skills & tools as accumulating capability](explanation/skills-and-tools.md)
- [Run modes](explanation/modes.md)
- [Multi-agent orchestration](explanation/multi-agent-orchestration.md)
- [Layout packs & the LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Trust & the sandbox](explanation/trust-and-sandbox.md)

---

For the product vision and design rationale see `VISION.md` (in the repo root);
for the full implementation history see `MILESTONES.md`. Those are developer-facing
— this documentation is for **using** Veles.
