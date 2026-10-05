# Providers

> 🌐 **語言：** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · **繁體中文** · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles 與供應商無關。對任何代理命令傳入 `--provider <id>`，或在設定中指定一個預設值。模型 ID 採用各供應商自有的命名方式。

## 供應商目錄

Veles 所知的每個供應商都是同一份目錄中的一個項目，該目錄由三個來源組成：

1. **內建**——下表所列，隨 Veles 一同發行。
2. **你自己的**——`~/.veles/providers.toml`：新增一個項目，即可接入託管的 OpenAI 相容 API 或你自己執行的伺服器（參見[新增你自己的供應商](../how-to/configure-providers.md#新增你自己的供應商)）。與內建 id 同名的項目會覆寫該供應商的設定（例如它的 `base_url`）。
3. **模組**——由登錄庫模組貢獻的供應商（`antigravity-cli`）。在 `[engine] provider`、某條路由或 `--provider` 中指定它，下次執行時會從你已連接的登錄庫安裝它，就像已宣告的 channel 一樣。

`--provider`、`veles models`、設定精靈、路由與 `veles doctor` 都讀取這份目錄，因此來自任何來源的供應商都能在內建供應商可用的所有地方使用。未知的 id 會得到一行錯誤，並列出現有的供應商；`veles doctor` 還會檢查 `~/.veles/providers.toml` 以及你的路由所指定的每個供應商。

| 供應商 | 類型 | API 金鑰 | 備註 |
|---|---|---|---|
| `openrouter` | 雲端閘道 | `OPENROUTER_API_KEY` | **預設。** 轉發數百個模型；模型 ID 形如 `anthropic/claude-sonnet-4.6` |
| `anthropic` | 雲端直連 | `ANTHROPIC_API_KEY` | Claude Messages API、提示快取 |
| `openai` | 雲端直連 | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | 雲端直連 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI 委派 | —（CLI 工作階段） | 委派給以 JSON-stream 模式執行的本機 `claude` CLI |
| `ollama` | 本機 | 無 | `OLLAMA_BASE_URL`（預設 `http://localhost:11434/v1`） |
| `llamacpp` | 本機 | 無 | `LLAMACPP_BASE_URL`（預設 `http://localhost:8080/v1`） |
| `openai-compat` | 本機／自訂 | 選用的 `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL`（必填，無預設） |

`gemini-cli` 已在 1.2.6 中移除——Google 不再向個人帳號提供 Gemini CLI。請改用帶 API 金鑰的 `gemini`，或 `antigravity-cli` 模組。

預設供應商：`openrouter`。**沒有硬寫死的預設模型**——請透過設定精靈、`[engine] model` 或 `--model` 指定一個（否則代理會回報「no model configured」）。逐任務的路由會繼承 `[engine]` 作為其基礎，除非在 `[routing.tasks]` 中覆寫——參見[逐任務路由](../how-to/per-task-routing.md)。

## 本機供應商

`ollama`、`llamacpp` 與 `openai-compat` 不需 API 金鑰。以 `veles models <provider>` 列出已安裝的模型（本機供應商一律即時取得）。

**工具呼叫是自動偵測的**，依據是後端所宣告的能力：ollama 會回報每個模型的能力，llama.cpp 伺服器則回報其聊天範本的能力。`VELES_LOCAL_TOOLS=1` 強制開啟工具呼叫，`=0` 強制關閉；未設定則自動偵測。

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

以 `*_BASE_URL` 環境變數覆寫端點（參見[環境變數](environment-variables.md)）。

## CLI 委派（`claude-cli`、`antigravity-cli`）

如果你持有 Claude 或 Google 訂閱，Veles 可以以無介面方式執行其 CLI 並充當協調者——不需另一個 API 金鑰。`claude-cli` 是內建的；`antigravity-cli`（即 `agy` CLI）是一個登錄庫模組，在你指定它時會自行安裝。

委派方只充當模型：Veles 的工具透過 MCP 橋接觸及它，每一次呼叫都要經過 Veles 的信任階梯。橋接的設定位於執行中行程的目錄 `.veles/tmp/delegate-<pid>/` 內，行程結束時即被移除。`agy` 在該目錄下的暫存工作區中執行，而不是在你的專案裡，並且有一道關卡會拒絕它自帶的 shell 與檔案工具。

## 多模態狀態（視覺／語音轉文字）

Veles 定義了 `VisionAdapter` 與一個 STT 轉接器協定（`modules/vision.py`、`modules/stt.py`），外加一個行程全域的登錄庫，**但沒有任何具體的轉接器隨附，daemon 啟動時也不會註冊任何一個**。因此目前傳送到 channel 的照片或語音訊息會回傳「not configured」通知，而非被分析。`vision` 路由任務存在於此，供將來接上轉接器時使用。參見[連接 Telegram](../how-to/connect-telegram.md#multimodal-limitation)。

## 挑選模型

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

若要為不同工作使用不同模型（壓縮用便宜的、規劃用強的），參見[逐任務路由](../how-to/per-task-routing.md)。
