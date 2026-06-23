# 快速上手

> 🌐 **Languages:** [English](../../en/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md) · **简体中文**

在本教程中，你会安装 Veles、给它一个 API 密钥、创建你的第一个项目，
并运行你的第一个提示。约需 10 分钟。完成后你将得到一个可以对话的
可用 Veles 项目。

## 前置条件

- **Python 3.13+**（Veles 要求 `>=3.13`）。
- 一个 LLM API 密钥。我们将使用 **OpenRouter**（默认提供商）；任何
  [其他提供商](../reference/providers.md)同样可用，包括完全本地、
  无需密钥的那些。

## 1. 安装

Veles 通过 [uv](https://docs.astral.sh/uv/) 安装为一个全局 `veles` 命令：

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

之后要更新：`uv tool install . --reinstall`。

## 2. 给 Veles 一个 API 密钥

从 [openrouter.ai](https://openrouter.ai) 获取一个密钥并导出它：

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

你也可以把它存储在操作系统的钥匙串中，这样就不必每个 shell 都重新导出：

```bash
veles secret set OPENROUTER_API_KEY
```

（更想要完全本地、无需密钥的设置？安装 [Ollama](https://ollama.com)、
`ollama pull qwen3:4b-instruct`，然后在下面使用 `--provider ollama`。）

## 3. 创建你的第一个项目

一个 Veles 项目就是一个带有 `.veles/` 状态文件夹的目录。创建一个：

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

这会创建 `AGENTS.md`（你的项目上下文）、`sources/` 和 `wiki/`（默认的
[LLM-Wiki 布局](../explanation/layout-packs-and-llm-wiki.md)），以及
`.veles/`（机器状态）。参见[项目布局](../reference/project-layout.md)。

## 4. 运行你的第一个提示

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles 会加载你的项目上下文，调用模型，并打印答案。这个
轮次会被保存到项目的记忆中。

加上 `--stream` 可以看到令牌随到随显，或加上 `--verbose` 看每轮的进度：

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. 打开交互式 REPL

要进行多轮对话，打开 TUI：

```bash
veles tui
```

输入一条消息并按 Enter。常用按键：`Ctrl+D` 退出，`Shift+Tab`
循环切换[运行模式](../explanation/modes.md)，`/help` 列出斜杠命令。完整
列表见 [TUI 参考](../reference/tui.md)。

## 6. 查看 Veles 记住了什么

每次运行都会被保存。列出并搜索你的会话：

```bash
veles sessions list
veles sessions search "three sentences"
```

## 接下来去哪里

- **[构建知识库](building-a-knowledge-base.md)** — 把来源资料
  摄入 wiki 并就它们提问。
- **[配置提供商](../how-to/configure-providers.md)** — 切换到
  Anthropic、OpenAI、Gemini，或一个完全本地的模型。
- **[架构概览](../explanation/architecture.md)** — 理解 Veles
  在幕后做了什么。
