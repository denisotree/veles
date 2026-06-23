# 架构概览

> 🌐 **Languages:** [English](../../en/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md) · **简体中文**

本页解释 Veles *是什么* 以及它的各个部分如何组合在一起，从而帮助你理解其余文档。关于权威的产品愿景，请参阅仓库根目录中的 `VISION.md`。

## 设计意图

Veles 刻意保持 **极简且清晰解耦** —— 模块职责单一，不存在巨型文件。它是 **本地优先** 的：你针对机器上的某个目录运行它，它会在那里保存自己的结构化内存。

## 五大支柱（核心）

核心中的一切都服务于以下五项工作之一：

1. **项目内存** —— 一份结构化产物（独立于你的内容），保存会话日志、习得的规则/洞见、项目文件映射，以及带遥测数据的技能/工具注册表。参阅 [项目内存与学习循环](project-memory-and-learning-loop.md)。
2. **学习循环** —— 策展器（curator）、洞见提取器以及"做梦"机制，它们让内存保持新鲜，并将经验转化为可复用的规则。
3. **多智能体编排** —— 一个管理者将任务分解并派生专门的工作者。参阅 [多智能体编排](multi-agent-orchestration.md)。
4. **提供方协议** —— 在众多 LLM 后端（云端、本地、CLI 委派）之上的统一接口。参阅 [提供方](../reference/providers.md)。
5. **极简工具与技能** —— 一个小型引导集，随着 Veles 编写自己的工具并将重复流程形式化为技能而 **不断累积**。参阅 [技能与工具](skills-and-tools.md)。

## 其余一切都是可选模块

网关/通道、守护进程、调度器、TUI、视觉/STT —— 全部都是 **可插拔的**，仅在使用时才加载。Veles 以最小配置启动，并按需扩展，因此一次简单的 `veles run` 始终保持简单。

## 一轮对话如何流转

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

上下文文件（`AGENTS.md`）刻意保持精简；辅助知识（wiki 页面、项目文件映射、相关的历史轮次）是 **按需** 拉取的，而非一开始就全部倾倒进来。

## 状态保存在哪里

- `<project>/.veles/` —— 该项目的内存、配置、本地技能/工具。
- `~/.veles/` —— 用户全局配置、跨项目技能/工具、缓存、信任设置。
- `<project>/AGENTS.md`、`wiki/`、`sources/` —— 你的内容（LLM-Wiki 布局）。

参阅 [项目布局](../reference/project-layout.md)。

## 单循环服务多项目

一个智能体循环服务于多个项目。每个项目拥有自己的目录，包含各自的上下文和内存；`AGENTS.md` 通过符号链接指向 `CLAUDE.md`/`GEMINI.md`，因此在该目录下启动的外部 CLI 能看到相同的上下文。参阅 [多项目](../how-to/multi-project-and-subprojects.md)。

## 各类操作界面

- **CLI**（`veles run`、`veles add`、……）—— 一次性和脚本化使用。
- **TUI**（`veles tui`）—— 带 [运行模式](modes.md) 的交互式 REPL。
- **守护进程 + 通道** —— 无头 API、Telegram、定时任务。

这三者都驱动同一个核心智能体循环。
