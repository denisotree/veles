# 布局包与 LLM-Wiki

> 🌐 **语言：** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · **简体中文** · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

**布局包** 定义了一个项目的 *用户内容* 如何组织 —— 存在哪些目录、智能体可以写入哪些目录，以及它提供哪些操作。默认是 **`bare`**，除了 `.veles/` 和 `AGENTS.md` 之外不会向你的目录添加任何东西。**LLM-Wiki** 是扩展注册表中的一个选项，**而非** Veles 的核心原则。

## 什么是布局包

布局包是一个目录，其中包含一份 `layout.toml` 清单文件（外加可选的技能和模板文件）。该清单声明：

- **可写区** —— 智能体可以写入内容的目录（在每次 `write_file` 时强制执行）。
- **只读区** —— 智能体可读取但绝不修改的资料。
- **操作** —— 具名的工作流，作为包内的技能随包一同发布。
- **脚手架**（`[layout.scaffold]`）—— `veles init` 创建的内容：目录以及一份可选的 `AGENTS.md` 模板（`{name}` 会被替换）。
- **引擎**（`[layout.engines]`）—— 该包要求提供哪些内容机制。引擎由模块提供（注册表中的 `wiki` 模块提供 `wiki`）。没有它，项目中就不存在 wiki 工具、wiki 召回、INDEX 注入。
- **上下文文件**（`context_file`）—— 一个被注入到智能体稳定系统提示中的文件（LLM-Wiki 使用 `INDEX.md`）。

## 可用的包

| 包 | 来源 | `veles init --layout <name>` 产出的内容 |
|---|---|---|
| `bare` *(默认)* | 内置 | 完全没有内容脚手架 —— 适用于代码仓库和自由形式的工作。在项目根目录内写入是宽松允许的（仍受信任阶梯约束）。 |
| `llm-wiki` | 注册表（`public:official/llm-wiki`，会带上 `wiki` 模块） | [Karpathy 风格的 LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)：`sources/`（按约定只读，不强制）、`wiki/`（智能体可写）、注入到提示中的 `INDEX.md`、`ingest`/`query`/`lint`/`organize`/`structure_design` 技能、开启的 wiki 引擎、`veles add` 和 `/wiki`。由布局声明的行为提示（`templates/behaviour.md`）承载 sources/wiki 的纪律以及迁移/日志补丁规则。 |
| `notes` | 注册表（`public:official/notes`） | 一个单一的扁平 `notes/` 目录，供智能体写入。没有任何 wiki 机制。 |

在终端中，`veles init` 会询问使用哪个包（已安装的以及你的注册表中的）；选择尚未安装的包时会提示安装。`veles registry install llm-wiki` 可提前安装。

## 1.2.3 之前的项目

布局未安装的项目（升级后的 `llm-wiki` 项目，或没有 `layout` 键的项目 —— 它们当时都是 wiki 项目）仍可打开。在终端中，`veles` 和 `veles run` 会在一次确认下提议安装该包（连同它所需的引擎）；在其他场景 —— 守护进程、通道、其他命令 —— Veles 只会打印一次安装命令，并在没有 wiki 的情况下继续工作。`wiki/` 中的任何内容都不会被改动。

## 自定义布局

将一个包放入 `~/.veles/layouts/<name>/layout.toml`（用户全局）或 `<project>/.veles/layouts/<name>/`（项目本地；会遮蔽同名的用户级和内置包），然后传入 `veles init --layout <name>`。注册表中的 `notes` 包是可供复制的最小示例。请求某个引擎、而已安装模块都不提供它的包，会得到同样的安装提示。你也可以在 `AGENTS.md` 中描述约定 —— 布局强制执行各区域，AGENTS.md 引导行为。

## 它 *不是* 什么

布局只管辖 **你的内容**。Veles 自身的项目记忆 —— `memory.db` 加上 `.veles/memory/` 产物树（洞见、会话摘要、提案、系统操作日志）—— 属于系统侧，在任何布局下都以相同方式工作。切换布局绝不会触及学习循环、会话或注册表。参阅 [架构](architecture.md) 和 [项目布局](../reference/project-layout.md)。
