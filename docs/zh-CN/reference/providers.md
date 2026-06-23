# 提供商

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/providers.md)

Veles 与提供方无关。向任何 agent 命令传入 `--provider <name>`，或在配置中设置默认值。模型 ID 使用各提供方自己的命名方式。

| 提供方 | 类型 | API key | 备注 |
|---|---|---|---|
| `openrouter` | 云端网关 | `OPENROUTER_API_KEY` | **默认。** 中转数百个模型；模型 ID 形如 `anthropic/claude-sonnet-4.6` |
| `anthropic` | 云端直连 | `ANTHROPIC_API_KEY` | Claude Messages API，prompt caching |
| `openai` | 云端直连 | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | 云端直连 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | 子进程 | —（CLI session） | 委托给以 JSON-stream 模式运行的本地 `claude` CLI |
| `gemini-cli` | 子进程 | —（CLI session） | 委托给本地 `gemini` CLI |
| `ollama` | 本地 | 无 | `OLLAMA_BASE_URL`（默认 `http://localhost:11434/v1`） |
| `llamacpp` | 本地 | 无 | `LLAMACPP_BASE_URL`（默认 `http://localhost:8080/v1`） |
| `openai-compat` | 本地/自定义 | 无 | `OPENAI_COMPAT_BASE_URL`（必填，无默认值） |

默认提供方：`openrouter`。**没有硬编码的默认模型**——通过设置向导、`[provider] model` 或 `--model` 指定一个（否则 agent 会报告 "no model configured"）。除非在 `[routing.tasks]` 中被覆盖，否则按任务的路由会以 `[provider]` 作为基础——参见[按任务路由](../how-to/per-task-routing.md)。

## 本地提供方

`ollama`、`llamacpp` 和 `openai-compat` 无需 API key。用 `veles models <provider>` 列出已安装的模型（对本地提供方始终实时获取）。

**本地提供方上默认关闭 tool 调用**——许多本地模型会发出格式错误的 tool 调用。在选好支持 tool 的模型后再启用：

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

用 `*_BASE_URL` 环境变量覆盖端点（参见[环境变量](environment-variables.md)）。

## CLI 委托（`claude-cli`、`gemini-cli`）

如果你持有 Claude 或 Gemini CLI 订阅，Veles 可以以 JSON 流式模式运行该二进制程序并充当协调者——让循环保持本地优先，无需单独的 API key。只有在配置了 MCP 桥接时，Veles 的 tools 才能触达该子进程。

## 多模态状态（视觉 / 语音转文字）

Veles 定义了一个 `VisionAdapter` 和一个 STT 适配器协议（`modules/vision.py`、`modules/stt.py`），外加一个进程级全局注册表，**但没有附带任何具体适配器，且在 daemon 启动时不会注册任何适配器**。因此，目前发送到 channel 的照片或语音消息只会返回 "not configured" 提示，而不会被分析。`vision` 路由任务的存在是为将来接入适配器时备用。参见[连接 Telegram](../how-to/connect-telegram.md#multimodal-limitation)。

## 选择模型

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

如需为不同工作使用不同的模型（压缩用便宜的，规划用强大的），参见[按任务路由](../how-to/per-task-routing.md)。
