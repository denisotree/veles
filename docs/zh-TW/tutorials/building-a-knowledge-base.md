# 建立知識庫

> 🌐 **語言：** **English** · [Русский](../../ru/tutorials/building-a-knowledge-base.md)

在本教學中，你會把一個 Veles 專案變成一座活的知識庫：匯入幾個來源、讓 Veles 寫出 wiki 頁面、提出問題，並整併你學到的內容。這是預設的 **LLM-Wiki** 工作流程。約需 15 分鐘。

你應該先完成 [Getting started](getting-started.md)。

## 概念

一個 Veles 專案有兩個內容區域：

- `sources/` — 你提供給它的原始、不可變動素材（對 agent 唯讀）。
- `wiki/` — agent 自己、由 LLM 產生的知識（它唯一會寫入內容的區域）。

你餵入 sources；Veles 將它們提煉成彼此連結的 wiki 頁面；你以自然語言查詢 wiki。背後的原因請見 [layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)。

## 1. 匯入一個來源

`veles add` 會讀取一個檔案或 URL，並寫出一個總結它的 wiki 頁面：

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

每次 `add` 都會在 `wiki/` 底下產生一個頁面，並將它連結進 wiki 圖譜。

## 2. 看著 wiki 成長

看看寫出了什麼：

```bash
ls wiki/concepts wiki/entities wiki/sources
```

頁面彼此交叉參照。隨選載入的 `wiki/INDEX.md` 目錄維護著一份地圖，agent 在需要時才載入（而非一次傾倒整個 context）。

## 3. 提出問題

現在以自然語言查詢你的知識庫：

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles 會搜尋 wiki、讀取相關頁面，然後回答 — 立基於你匯入的內容，而不只是它的訓練資料。

若要進行互動式的一來一往，在 TUI 中（`veles tui`）做同樣的事。

## 4. 整併 sessions

隨著你工作，對話會累積起來。執行 curator 把它們壓縮成持久的 wiki 頁面並萃取出心得：

```bash
veles curate
```

這會寫出 `wiki/sessions/` 頁面，並更新專案的 insights 與 rules。Veles 也會隨時間自動做這件事 — 見 [project memory & the learning loop](../explanation/project-memory-and-learning-loop.md)。

## 5. 保持 wiki 健康

隨著時間推移，頁面會過時或變成孤立。`lint` 操作會找出它們：

```bash
veles run "lint"
```

（`ingest`、`query` 與 `lint` 是隨 LLM-Wiki layout 附帶的 skills；你以 `veles run "<operation>"` 來呼叫它們，或讓 agent 自行呼叫。）

## 你建立了什麼

一座自我組織的知識庫：來源進去、彼此連結的 wiki 頁面出來、可用自然語言查詢，而且會隨著 Veles 整併而愈來愈整齊。接下來：

- **[Manage skills, tools, and modules](../how-to/manage-skills-and-tools.md)** — 教 Veles 可重複使用的工作流程。
- **[Run as a daemon](../how-to/run-as-daemon.md)** + **[connect Telegram](../how-to/connect-telegram.md)** — 從你的手機與知識庫對話。
- **[Multiple projects & subprojects](../how-to/multi-project-and-subprojects.md)** — 擴展到多座知識庫。
