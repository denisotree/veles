# 构建知识库

> 🌐 **Languages:** [English](../../en/tutorials/building-a-knowledge-base.md) · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · **简体中文**

在本教程中，你会把一个 Veles 项目变成一个鲜活的知识库：摄入
几份来源资料，让 Veles 撰写 wiki 页面，提出问题，并整合你
学到的内容。这是默认的 **LLM-Wiki** 工作流。约需 15 分钟。

你应该先完成[快速上手](getting-started.md)。

## 思路

一个 Veles 项目有两个内容区：

- `sources/` — 你提供给它的原始、不可变资料（对智能体只读）。
- `wiki/` — 智能体自身的、由 LLM 生成的知识（它唯一会写入
  内容的区域）。

你输入来源资料；Veles 将其提炼为相互链接的 wiki 页面；你用
自然语言查询 wiki。原因参见[布局包与 LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)。

## 1. 摄入一份来源

`veles add` 读取一个文件或 URL，并写出一个总结它的 wiki 页面：

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

每次 `add` 都会在 `wiki/` 下生成一个页面，并把它链接进 wiki 图谱。

## 2. 观察 wiki 的增长

看看写出了什么：

```bash
ls wiki/concepts wiki/entities wiki/sources
```

页面之间相互交叉引用。按需的 `wiki/INDEX.md` 目录维护着一张
地图，供智能体在需要时加载（而不是一次性堆砌的上下文转储）。

## 3. 提出问题

现在用自然语言查询你的知识库：

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles 会搜索 wiki，读取相关页面并作答——其答案根植于你
摄入的内容，而不仅仅是它的训练数据。

要进行交互式的一来一往，在 TUI 中执行相同操作（`veles tui`）。

## 4. 整合会话

随着你工作，对话会不断累积。运行 curator 把它们压缩成
持久的 wiki 页面并提取经验：

```bash
veles curate
```

这会写出 `wiki/sessions/` 页面，并更新项目的洞察和规则。
Veles 也会随着时间自动执行此操作——参见
[项目记忆与学习循环](../explanation/project-memory-and-learning-loop.md)。

## 5. 保持 wiki 的健康

随着时间推移，页面会变得陈旧或成为孤儿。`lint` 操作会找出它们：

```bash
veles run "lint"
```

（`ingest`、`query` 和 `lint` 是随 LLM-Wiki 布局捆绑的技能；你可以
用 `veles run "<operation>"` 调用它们，或让智能体来调用它们。）

## 你构建了什么

一个自组织的知识库：来源资料进，相互链接的 wiki 页面出，可用
自然语言查询，并随着 Veles 的整合而变得更整洁。从这里出发：

- **[管理技能、工具和模块](../how-to/manage-skills-and-tools.md)** —
  教 Veles 可复用的工作流。
- **[作为守护进程运行](../how-to/run-as-daemon.md)** + **[连接 Telegram](../how-to/connect-telegram.md)** —
  从你的手机上与你的知识库对话。
- **[多个项目与子项目](../how-to/multi-project-and-subprojects.md)** —
  扩展到许多个知识库。
