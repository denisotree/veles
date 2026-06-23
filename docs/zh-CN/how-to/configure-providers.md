# 如何配置提供方

> 🌐 **语言：** [English](../../en/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · **简体中文**

在 OpenRouter、Anthropic、OpenAI、Gemini、本地模型或 CLI 订阅之间切换 Veles。完整的提供方列表见：[提供方参考](../reference/providers.md)。

## 为单条命令选择提供方

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## 为项目设置默认值

在 `<project>/.veles/config.toml` 中设置基础默认值：

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
```

或者在 `~/.veles/config.toml` 中设置用户全局默认值：

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## 提供 API 密钥

云端提供方需要密钥。将其存入操作系统的钥匙串一次即可：

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

……或者导出[环境变量](../reference/environment-variables.md)：

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

查找顺序：钥匙串（项目作用域）→ 钥匙串（默认）→ 环境变量。密钥**绝不会**写入配置文件。

## 使用完全本地的模型（无需密钥）

安装 [Ollama](https://ollama.com)，拉取一个模型，然后让 Veles 指向它：

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

在本地提供方上，工具调用**默认关闭**。在你选好一个支持工具调用的模型后再启用它：

```bash
export VELES_LOCAL_TOOLS=1
```

如果你的服务器不在默认端口上，可覆盖端点：

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## 委托给 Claude / Gemini CLI 订阅

如果你已对 `claude` 或 `gemini` CLI 完成认证，Veles 可以驱动它：

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

无需 API 密钥——认证由 CLI 处理。

## 列出可用模型

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## 下一步

- [将不同任务路由到不同模型](per-task-routing.md)——用便宜的模型做压缩，用强模型做规划。
