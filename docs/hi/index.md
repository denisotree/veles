# Veles दस्तावेज़ीकरण

> 🌐 **भाषाएँ:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · **हिन्दी** · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles एक minimalist, local-first CLI एजेंट फ्रेमवर्क है। आप इसे एक प्रोजेक्ट
डायरेक्टरी की ओर इंगित करते हैं; यह एक संरचित **project memory** रखता है, आपके
सत्रों से **सीखता** है, किसी भी LLM प्रोवाइडर (cloud या local) को चलाता है, और काम
करते-करते पुन: उपयोग योग्य **skills** और **tools** जमा करता रहता है।

यह दस्तावेज़ीकरण [Diátaxis](https://diataxis.fr/) मॉडल का अनुसरण करता है। वह
क्वाड्रंट चुनें जो अभी आपकी ज़रूरत से मेल खाता हो।

## यहाँ से शुरू करें

अगर आपने Veles कभी नहीं चलाया है, तो दोनों ट्यूटोरियल क्रम में करें:

1. **[Getting started](tutorials/getting-started.md)** — Veles इंस्टॉल करें, एक API
   key सेट करें, अपना पहला प्रोजेक्ट बनाएँ, और अपना पहला prompt चलाएँ।
2. **[Building a knowledge base](tutorials/building-a-knowledge-base.md)** —
   स्रोतों को LLM-Wiki में ingest करें, सवाल पूछें, और सत्रों को एकीकृत करें।

## Tutorials — करके सीखें

- [Getting started](tutorials/getting-started.md)
- [Building a knowledge base](tutorials/building-a-knowledge-base.md)

## How-to guides — कोई काम पूरा करें

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

## Reference — देखकर पता करें

- [CLI command reference](reference/cli.md)
- [Configuration (`config.toml`)](reference/configuration.md)
- [Environment variables](reference/environment-variables.md)
- [Providers](reference/providers.md)
- [TUI keybindings & slash commands](reference/tui.md)
- [Project layout & state](reference/project-layout.md)

## Explanation — डिज़ाइन को समझें

- [Architecture overview](explanation/architecture.md)
- [Project memory & the learning loop](explanation/project-memory-and-learning-loop.md)
- [Skills & tools as accumulating capability](explanation/skills-and-tools.md)
- [Run modes](explanation/modes.md)
- [Multi-agent orchestration](explanation/multi-agent-orchestration.md)
- [Layout packs & the LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Trust & the sandbox](explanation/trust-and-sandbox.md)

---

प्रोडक्ट विज़न और डिज़ाइन के तर्क के लिए `VISION.md` देखें (repo root में);
पूरे implementation इतिहास के लिए `MILESTONES.md` देखें। वे डेवलपर-केंद्रित हैं
— यह दस्तावेज़ीकरण Veles के **उपयोग** के लिए है।
