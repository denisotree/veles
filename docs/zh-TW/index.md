# Veles 文件

> 🌐 **語言：** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · **繁體中文** · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles 是一個極簡、以本機為優先的 CLI agent 框架。你將它指向一個專案
目錄，它就會維護一份結構化的**專案記憶體**、從你的工作階段中**學習**、
執行任何 LLM 供應商（雲端或本機），並在運作的過程中累積可重複使用的
**skills** 與 **tools**。

本文件遵循 [Diátaxis](https://diataxis.fr/) 模型。請挑選符合你當下
需求的象限。

## 從這裡開始

如果你從未執行過 Veles，請依序完成這兩篇教學：

1. **[快速上手](tutorials/getting-started.md)** — 安裝 Veles、設定 API
   金鑰、建立你的第一個專案，並執行你的第一個提示。
2. **[建立知識庫](tutorials/building-a-knowledge-base.md)** — 將
   來源攝取進 LLM-Wiki、提問，並整併工作階段。

## 教學 — 邊做邊學

- [快速上手](tutorials/getting-started.md)
- [建立知識庫](tutorials/building-a-knowledge-base.md)

## 操作指南 — 完成一項任務

- [設定供應商（雲端與本機）](how-to/configure-providers.md)
- [將不同任務路由到不同模型](how-to/per-task-routing.md)
- [將 Veles 作為 daemon 執行](how-to/run-as-daemon.md)
- [連接 Telegram 頻道](how-to/connect-telegram.md)
- [管理 skills、tools 與 modules](how-to/manage-skills-and-tools.md)
- [使用多個專案與子專案](how-to/multi-project-and-subprojects.md)
- [安全性：信任、autopilot、機密](how-to/security-and-permissions.md)
- [長時間執行的任務：goals、jobs、dreaming、research](how-to/long-running-tasks.md)
- [連接外部 MCP 伺服器](how-to/external-mcp-servers.md)
- [備份與分享專案](how-to/backup-and-share.md)

## 參考 — 查閱資料

- [CLI 指令參考](reference/cli.md)
- [設定（`config.toml`）](reference/configuration.md)
- [環境變數](reference/environment-variables.md)
- [供應商](reference/providers.md)
- [TUI 按鍵綁定與斜線指令](reference/tui.md)
- [專案佈局與狀態](reference/project-layout.md)

## 說明 — 理解設計

- [架構總覽](explanation/architecture.md)
- [專案記憶體與學習迴圈](explanation/project-memory-and-learning-loop.md)
- [skills 與 tools 作為持續累積的能力](explanation/skills-and-tools.md)
- [執行模式](explanation/modes.md)
- [多 agent 協調](explanation/multi-agent-orchestration.md)
- [Layout packs 與 LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [信任與沙箱](explanation/trust-and-sandbox.md)

---

關於產品願景與設計理念，請參閱 `VISION.md`（位於 repo 根目錄）；
完整的實作歷史請見 `MILESTONES.md`。那些文件是面向開發者的
— 本文件則是給**使用** Veles 的人看的。
