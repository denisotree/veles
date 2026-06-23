# 如何設定 providers

> 🌐 **語言：** **English** · [Русский](../../ru/how-to/configure-providers.md)

在 OpenRouter、Anthropic、OpenAI、Gemini、本地模型，或 CLI
訂閱之間切換 Veles。完整的 provider 清單：[providers 參考](../reference/providers.md)。

## 為單一指令挑選 provider

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## 為專案設定預設值

在 `<project>/.veles/config.toml` 中放入一個基底：

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
```

或在 `~/.veles/config.toml` 中設定一個使用者全域的預設值：

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## 提供 API 金鑰

雲端 providers 需要金鑰。把它一次存入作業系統的 keychain：

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

……或匯出該[環境變數](../reference/environment-variables.md)：

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

查找順序：keychain（專案範圍）→ keychain（預設）→ 環境變數。金鑰
**絕不會**被寫入設定檔。

## 使用完全本地的模型（不需金鑰）

安裝 [Ollama](https://ollama.com)，拉取一個模型，然後把 Veles 指向它：

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

在本地 providers 上，tool calling **預設為關閉**。在你挑選了
支援 tool 的模型之後再啟用它：

```bash
export VELES_LOCAL_TOOLS=1
```

若你的伺服器不在預設連接埠上，可覆寫端點：

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## 委派給 Claude / Gemini CLI 訂閱

若你已對 `claude` 或 `gemini` CLI 完成認證，Veles 可以驅動它：

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

不需要 API 金鑰——由該 CLI 處理認證。

## 列出可用的模型

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## 下一步

- [把不同任務路由到不同模型](per-task-routing.md)——用便宜的模型
  做壓縮，用強力的模型做規劃。
