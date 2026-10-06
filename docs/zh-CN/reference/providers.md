# 提供商

> 🌐 **语言：** [English](../../en/reference/providers.md) · **简体中文** · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles 与提供方无关。向任何 agent 命令传入 `--provider <id>`，或在配置中设置默认值。模型 ID 使用各提供方自己的命名方式。

## 提供方目录

Veles 已知的每个提供方都是同一份目录中的一个条目，该目录由三个来源构成：

1. **内置**——下表所列，随 Veles 一同发布。
2. **你自己的**——`~/.veles/providers.toml`：添加一个条目，即可接入托管的 OpenAI 兼容 API 或你自己运行的服务器（参见[添加你自己的提供方](../how-to/configure-providers.md#添加你自己的提供方)）。与内置 id 同名的条目会覆盖该提供方的设置（例如它的 `base_url`）。
3. **模块**——由注册表模块贡献的提供方（`antigravity-cli`）。在 `[engine] provider`、某条路由或 `--provider` 中指定它，下次运行时会从你已连接的注册表中安装它，就像已声明的 channel 一样。

`--provider`、`veles models`、设置向导、路由和 `veles doctor` 都读取这份目录，因此来自任何来源的提供方都能在内置提供方可用的所有地方使用。未知的 id 会得到一行错误，并列出现有的提供方；`veles doctor` 还会检查 `~/.veles/providers.toml` 以及你的路由所指定的每个提供方。

| 提供方 | 类型 | API key | 备注 |
|---|---|---|---|
| `openrouter` | 云端网关 | `OPENROUTER_API_KEY` | **默认。** 中转数百个模型；模型 ID 形如 `anthropic/claude-sonnet-4.6` |
| `anthropic` | 云端直连 | `ANTHROPIC_API_KEY` | Claude Messages API，prompt caching |
| `openai` | 云端直连 | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | 云端直连 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI 委托 | —（CLI session） | 委托给以 JSON-stream 模式运行的本地 `claude` CLI |
| `codex` | CLI 委托 | —（CLI session） | 委托给本地 `codex` CLI（ChatGPT 订阅） |
| `ollama` | 本地 | 无 | `OLLAMA_BASE_URL`（默认 `http://localhost:11434/v1`） |
| `llamacpp` | 本地 | 无 | `LLAMACPP_BASE_URL`（默认 `http://localhost:8080/v1`） |
| `openai-compat` | 本地/自定义 | 可选的 `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL`（必填，无默认值） |

`gemini-cli` 已在 1.2.6 中移除——Google 不再向个人账号提供 Gemini CLI。请改用带 API key 的 `gemini`，或 `antigravity-cli` 模块。

默认提供方：`openrouter`。**没有硬编码的默认模型**——通过设置向导、`[engine] model` 或 `--model` 指定一个（否则 agent 会报告 "no model configured"）。除非在 `[routing.tasks]` 中被覆盖，否则按任务的路由会以 `[engine]` 作为基础——参见[按任务路由](../how-to/per-task-routing.md)。

## 本地提供方

`ollama`、`llamacpp` 和 `openai-compat` 无需 API key。用 `veles models <provider>` 列出已安装的模型（对本地提供方始终实时获取）。

**tool 调用是自动检测的**，依据是后端所声明的能力：ollama 会报告每个模型的能力，llama.cpp 服务器则报告其聊天模板的能力。`VELES_LOCAL_TOOLS=1` 强制开启 tool 调用，`=0` 强制关闭；未设置则自动检测。

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

用 `*_BASE_URL` 环境变量覆盖端点（参见[环境变量](environment-variables.md)）。

## CLI 委托（`claude-cli`、`codex`、`antigravity-cli`）

如果你持有 Claude、ChatGPT 或 Google 订阅，Veles 可以以无界面方式运行其 CLI 并充当协调者——无需单独的 API key。`claude-cli` 和 `codex` 是内置的；`antigravity-cli`（即 `agy` CLI）是一个注册表模块，在你指定它时会自行安装。

委托方只充当模型：Veles 的 tools 通过 MCP 桥接触达它，每一次调用都要经过 Veles 的信任阶梯。桥接的配置位于运行中进程的目录 `.veles/tmp/delegate-<pid>/` 中，进程退出时即被删除。`agy` 在你项目之外（`~/.veles/tmp/` 下）的临时工作区中运行，因此项目自己的 `.agents/` 配置不会触及它，并且有一道关卡会拒绝它自带的 shell 和文件 tools。

`codex` 同样在你的项目之外运行（位于 `~/.veles/tmp/` 下），会忽略你的 codex 配置，并关闭它自带的 tools——shell、文件编辑、图像、子智能体、浏览器、网页搜索；Veles 每个进程检查一次这些标志的名称，并拒绝运行已将其所依赖标志重命名的 codex。它的 MCP 服务器通过参数传入，而不是文件。在 `veles run` 中，codex 遵循 Veles tool 协议的可靠性不如 claude：它可能不调用 tool 就回答说无法读取某个文件——请再问一次，或点名该 tool（"use read_file on …"）。

## 多模态状态（视觉 / 语音转文字）

Veles 定义了一个 `VisionAdapter` 和一个 STT 适配器协议（`modules/vision.py`、`modules/stt.py`），外加一个进程级全局注册表，**但没有附带任何具体适配器，且在 daemon 启动时不会注册任何适配器**。因此，目前发送到 channel 的照片或语音消息只会返回 "not configured" 提示，而不会被分析。`vision` 路由任务的存在是为将来接入适配器时备用。参见[连接 Telegram](../how-to/connect-telegram.md#multimodal-limitation)。

## 选择模型

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

如需为不同工作使用不同的模型（压缩用便宜的，规划用强大的），参见[按任务路由](../how-to/per-task-routing.md)。
