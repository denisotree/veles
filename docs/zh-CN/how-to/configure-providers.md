# 如何配置提供方

> 🌐 **语言：** [English](../../en/how-to/configure-providers.md) · **简体中文** · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

在 OpenRouter、Anthropic、OpenAI、Gemini、本地模型或 CLI 订阅之间切换 Veles。完整提供方列表：[提供方参考](../reference/providers.md)。

## 按命令选择提供方

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## 为项目设置默认值

在 `<project>/.veles/config.toml` 中放一个基础配置：

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

或在 `~/.veles/config.toml` 中设置一个用户全局默认值：

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## 提供 API key

云端提供方需要 key。把它一次性存到操作系统钥匙串里：

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

……或导出[环境变量](../reference/environment-variables.md)：

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

查找顺序：钥匙串（项目作用域）→ 钥匙串（默认）→ 环境变量。密钥**绝不会**写入配置文件。

## 使用完全本地的模型（无需 key）

安装 [Ollama](https://ollama.com)，拉取一个模型，并让 Veles 指向它：

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

tool 调用是根据服务器所声明的能力**自动检测**的。可用 `VELES_LOCAL_TOOLS=1` 强制开启（或用 `=0` 关闭）。

如果你的服务器不在默认端口上，覆盖端点：

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## 添加你自己的提供方

任何托管的 OpenAI 兼容 API，或你自己运行的服务器，只要在 `~/.veles/providers.toml` 中添加一个条目就能成为提供方——无需写代码。id 就是表名：

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

然后像使用任何内置提供方一样使用它：

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| 键 | 含义 |
|---|---|
| `kind` | `openai-api`（托管的 API）或 `local`（你自己运行的服务器） |
| `base_url` | OpenAI 兼容的端点，以 `/v1` 结尾（或该提供方的等效路径） |
| `base_url_env` | 设置后会覆盖 `base_url` 的环境变量 |
| `key_env` | 读取 key 的环境变量名；会先尝试钥匙串 |
| `label`、`tagline` | 向导中如何显示它 |
| `tools` | `auto`（默认）、`on` 或 `off`——模型是否获得 tool 调用 |

与内置 id 同名的条目（`[providers.ollama]`）会改变该提供方的设置——例如它的 `base_url`——但不会改变它的 kind。损坏的文件只会报告一次，Veles 会继续使用内置提供方；`veles doctor` 会列出该文件的问题所在。

常见 API 的起点——**未经 Veles 团队验证**，请查阅提供方的文档以获取当前的端点：

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## 委托给 Claude / Google 订阅

如果你已认证了 `claude` CLI，Veles 可以驱动它：

```bash
veles run --provider claude-cli "..."
```

对于 Google 订阅，请先安装 Antigravity CLI（`agy`）并登录一次，然后指定它的提供方——`antigravity-cli` 模块会在该次运行时从你已连接的注册表中自行安装：

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
```

无需 API key——认证由 CLI 处理。

## 列出可用模型

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## 下一步

- [将不同的任务路由到不同的模型](per-task-routing.md) — 压缩用便宜的模型，规划用强大的模型。
