# 如何設定 providers

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/configure-providers.md)

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
[provider]
default = "openrouter"                 # provider name
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

本機供應商上工具呼叫**預設為關閉**。在你挑選了具備工具能力的模型後再啟用它：

```bash
export VELES_LOCAL_TOOLS=1
```

如果你的伺服器不在預設連接埠上，覆寫端點：

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## 委派給 Claude／Gemini CLI 訂閱

如果你已驗證 `claude` 或 `gemini` CLI，Veles 可以驅動它：

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
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
