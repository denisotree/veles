# 開始上手

> 🌐 **語言：** [English](../../en/tutorials/getting-started.md) · [简体中文](../../zh-CN/tutorials/getting-started.md) · **繁體中文** · [日本語](../../ja/tutorials/getting-started.md) · [한국어](../../ko/tutorials/getting-started.md) · [Español](../../es/tutorials/getting-started.md) · [Français](../../fr/tutorials/getting-started.md) · [Italiano](../../it/tutorials/getting-started.md) · [Português (BR)](../../pt-BR/tutorials/getting-started.md) · [Português (PT)](../../pt-PT/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md) · [العربية](../../ar/tutorials/getting-started.md) · [हिन्दी](../../hi/tutorials/getting-started.md) · [বাংলা](../../bn/tutorials/getting-started.md) · [Tiếng Việt](../../vi/tutorials/getting-started.md)

在本教學中，你會安裝 Veles、提供一個 API 金鑰、建立你的第一個專案，並執行你的第一個提示。約需 10 分鐘。完成後你會擁有一個可與之對話、能運作的 Veles 專案。

## 先決條件

- **Python 3.13+**（Veles 要求 `>=3.13`）。
- 一個 LLM API 金鑰。我們會使用 **OpenRouter**（預設供應商）；任何[其他供應商](../reference/providers.md)也都可以，包括完全在本機、無需金鑰的供應商。

## 1. 安裝

Veles 透過 [uv](https://docs.astral.sh/uv/) 安裝成全域的 `veles` 命令：

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

日後更新：`uv tool upgrade veles-ai`。

## 2. 給 Veles 一個 API 金鑰

從 [openrouter.ai](https://openrouter.ai) 取得金鑰並匯出：

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

你也可以將它存進 OS 鑰匙圈，這樣就不必每開一個 shell 都重新匯出：

```bash
veles secret set OPENROUTER_API_KEY
```

（偏好完全本機、無需金鑰的設定？安裝 [Ollama](https://ollama.com)、執行 `ollama pull qwen3:4b-instruct`，並在下方使用 `--provider ollama`。）

## 3. 建立你的第一個專案

一個 Veles 專案就只是一個含有 `.veles/` 狀態資料夾的目錄。建立一個：

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

這會建立 `AGENTS.md`（你的專案脈絡）、`sources/` 與 `wiki/`（預設的 [LLM-Wiki 版面](../explanation/layout-packs-and-llm-wiki.md)），以及 `.veles/`（機器狀態）。參見[專案版面](../reference/project-layout.md)。

## 4. 執行你的第一個提示

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles 會載入你的專案脈絡、呼叫模型並印出答案。該輪次會被存進專案的記憶體。

加上 `--stream` 可在 token 抵達時即時看到，或用 `--verbose` 顯示逐輪進度：

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. 開啟互動式 REPL

若要進行多輪對話，開啟 TUI：

```bash
veles tui
```

輸入一則訊息並按 Enter。實用按鍵：`Ctrl+D` 離開、`Shift+Tab` 循環切換[執行模式](../explanation/modes.md)、`/help` 列出斜線命令。完整清單見 [TUI 參考](../reference/tui.md)。

## 6. 查看 Veles 記得什麼

每次執行都會被儲存。列出並搜尋你的工作階段：

```bash
veles sessions list
veles sessions search "three sentences"
```

## 接下來

- **[建立知識庫](building-a-knowledge-base.md)**——將來源匯入 wiki 並針對它們提問。
- **[設定供應商](../how-to/configure-providers.md)**——切換到 Anthropic、OpenAI、Gemini 或完全本機的模型。
- **[架構概覽](../explanation/architecture.md)**——了解 Veles 在底層做了什麼。
