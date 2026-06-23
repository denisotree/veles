# Veles ডকুমেন্টেশন

> 🌐 **ভাষা:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · **বাংলা** · [Tiếng Việt](../vi/index.md)

Veles একটি minimalist, local-first CLI agent framework। আপনি এটিকে একটি প্রজেক্ট ডিরেক্টরির দিকে নির্দেশ করেন; এটি একটি কাঠামোবদ্ধ **project memory** রাখে, আপনার session থেকে **শেখে**, যেকোনো LLM provider চালায় (cloud বা local), এবং কাজ করতে করতে পুনঃব্যবহারযোগ্য **skill** ও **tool** সঞ্চয় করে।

এই ডকুমেন্টেশন [Diátaxis](https://diataxis.fr/) মডেল অনুসরণ করে। এই মুহূর্তে আপনার যা দরকার তার সঙ্গে মানানসই quadrant বেছে নিন।

## এখান থেকে শুরু করুন

আপনি যদি কখনো Veles না চালিয়ে থাকেন, ক্রমানুসারে দুটি টিউটোরিয়াল করুন:

1. **[Getting started](tutorials/getting-started.md)** — Veles ইনস্টল করুন, একটি API key সেট করুন, আপনার প্রথম প্রজেক্ট তৈরি করুন, এবং প্রথম prompt চালান।
2. **[Building a knowledge base](tutorials/building-a-knowledge-base.md)** — LLM-Wiki-তে source ingest করুন, প্রশ্ন করুন, এবং session একত্রিত করুন।

## Tutorials — করতে করতে শিখুন

- [Getting started](tutorials/getting-started.md)
- [Building a knowledge base](tutorials/building-a-knowledge-base.md)

## How-to গাইড — একটি কাজ সম্পন্ন করুন

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

## Reference — খুঁজে দেখুন

- [CLI command reference](reference/cli.md)
- [Configuration (`config.toml`)](reference/configuration.md)
- [Environment variables](reference/environment-variables.md)
- [Providers](reference/providers.md)
- [TUI keybindings & slash commands](reference/tui.md)
- [Project layout & state](reference/project-layout.md)

## Explanation — ডিজাইন বুঝুন

- [Architecture overview](explanation/architecture.md)
- [Project memory & the learning loop](explanation/project-memory-and-learning-loop.md)
- [Skills & tools as accumulating capability](explanation/skills-and-tools.md)
- [Run modes](explanation/modes.md)
- [Multi-agent orchestration](explanation/multi-agent-orchestration.md)
- [Layout packs & the LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Trust & the sandbox](explanation/trust-and-sandbox.md)

---

product vision এবং design rationale-এর জন্য দেখুন `VISION.md` (repo root-এ); সম্পূর্ণ implementation history-র জন্য দেখুন `MILESTONES.md`। ওগুলো developer-facing — এই ডকুমেন্টেশন Veles **ব্যবহার** করার জন্য।
