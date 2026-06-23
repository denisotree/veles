# Veles 文档

> 🌐 **语言：** [English](../en/index.md) · **简体中文** · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles 是一个极简、本地优先的 CLI 智能体框架。你将它指向一个项目
目录；它会维护一份结构化的**项目内存**，从你的会话中**学习**，
运行任意 LLM 提供商（云端或本地），并在工作过程中积累可复用的
**技能**与**工具**。

本文档遵循 [Diátaxis](https://diataxis.fr/) 模型。请选择与你当前需求
相匹配的象限。

## 从这里开始

如果你从未运行过 Veles，请按顺序完成这两篇教程：

1. **[快速上手](tutorials/getting-started.md)** — 安装 Veles、设置 API
   密钥、创建你的第一个项目，并运行你的第一条提示。
2. **[构建知识库](tutorials/building-a-knowledge-base.md)** — 将
   源材料摄取进 LLM-Wiki、提出问题，并整合会话。

## 教程 — 在实践中学习

- [快速上手](tutorials/getting-started.md)
- [构建知识库](tutorials/building-a-knowledge-base.md)

## 操作指南 — 完成一项任务

- [配置提供商（云端与本地）](how-to/configure-providers.md)
- [将不同任务路由到不同模型](how-to/per-task-routing.md)
- [将 Veles 作为守护进程运行](how-to/run-as-daemon.md)
- [接入 Telegram 通道](how-to/connect-telegram.md)
- [管理技能、工具与模块](how-to/manage-skills-and-tools.md)
- [处理多项目与子项目](how-to/multi-project-and-subprojects.md)
- [安全：信任、自动驾驶、密钥](how-to/security-and-permissions.md)
- [长时间运行的任务：目标、作业、做梦、研究](how-to/long-running-tasks.md)
- [接入外部 MCP 服务器](how-to/external-mcp-servers.md)
- [备份与共享项目](how-to/backup-and-share.md)

## 参考 — 查阅它

- [CLI 命令参考](reference/cli.md)
- [配置（`config.toml`）](reference/configuration.md)
- [环境变量](reference/environment-variables.md)
- [提供商](reference/providers.md)
- [TUI 按键绑定与斜杠命令](reference/tui.md)
- [项目布局与状态](reference/project-layout.md)

## 说明 — 理解其设计

- [架构概览](explanation/architecture.md)
- [项目内存与学习循环](explanation/project-memory-and-learning-loop.md)
- [作为累积能力的技能与工具](explanation/skills-and-tools.md)
- [运行模式](explanation/modes.md)
- [多智能体编排](explanation/multi-agent-orchestration.md)
- [布局包与 LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [信任与沙箱](explanation/trust-and-sandbox.md)

---

关于产品愿景与设计理念，请参阅 `VISION.md`（位于仓库根目录）；
关于完整的实现历史，请参阅 `MILESTONES.md`。它们面向开发者
——本文档面向**使用** Veles。
