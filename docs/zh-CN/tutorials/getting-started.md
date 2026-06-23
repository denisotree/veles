# 快速上手

> 🌐 **语言：** [English](../../en/tutorials/getting-started.md) · **简体中文** · [繁體中文](../../zh-TW/tutorials/getting-started.md) · [日本語](../../ja/tutorials/getting-started.md) · [한국어](../../ko/tutorials/getting-started.md) · [Español](../../es/tutorials/getting-started.md) · [Français](../../fr/tutorials/getting-started.md) · [Italiano](../../it/tutorials/getting-started.md) · [Português (BR)](../../pt-BR/tutorials/getting-started.md) · [Português (PT)](../../pt-PT/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md) · [العربية](../../ar/tutorials/getting-started.md) · [हिन्दी](../../hi/tutorials/getting-started.md) · [বাংলা](../../bn/tutorials/getting-started.md) · [Tiếng Việt](../../vi/tutorials/getting-started.md)

在本教程中，你将安装 Veles、给它一个 API key、创建你的第一个项目，并运行你的第一个 prompt。大约 10 分钟。完成后你将得到一个可以对话的、可用的 Veles 项目。

## 前置条件

- **Python 3.13+**（Veles 要求 `>=3.13`）。
- 一个 LLM API key。我们会使用 **OpenRouter**（默认提供方）；[其他任何提供方](../reference/providers.md)也都可以，包括完全本地、无需 key 的那些。

## 1. 安装

Veles 通过 [uv](https://docs.astral.sh/uv/) 安装为一个全局 `veles` 命令：

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

之后更新：`uv tool upgrade veles-ai`。

## 2. 给 Veles 一个 API key

从 [openrouter.ai](https://openrouter.ai) 获取一个 key 并导出：

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

你也可以把它存到操作系统钥匙串里，这样就不必每开一个 shell 都重新导出：

```bash
veles secret set OPENROUTER_API_KEY
```

（想要完全本地、无需 key 的配置？安装 [Ollama](https://ollama.com)，执行 `ollama pull qwen3:4b-instruct`，然后在下面使用 `--provider ollama`。）

## 3. 创建你的第一个项目

一个 Veles 项目就是一个带有 `.veles/` 状态文件夹的目录。创建一个：

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

这会创建 `AGENTS.md`（你的项目上下文）、`sources/` 和 `wiki/`（默认的 [LLM-Wiki 布局](../explanation/layout-packs-and-llm-wiki.md)），以及 `.veles/`（机器状态）。参见[项目布局](../reference/project-layout.md)。

## 4. 运行你的第一个 prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles 会加载你的项目上下文、调用模型并打印答案。这一回合会被保存到项目的内存中。

加上 `--stream` 可以看到逐 token 抵达的内容，或加上 `--verbose` 查看每回合的进度：

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. 打开交互式 REPL

进行多回合对话时，打开 TUI：

```bash
veles tui
```

输入一条消息并按回车。常用按键：`Ctrl+D` 退出，`Shift+Tab` 切换[运行模式](../explanation/modes.md)，`/help` 列出斜杠命令。完整列表见 [TUI 参考](../reference/tui.md)。

## 6. 查看 Veles 记住了什么

每次运行都会被保存。列出并搜索你的 sessions：

```bash
veles sessions list
veles sessions search "three sentences"
```

## 接下来去哪

- **[构建知识库](building-a-knowledge-base.md)** — 将来源摄取到 wiki 中并对它们提问。
- **[配置提供方](../how-to/configure-providers.md)** — 切换到 Anthropic、OpenAI、Gemini 或完全本地的模型。
- **[架构概览](../explanation/architecture.md)** — 了解 Veles 在底层都做了些什么。
