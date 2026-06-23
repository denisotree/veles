# 執行模式

> 🌐 **語言:** **English** · [Русский](../../ru/explanation/modes.md)

在 TUI 中,每個 prompt 都由一個**執行模式**處理——這是一種策略,決定該回合獲得多少自主權與哪些 tools。用 `Shift+Tab` 循環切換模式;順序為 `auto → planning → writing → goal`。

## 四種模式

### `writing` — 直接對話
最直接的模式:你的 prompt 連同完整的 toolset 送給 agent,它做出回應。當你想讓 agent 動手執行一般工作時使用它。

### `planning` — 唯讀研究 + 計畫
變更動作被封鎖(沒有 `write_file`、沒有 `run_shell`)。agent 使用讀取／搜尋 tools 蒐集 context,然後產出一份結構化的計畫產物。在動手之前先思考時使用它——或在 CLI 上對 `veles run` 傳入 `--plan` 以達到相同效果。

### `auto` — 智慧路由(預設)
一次快速分類會判定你的 prompt 是直接請求,還是需要規劃,然後據此派發到 `writing` 或 `planning`。當你尚未表達意圖時,它是最聰明的後備選項,這也是為何它是循環中預設的第一站。

### `goal` — 長程目標
為多步驟目標驅動一個有限狀態機:它會訪談你以釐清需求、確認計畫、執行步驟(搭配 advisor 檢查),並驗證完成條件——全部都在明確的預算之下。CLI 的對應是 [`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints) 命令家族。

## 為何存在模式

不同的請求需要不同程度的謹慎。一個簡單問題不該需要繁文縟節;一個有風險的變更則受益於先做一次唯讀的規劃;一個大型目標需要預算與檢查點。模式讓這個選擇變得明確、且可逐回合切換,而不是把單一行為固化到整個 session。

當你在 session 中途切換時,agent 會被告知新的規則,因此它的行為會立即改變。
