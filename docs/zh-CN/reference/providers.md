# 提供商

> 🌐 **Languages:** [English](../../en/reference/providers.md) · [Русский](../../ru/reference/providers.md) · **简体中文**

Veles 与提供商无关。可在任意智能体命令上传入 `--provider <name>`，或在配置中
设置默认值。模型 ID 使用提供商自己的命名方式。

| 提供商 | 类型 | API 密钥 | 说明 |
|---|---|---|---|
| `openrouter` | 云端网关 | `OPENROUTER_API_KEY` | **默认。** 中转数百种模型；模型 ID 形如 `anthropic/claude-sonnet-4.6` |
| `anthropic` | 云端直连 | `ANTHROPIC_API_KEY` | Claude Messages API，提示缓存 |
| `openai` | 云端直连 | `OPENAI_API_KEY` | GPT 聊天补全 |
| `gemini` | 云端直连 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | 子进程 | —（CLI 会话） | 委托给 JSON 流模式下的本地 `claude` CLI |
| `gemini-cli` | 子进程 | —（CLI 会话） | 委托给本地 `gemini` CLI |
| `ollama` | 本地 | 无 | `OLLAMA_BASE_URL`（默认 `http://localhost:11434/v1`） |
| `llamacpp` | 本地 | 无 | `LLAMACPP_BASE_URL`（默认 `http://localhost:8080/v1`） |
| `openai-compat` | 本地/自定义 | 无 | `OPENAI_COMPAT_BASE_URL`（必填，无默认值） |

默认值：提供商 `openrouter`，模型 `anthropic/claude-sonnet-4.6`，压缩器
`anthropic/claude-haiku-4.5`。

## 本地提供商

`ollama`、`llamacpp` 和 `openai-compat` 无需 API 密钥。用
`veles models <provider>` 列出已安装的模型（本地提供商始终实时获取）。

**本地提供商默认关闭工具调用**——许多本地模型会发出
格式错误的工具调用。在你选定一个支持工具的模型后再启用它：

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

用 `*_BASE_URL` 环境变量覆盖端点（参见
[环境变量](environment-variables.md)）。

## CLI 委托（`claude-cli`、`gemini-cli`）

如果你持有 Claude 或 Gemini CLI 订阅，Veles 可以在
JSON 流模式下运行该二进制文件并充当协调者——在不使用单独 API 密钥的
情况下让循环保持本地优先。只有在配置了 MCP 桥接时，Veles 工具才能
触及该子进程。

## 多模态状态（视觉 / 语音转文字）

Veles 定义了一个 `VisionAdapter` 和一个 STT 适配器协议（`modules/vision.py`、
`modules/stt.py`），外加一个进程全局注册表，**但未随附任何具体适配器，
且守护进程启动时也不会注册任何适配器**。因此目前发送到
通道的照片或语音消息会返回"未配置"提示，而不会被分析。
`vision` 路由任务的存在是为了在适配器接入后使用。参见
[连接 Telegram](../how-to/connect-telegram.md#multimodal-limitation)。

## 选择模型

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

若要为不同的任务使用不同的模型（压缩用便宜的、规划用强的），
参见[按任务路由](../how-to/per-task-routing.md)。
