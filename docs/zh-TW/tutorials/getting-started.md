# 開始上手

> 🌐 **語言：** **English** · [Русский](../../ru/tutorials/getting-started.md)

在本教學中，你會安裝 Veles、給它一把 API key、建立你的第一個專案，並執行你的第一個 prompt。約需 10 分鐘。完成後你會擁有一個可對話的、可運作的 Veles 專案。

## 先決條件

- **Python 3.13+**（Veles 需要 `>=3.13`）。
- 一把 LLM API key。我們會用 **OpenRouter**（預設 provider）；任何[其他 providers](../reference/providers.md) 也都可以，包括完全本機、不需 key 的那些。

## 1. 安裝

Veles 透過 [uv](https://docs.astral.sh/uv/) 安裝為一個全域的 `veles` 指令：

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

日後要更新：`uv tool install . --reinstall`。

## 2. 給 Veles 一把 API key

從 [openrouter.ai](https://openrouter.ai) 取得一把 key 並 export：

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

你也可以把它存進作業系統的 keychain，這樣就不必每開一個 shell 都重新 export：

```bash
veles secret set OPENROUTER_API_KEY
```

（偏好完全本機、不需 key 的設定？安裝 [Ollama](https://ollama.com)、執行 `ollama pull qwen3:4b-instruct`，並在下方使用 `--provider ollama`。）

## 3. 建立你的第一個專案

一個 Veles 專案就只是一個帶有 `.veles/` 狀態資料夾的目錄。建立一個：

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

這會建立 `AGENTS.md`（你的專案 context）、`sources/` 與 `wiki/`（預設的 [LLM-Wiki layout](../explanation/layout-packs-and-llm-wiki.md)），以及 `.veles/`（機器狀態）。見 [project layout](../reference/project-layout.md)。

## 4. 執行你的第一個 prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles 會載入你的專案 context、呼叫模型，並印出答案。這個 turn 會被存進專案的記憶。

加上 `--stream` 可看到 token 即時抵達，或加上 `--verbose` 看每個 turn 的進度：

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. 開啟互動式 REPL

若要進行多 turn 對話，開啟 TUI：

```bash
veles tui
```

輸入一則訊息並按 Enter。實用按鍵：`Ctrl+D` 退出、`Shift+Tab` 循環切換 [run modes](../explanation/modes.md)、`/help` 列出 slash 指令。完整清單見 [TUI reference](../reference/tui.md)。

## 6. 看看 Veles 記得什麼

每次執行都會被儲存。列出並搜尋你的 sessions：

```bash
veles sessions list
veles sessions search "three sentences"
```

## 接下來去哪

- **[Building a knowledge base](building-a-knowledge-base.md)** — 把來源匯入 wiki 並針對它們提問。
- **[Configure providers](../how-to/configure-providers.md)** — 切換到 Anthropic、OpenAI、Gemini，或一個完全本機的模型。
- **[Architecture overview](../explanation/architecture.md)** — 了解 Veles 在底層做了什麼。
