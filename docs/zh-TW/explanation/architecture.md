# 架構總覽

> 🌐 **語言：** [English](../../en/explanation/architecture.md) · [简体中文](../../zh-CN/explanation/architecture.md) · **繁體中文** · [日本語](../../ja/explanation/architecture.md) · [한국어](../../ko/explanation/architecture.md) · [Español](../../es/explanation/architecture.md) · [Français](../../fr/explanation/architecture.md) · [Italiano](../../it/explanation/architecture.md) · [Português (BR)](../../pt-BR/explanation/architecture.md) · [Português (PT)](../../pt-PT/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md) · [العربية](../../ar/explanation/architecture.md) · [हिन्दी](../../hi/explanation/architecture.md) · [বাংলা](../../bn/explanation/architecture.md) · [Tiếng Việt](../../vi/explanation/architecture.md)

本頁說明 Veles *是什麼*，以及它的各個部分如何組合在一起，好讓其餘文件更容易理解。權威的產品願景請參閱倉庫根目錄的 `VISION.md`。

## 設計初衷

Veles 刻意做到**極簡且乾淨分層**——單一職責的模組，沒有巨型檔案。它是**本地優先**的：你針對自己機器上的某個目錄執行它，它會把自己結構化的記憶保存在那裡。

## 五大支柱(核心)

核心中的一切都服務於以下五項工作之一:

1. **專案記憶**——一份結構化的產物(與你的內容分離),保存對話記錄、學到的規則／insight、專案檔案地圖,以及帶有遙測資料的 skill／tool 登錄表。參見[專案記憶與學習迴圈](project-memory-and-learning-loop.md)。
2. **學習迴圈**——curator、insight 擷取器與 dreaming,讓記憶保持新鮮,並把經驗轉化為可重複使用的規則。
3. **多 agent 編排**——一個 manager 負責拆解任務並派生出專門的 worker。參見[多 agent 編排](multi-agent-orchestration.md)。
4. **provider 協定**——以單一介面涵蓋多種 LLM 後端(雲端、本地、CLI 委派)。參見 [providers](../reference/providers.md)。
5. **極簡的 tools 與 skills**——一組小型的啟動集合,隨著 Veles 撰寫自己的 tools、並把重複流程形式化為 skills 而**逐步累積**。參見 [skills 與 tools](skills-and-tools.md)。

## 其餘一切都是可選模組

Gateway／channel、daemon、排程器、TUI、視覺／STT——全部都是**可插拔**的,只有在使用時才載入。Veles 以最小集合啟動,並按需擴展,因此單純的 `veles run` 維持單純。

## 一個回合如何流動

```
your prompt
   │
   ▼
context: AGENTS.md (small) + on-demand recall from project memory
   │
   ▼
agent loop  ──►  provider (routed per task)  ──►  tool calls
   │                                               │
   │            (trust ladder gates sensitive tools)
   ▼
response  ──►  saved to memory  ──►  learning triggers (insights, curator)
```

context 檔案(`AGENTS.md`)刻意保持精簡;輔助知識(wiki 頁面、專案檔案地圖、相關的過往回合)是**按需**拉入,而不是一開始就全部傾倒進來。

## 狀態存放在哪裡

- `<project>/.veles/`——本專案的記憶、設定、本地 skills／tools。
- `~/.veles/`——使用者全域設定、跨專案 skills／tools、快取、trust。
- `<project>/AGENTS.md`、`wiki/`、`sources/`——你的內容(LLM-Wiki 佈局)。

參見[專案佈局](../reference/project-layout.md)。

## 一個迴圈服務多專案

單一 agent 迴圈服務眾多專案。每個專案都有自己的目錄,擁有自己的 context 與記憶;`AGENTS.md` 會被符號連結到 `CLAUDE.md`／`GEMINI.md`,因此在那裡啟動的外部 CLI 也能看到相同的 context。參見[多專案](../how-to/multi-project-and-subprojects.md)。

## 各個介面

- **CLI**(`veles run`、`veles add`、……)——一次性與腳本化使用。
- **TUI**(`veles tui`)——具備[執行模式](modes.md)的互動式 REPL。
- **Daemon + channels**——無頭 API、Telegram、排程作業。

這三者都驅動同一套核心 agent 迴圈。
