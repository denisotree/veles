# Providers

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/providers.md)

Veles 與供應商無關。對任何代理命令傳入 `--provider <name>`，或在設定中指定一個預設值。模型 ID 採用各供應商自有的命名方式。

| 供應商 | 類型 | API 金鑰 | 備註 |
|---|---|---|---|
| `openrouter` | 雲端閘道 | `OPENROUTER_API_KEY` | **預設。** 轉發數百個模型；模型 ID 形如 `anthropic/claude-sonnet-4.6` |
| `anthropic` | 雲端直連 | `ANTHROPIC_API_KEY` | Claude Messages API、提示快取 |
| `openai` | 雲端直連 | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | 雲端直連 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | 子行程 | —（CLI 工作階段） | 委派給以 JSON-stream 模式執行的本機 `claude` CLI |
| `gemini-cli` | 子行程 | —（CLI 工作階段） | 委派給本機 `gemini` CLI |
| `ollama` | 本機 | 無 | `OLLAMA_BASE_URL`（預設 `http://localhost:11434/v1`） |
| `llamacpp` | 本機 | 無 | `LLAMACPP_BASE_URL`（預設 `http://localhost:8080/v1`） |
| `openai-compat` | 本機／自訂 | 無 | `OPENAI_COMPAT_BASE_URL`（必填，無預設） |

預設供應商：`openrouter`。**沒有硬寫死的預設模型**——請透過設定精靈、`[provider] model` 或 `--model` 指定一個（否則代理會回報「no model configured」）。逐任務的路由會繼承 `[provider]` 作為其基礎，除非在 `[routing.tasks]` 中覆寫——參見[逐任務路由](../how-to/per-task-routing.md)。

## 本機供應商

`ollama`、`llamacpp` 與 `openai-compat` 不需 API 金鑰。以 `veles models <provider>` 列出已安裝的模型（本機供應商一律即時取得）。

**本機供應商上工具呼叫預設為關閉**——許多本機模型會發出格式錯誤的工具呼叫。在你挑選了具備工具能力的模型後再啟用它：

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

以 `*_BASE_URL` 環境變數覆寫端點（參見[環境變數](environment-variables.md)）。

## CLI 委派（`claude-cli`、`gemini-cli`）

如果你持有 Claude 或 Gemini CLI 訂閱，Veles 可以用 JSON 串流模式執行該執行檔並充當協調者——讓整個迴圈保持本機優先，且不需另一個 API 金鑰。只有在設定了 MCP 橋接時，Veles 的工具才能觸及該子行程。

## 多模態狀態（視覺／語音轉文字）

Veles 定義了 `VisionAdapter` 與一個 STT 轉接器協定（`modules/vision.py`、`modules/stt.py`），外加一個行程全域的登錄庫，**但沒有任何具體的轉接器隨附，daemon 啟動時也不會註冊任何一個**。因此目前傳送到 channel 的照片或語音訊息會回傳「not configured」通知，而非被分析。`vision` 路由任務存在於此，供將來接上轉接器時使用。參見[連接 Telegram](../how-to/connect-telegram.md#multimodal-limitation)。

## 挑選模型

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

若要為不同工作使用不同模型（壓縮用便宜的、規劃用強的），參見[逐任務路由](../how-to/per-task-routing.md)。
