# 布局包与 LLM-Wiki

> 🌐 **Languages:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · **简体中文**

**布局包** 定义了一个项目的 *用户内容* 如何组织 —— 存在哪些目录、智能体可以写入哪些目录，以及它提供哪些操作。默认布局是 **LLM-Wiki**。这是一项内容选项，**而非** Veles 的核心原则。

## 什么是布局包

布局包是一个目录，其中包含一份 `layout.toml` 清单文件（外加可选的技能和模板文件）。该清单声明：

- **可写区** —— 智能体可以写入内容的目录（在每次 `write_file` 时强制执行）。
- **只读区** —— 智能体可读取但绝不修改的资料。
- **操作** —— 具名的工作流，作为包内的技能随包一同发布。
- **脚手架**（`[layout.scaffold]`）—— `veles init` 创建的内容：目录以及一份可选的 `AGENTS.md` 模板（`{name}` 会被替换）。
- **引擎**（`[layout.engines]`）—— 该包激活哪些核心内容机制。如今只有一个引擎：`wiki`。没有它，项目中就不存在 wiki 工具、wiki 召回、INDEX 注入。
- **上下文文件**（`context_file`）—— 一个被注入到智能体稳定系统提示中的文件（LLM-Wiki 使用 `INDEX.md`）。

## 内置包

| 包 | `veles init --layout <name>` 产出的内容 |
|---|---|
| `llm-wiki` *(默认)* | [Karpathy 风格的 LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)：`sources/`（只读）、`wiki/`（智能体可写）、注入到提示中的 `INDEX.md`、`ingest`/`query`/`lint` 技能，以及开启的 wiki 引擎。 |
| `notes` | 一个单一的扁平 `notes/` 目录，供智能体写入。没有任何 wiki 机制。 |
| `bare` | 完全没有内容脚手架 —— 适用于代码仓库和自由形式的工作。在项目根目录内写入是宽松允许的（仍受信任阶梯约束）。 |

## 自定义布局

将一个包放入 `~/.veles/layouts/<name>/layout.toml`（用户全局）或 `<project>/.veles/layouts/<name>/`（项目本地；会遮蔽同名的用户级和内置包），然后传入 `veles init --layout <name>`。内置的 `notes` 是可供复制的最小示例。你也可以在 `AGENTS.md` 中描述约定 —— 布局强制执行各区域，AGENTS.md 引导行为。

## 它 *不是* 什么

布局只管辖 **你的内容**。Veles 自身的项目内存 —— `memory.db` 加上 `.veles/memory/` 产物树（洞见、会话摘要、提案、系统操作日志）—— 属于系统侧，在任何布局下都以相同方式工作。切换布局绝不会触及学习循环、会话或注册表。参阅 [架构](architecture.md) 和 [项目布局](../reference/project-layout.md)。
