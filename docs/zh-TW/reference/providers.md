# Providers

> 🌐 **語言：** **English** · [Русский](../../ru/reference/providers.md)

Veles 不綁定特定 provider。對任何 agent 指令傳入 `--provider <name>`，或在組態中設定一個預設值。Model ID 採用各 provider 自己的命名方式。

| Provider | Kind | API key | Notes |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **預設。** 轉接數百種模型；model ID 形如 `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API，prompt caching |
| `openai` | Cloud direct | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocess | — (CLI session) | 委派給本機以 JSON-stream 模式執行的 `claude` CLI |
| `gemini-cli` | Subprocess | — (CLI session) | 委派給本機的 `gemini` CLI |
| `ollama` | Local | none | `OLLAMA_BASE_URL`（預設 `http://localhost:11434/v1`） |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL`（預設 `http://localhost:8080/v1`） |
| `openai-compat` | Local/custom | none | `OPENAI_COMPAT_BASE_URL`（必填，無預設） |

預設值：provider 為 `openrouter`、model 為 `anthropic/claude-sonnet-4.6`、compressor 為 `anthropic/claude-haiku-4.5`。

## 本機 providers

`ollama`、`llamacpp` 與 `openai-compat` 都不需要 API key。以 `veles models <provider>` 列出已安裝的模型（本機 providers 永遠是即時查詢）。

**本機 providers 預設關閉 tool calling** — 許多本機模型會發出格式錯誤的 tool call。當你選定一個支援 tool 的模型後再啟用它：

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

以 `*_BASE_URL` 環境變數覆寫端點（見 [environment variables](environment-variables.md)）。

## CLI 委派（`claude-cli`、`gemini-cli`）

如果你持有 Claude 或 Gemini CLI 訂閱，Veles 可以用 JSON-streaming 模式執行該執行檔並擔任協調者 — 在不需要另外 API key 的情況下保持 loop 以本機為先。Veles tools 只有在設定了 MCP bridge 時才能接觸到該 subprocess。

## 多模態狀態（vision / speech-to-text）

Veles 定義了一個 `VisionAdapter` 與一個 STT adapter protocol（`modules/vision.py`、`modules/stt.py`）以及一個 process 全域的註冊表，**但沒有任何具體 adapter 隨附，且 daemon 啟動時也不會註冊任何一個**。因此目前送到某個 channel 的照片或語音訊息會回傳一則「未設定」通知，而非被分析。`vision` routing task 已存在，供 adapter 接上時使用。見 [connect Telegram](../how-to/connect-telegram.md#multimodal-limitation)。

## 選擇模型

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

若要為不同工作使用不同模型（壓縮用便宜的、規劃用強大的），見 [per-task routing](../how-to/per-task-routing.md)。
