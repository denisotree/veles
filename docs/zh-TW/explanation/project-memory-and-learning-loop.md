# 專案記憶與學習迴圈

> 🌐 **語言:** **English** · [Русский](../../ru/explanation/project-memory-and-learning-loop.md)

Veles 的標誌性特色在於它會按專案**記憶**並**學習**。本頁說明這份記憶是什麼,以及學習迴圈如何讓它持續有用。

## 記憶是一份結構化產物

專案記憶存放在 `<project>/.veles/`——`memory.db`(SQLite,真理來源)加上一個人類可讀的 `.veles/memory/` 樹(渲染後的 insight 檢視、session digest、proposal、system-ops journal)。它與**你的內容分離**,並在任何佈局(wiki、notes 或 bare)下都以相同方式運作。它不是聊天逐字稿的傾倒,而是一組結構化的層次:

- **Session 記錄**——每一次對話,每個回合一列,並建立全文索引。
- **規則**——agent 應遵循的簡短祈使句(`format`、`do`、`don't`、`preference`),注入到穩定的系統 prompt 中。
- **Insights**——從 sessions 提煉出的教訓。SQL 列是正本(recall、aging 與 dedup 都對它操作);一份 markdown 檢視會渲染到 `.veles/memory/insights/`,供人類閱讀與匯出使用。
- **專案樹地圖**——一份經快取、帶語意標記的檔案地圖,讓 agent 讀取那 3–5 個相關檔案,而非整棵樹。
- **Skill 與 tool 登錄表**——附帶遙測資料(使用／成功／錯誤次數),供排名與 dedup 使用。

表格清單參見[專案佈局](../reference/project-layout.md#project-memory-velesmemorydb)。

## Recall:精簡的 context,按需拉取

`AGENTS.md` 刻意保持精簡。當你提問時,Veles 只拉入相關的內容:相符的過往回合(全文 + 可選的向量 reranking)、適用的規則與 insights,以及專案樹地圖評分最高的那些檔案。這讓每一次模型呼叫都保持聚焦且廉價,而非把一切都傾倒進去。

## 學習迴圈

經驗透過三種機制變成持久的知識:

### Insights — 擷取教訓
一次執行之後,擷取器會尋找值得記住的事物:明確的「記住 X」／「絕不要 Y」回饋,以及 tool-error→recovery 模式(一次失敗緊接著一次修復)。它把這些提煉成 insights 與規則,讓同樣的錯誤不再重複。

### Curator — 整併 sessions
curator 把較舊的 sessions 提煉成持久的記憶:一律產生 SQL insights 與規則;當專案佈局啟用 wiki engine 時,額外產生一個 `wiki/sessions/` 頁面。它會在閒置／回合後的計時器觸發時執行,或以 `veles curate` 按需執行。

### Dreaming — 背景維護
`veles dream`(以及 daemon 在閒置時)會擷取 insights、對 skills 與 insights 去重、建議晉升,並(在 wiki 佈局下)對 wiki 進行 lint——在不阻擋你的情況下保持記憶新鮮。加上 `--include-consolidation` 可進行更深入的 LLM 處理。

## Context 壓縮

長對話會由一個滑動視窗壓縮器維持在模型的 context 上限之內:當記憶體中的歷史越過某個 token 門檻時,中段會被(由一個廉價的路由模型)摘要,並以指向 `.veles/memory/sessions/` 中已儲存摘要的指標取代。完整歷史始終保留在 `memory.db` 中——只有記憶體中的視窗被壓縮,因此在磁碟上是無損的。

## 為何這很重要

由於記憶是結構化的,且迴圈持續運行,一個 Veles 專案會**越用越有用**——它會學會你的慣例、避免重複的錯誤,並把答案建立在它確實見過的事物之上。
