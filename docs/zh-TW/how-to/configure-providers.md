# 如何設定供應商

> 🌐 **語言：** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · **繁體中文** · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

讓 Veles 在 OpenRouter、Anthropic、OpenAI、Gemini、本機模型或 CLI 訂閱之間切換。完整供應商清單：[供應商參考](../reference/providers.md)。

## 為每個命令挑選供應商

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## 為專案設定預設值

在 `<project>/.veles/config.toml` 中放一個基礎設定：

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

或在 `~/.veles/config.toml` 中設定使用者全域的預設值：

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## 提供 API 金鑰

雲端供應商需要金鑰。將它存進 OS 鑰匙圈一次即可：

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

……或匯出[環境變數](../reference/environment-variables.md)：

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

查詢順序：鑰匙圈（專案範圍）→ 鑰匙圈（預設）→ 環境變數。金鑰**絕不會**寫入設定檔。

## 使用完全本機的模型（無需金鑰）

安裝 [Ollama](https://ollama.com)、拉取一個模型，並讓 Veles 指向它：

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

工具呼叫是根據伺服器所宣告的能力**自動偵測**的。可用 `VELES_LOCAL_TOOLS=1` 強制開啟（或用 `=0` 關閉）。

如果你的伺服器不在預設連接埠上，覆寫端點：

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## 新增你自己的供應商

任何託管的 OpenAI 相容 API，或你自己執行的伺服器，只要在 `~/.veles/providers.toml` 中新增一個項目就能成為供應商——不需寫程式碼。id 就是表名：

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

然後像使用任何內建供應商一樣使用它：

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| 鍵 | 含義 |
|---|---|
| `kind` | `openai-api`（託管的 API）或 `local`（你自己執行的伺服器） |
| `base_url` | OpenAI 相容的端點，以 `/v1` 結尾（或該供應商的等效路徑） |
| `base_url_env` | 設定後會覆寫 `base_url` 的環境變數 |
| `key_env` | 讀取金鑰的環境變數名稱；會先嘗試鑰匙圈 |
| `label`、`tagline` | 精靈中如何顯示它 |
| `tools` | `auto`（預設）、`on` 或 `off`——模型是否獲得工具呼叫 |

與內建 id 同名的項目（`[providers.ollama]`）會改變該供應商的設定——例如它的 `base_url`——但不會改變它的 kind。損壞的檔案只會回報一次，Veles 會繼續使用內建供應商；`veles doctor` 會列出該檔案的問題所在。

常見 API 的起點——**未經 Veles 團隊驗證**，請查閱供應商的文件以取得目前的端點：

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

## 委派給 Claude／ChatGPT／Google 訂閱

如果你已驗證 `claude` CLI，Veles 可以驅動它：

```bash
veles run --provider claude-cli "..."
```

對於 ChatGPT 訂閱，請先安裝 Codex CLI 並登入一次（`codex login`）：

```bash
veles run --provider codex --model gpt-6-luna "..."
veles models codex      # the models your account has
```

對於 Google 訂閱，請先安裝 Antigravity CLI（`agy`）並登入一次，然後指定它的供應商——`antigravity-cli` 模組會在該次執行時從你已連接的登錄庫自行安裝：

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
```

不需 API 金鑰——驗證由 CLI 處理。

## 列出可用的模型

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## 接下來

- [將不同任務路由到不同模型](per-task-routing.md)——壓縮用便宜的模型，規劃用強的模型。
