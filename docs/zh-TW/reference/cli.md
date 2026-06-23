# CLI 參考

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/cli.md)

涵蓋每一個 Veles 命令、子命令與旗標。執行 `veles <command> --help` 可取得權威且永遠最新的簽章——本頁面對應 `src/veles/cli/_parsers/` 中的引數解析器。

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard`——即使 `~/.veles/config.toml` 不存在也跳過首次執行的設定精靈（同時也受 TTY 與 `VELES_NO_WIZARD=1` 控制）。
- 不帶任何引數時，`veles` 會啟動互動式 [TUI](tui.md)。

多數代理命令都接受底部列出的[共用代理迴圈旗標](#shared-agent-loop-flags)與[供應商名稱](#provider-names)。

---

## 專案生命週期

### `veles init [name]`
在目前目錄建立一個新的 Veles 專案（一個 `.veles/` 狀態目錄＋ `AGENTS.md` ＋所選版面套件的內容骨架）。

| 旗標 | 預設 | 用途 |
|---|---|---|
| `name`（位置引數） | cwd 的 basename | 專案名稱 |
| `--layout <name>` | `llm-wiki` | 內容骨架所用的版面套件（`llm-wiki`、`notes`、`bare`，或來自 `~/.veles/layouts/` 的自訂套件） |
| `--force` | 關閉 | 即使 `.veles/` 已存在也重新建立 |

### `veles schema {validate,edit,fix}`
驗證或編輯 `AGENTS.md`（專案脈絡檔）。

- `validate`——檢查必要的 H2 章節。
- `edit`——在 `$EDITOR`（預設 `vi`）中開啟 `AGENTS.md`，離開時驗證。
- `fix`——透過 LLM 精靈互動式補上缺漏的章節。

### `veles self-doc [refresh|show]`
產生並顯示專案的自我文件（`wiki/self-doc/overview.md`）。單獨執行 `veles self-doc` 會顯示目前的頁面；`refresh` 會重新產生。

### `veles doctor`
對使用者全域狀態與作用中的專案執行健康檢查。無論是否有作用中的專案都可運作。

| 旗標 | 預設 | 用途 |
|---|---|---|
| `--json` | 關閉 | 輸出 JSON 報告 |
| `--strict` | 關閉 | 出現任何警告即以非零退出（CI 把關） |

### `veles export {full,template} <path>`
將專案打包為 `.tar.gz` 套件。參見[備份與分享](../how-to/backup-and-share.md)。

- `full <path>`——整個專案（`.veles/` ＋ `AGENTS.md`），去除執行期暫態檔。
- `template <path>`——經過淨化的子集（schema ＋技能＋模組＋非工作階段的 wiki 頁面）；移除 `memory.db`、`sources/`、`sessions/`、`trust` 授權，並對文字進行 PII 遮蔽。

### `veles import <path>`
還原由 `veles export` 建立的套件。

| 旗標 | 預設 | 用途 |
|---|---|---|
| `path`（位置引數） | — | 套件路徑（`.tar.gz`） |
| `--into <dir>` | cwd | 目標目錄 |
| `--force` | 關閉 | 覆寫目標處既有的 `.veles/` |

---

## 執行代理

### `veles run "<prompt>"`
端到端執行單一提示，並具備記憶體持久化與 curator／學習觸發器。接受所有[共用代理迴圈旗標](#shared-agent-loop-flags)，外加：

| 旗標 | 預設 | 用途 |
|---|---|---|
| `--resume <session_id>` | 新工作階段 | 接續既有的工作階段 |
| `--manager` | 關閉 | 透過多代理 manager 進行任務拆解（亦可用 `VELES_MANAGER_MODE=1`） |
| `--verify` | 關閉 | 執行結束後，由路由選定的 advisor 評判答案；若確信失敗，則在更強的模型上重跑（亦可用 `VELES_VERIFY_MODE=1`） |
| `--plan` | 關閉 | 規劃模式：允許讀取／搜尋／草擬，封鎖任何變更 |
| `--no-agents-md` | 關閉 | 不將 `AGENTS.md` 注入系統提示 |
| `--no-index` | 關閉 | 不注入 `wiki/INDEX.md` |
| `--no-compress` | 關閉 | 停用滑動視窗脈絡壓縮 |
| `--no-curator` | 關閉 | 本次執行停用 curator 觸發器 |
| `--no-insights` | 關閉 | 停用執行後的洞見擷取 |
| `--no-proposer` | 關閉 | 停用子專案 proposer 的自動觸發 |
| `--no-route-refresh` | 關閉 | 停用從 `AGENTS.md` 進行的 NL 路由刷新 |
| `--no-suggest-promote` | 關閉 | 停用自動晉升建議器 |
| `--compressor-model <id>` | 由路由決定 | 覆寫壓縮模型 |
| `--compress-threshold-tokens <n>` | `50000` | 觸發壓縮的歷史大小 |

### `veles tui`
開啟互動式 REPL。參見 [TUI 參考](tui.md)。接受共用代理迴圈旗標、`--resume`、上述的 `--no-*` 注入／壓縮旗標，外加：

| 旗標 | 預設 | 用途 |
|---|---|---|
| `--theme <name>` | 設定檔或 `everforest` | 色彩主題（everforest、dracula、gruvbox、tokyo-night、catppuccin） |

### `veles add <source>`
讀取一個來源（本機檔案或 `http(s)://` URL），並將其綜整成一個 wiki 頁面。接受共用代理迴圈旗標。

### `veles curate`
執行一次 curator 處理：將未處理的工作階段壓縮為 `wiki/sessions/` 頁面。

| 旗標 | 預設 | 用途 |
|---|---|---|
| `--limit <n>` | 一個較小的預設值 | 本次最多處理的工作階段數 |

外加共用代理迴圈旗標。

### `veles research "<question>"`
深度研究：拆解為子問題 → 平行探索網路 → 綜整成附引用的報告。

| 旗標 | 預設 | 用途 |
|---|---|---|
| `--max-subquestions <n>` | `4` | 平行的研究面向數 |

外加共用代理迴圈旗標。

### `veles dream`
執行一次背景的記憶整併循環（洞見 → 技能去重 → 晉升建議 → wiki lint，並可選擇性地進行 LLM 整併）。

| 旗標 | 預設 | 用途 |
|---|---|---|
| `--include-consolidation` | 關閉 | 執行高成本的 LLM 整併（需 API 金鑰） |
| `--dry-run` | 關閉 | 執行所有步驟但跳過 `wiki/state` 寫入 |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | 關閉 | 跳過個別步驟 |
| `--consolidation-model <id>` | 由路由決定（退回 `anthropic/claude-haiku-4.5`） | 覆寫整併模型 |
| `--provider <name>` | 由路由決定 | 整併子代理的供應商（省略則使用專案路由選定的供應商） |
| `--project-root <path>` | 自動探索 | 覆寫專案 |

---

## 知識：技能、工具、模組

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出作用中專案的技能（含遙測） |
| `show <name>` | 印出某技能的 `SKILL.md` |
| `add <source> [--name N] [--scope project\|user] [-y]` | 從 git URL 或本機路徑安裝 |
| `remove <name> [--scope project\|user] [-y]` | 刪除已安裝的技能 |
| `promote <name> [--keep-telemetry]` | 將專案技能複製到使用者範圍（`~/.veles/skills/`） |
| `demote <name> [-y]` | 將使用者技能複製進作用中的專案 |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | 找出近乎重複的技能 |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | 列出符合自動晉升門檻的技能 |

### `veles tool {list,show,promote}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出本專案 `memory.db` 中編目的工具 |
| `show <name>` | 印出某工具的清單檔＋遙測 |
| `promote <name> [-y]` | 將專案工具移至 `~/.veles/tools/`（跨專案） |

### `veles module {list,show,add,remove}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出已安裝的模組 |
| `show <name>` | 印出某模組的清單檔 |
| `add <source> [--name N] [-y]` | 從 git URL 或本機路徑安裝模組 |
| `remove <name> [-y]` | 刪除已安裝的模組 |

### `veles browse {modules,skills} [query]`
瀏覽經策展的登錄庫。

| 旗標 | 預設 | 用途 |
|---|---|---|
| `query`（位置引數） | `""` | 子字串篩選 |
| `--source <url>` | canonical | 覆寫登錄庫來源 |
| `--json` | 關閉 | 輸出 JSON |

---

## 工作階段與記憶體

### `veles sessions {list,show,delete,search}`

| 子命令 | 用途 |
|---|---|
| `list [--limit n]` | 列出最近的工作階段（預設 20） |
| `show <session_id>` | 印出某工作階段的完整輪次歷史 |
| `delete <session_id>` | 刪除某工作階段及其輪次 |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | 對輪次內容做全文（FTS5）搜尋 |

---

## 多專案

### `veles project {list,add,remove,switch}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出已註冊的專案，最近的排最前 |
| `add <path> [--slug S]` | 註冊一個既有的專案目錄 |
| `remove <slug>` | 取消註冊某專案（檔案不受影響） |
| `switch <slug>` | 印出該專案的絕對路徑（使用 `cd $(veles project switch <slug>)`） |

### `veles subproject {init,list,switch,remove,suggest}`

| 子命令 | 用途 |
|---|---|
| `init <subdir> [--name N] [--description D]` | 建立並註冊子專案 |
| `list` | 列出作用中專案的子專案 |
| `switch <slug>` | 印出某子專案的絕對路徑 |
| `remove <slug>` | 取消註冊某子專案 |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | 偵測主題群集並提議子專案 |

---

## 路由與模型

### `veles route {show,set,reset,refresh}`
逐任務的集成路由——決定哪個 `provider:model` 處理各種任務類型（`default`、`curator`、`compressor`、`insights`、`skills`、`advisor`、`vision`、`embedding`）。參見[逐任務路由](../how-to/per-task-routing.md)。

| 子命令 | 用途 |
|---|---|
| `show` | 印出作用中專案已解析的路由表 |
| `set <task> <provider:model>` | 將某任務固定到一個 spec |
| `reset [task]` | 將一個任務（或全部）重設為預設 |
| `refresh [--force]` | 重新解析 `AGENTS.md` 中的自然語言路由提示 |

### `veles models <provider>`
列出某供應商的模型。雲端供應商（openrouter／openai／gemini）會快取 24 小時；本機供應商一律即時取得。

| 旗標 | 預設 | 用途 |
|---|---|---|
| `provider`（位置引數） | — | [供應商名稱](#provider-names)之一 |
| `--refresh` | 關閉 | 繞過磁碟快取（僅限雲端） |
| `--json` | 關閉 | 以 JSON 輸出 `{provider, source, models}` |

---

## 長時間執行的任務

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
具備預算與檢查點的長期目標。

| 子命令 | 用途 |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | 列出目標 |
| `show <id> [--json]` | 顯示單一目標 |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | 建立一個目標 |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | 追加進度 |
| `pause <id>` / `resume <id>` | 暫停／恢復 |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | 完成／取消 |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
排程的代理工作。

| 子命令 | 用途 |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | 建立工作（schedule = cron、`<N><s\|m\|h\|d>` 或 ISO 時間戳） |
| `list [--json]` / `show <id>` | 檢視工作 |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | 生命週期 |
| `history <id> [--limit n]` | 最近的執行 |
| `tick` | 同步執行一次所有到期的工作（不需 daemon；接受代理迴圈旗標） |

---

## 安全與存取控制

### `veles trust {list,set,revoke,clear}`
針對敏感工具（`run_shell`、`write_file`、`fetch_url`…）的持久化授權。參見[安全](../how-to/security-and-permissions.md)。

| 子命令 | 用途 |
|---|---|
| `list` | 顯示授權（使用者＋專案範圍） |
| `set <tool> [--scope project\|user]` | 授予某工具 |
| `revoke <tool> [--scope project\|user\|both]` | 移除某授權 |
| `clear [--scope project\|user\|all]` | 清除某範圍內的授權 |

### `veles autopilot {enable,disable,status}`
一個限時的視窗，期間信任階梯的提示會自動允許。

| 子命令 | 用途 |
|---|---|
| `enable --until <DUR>` | 開啟一個視窗（`+30m`、`+2h`、`+1d` 或 ISO `2026-05-12T18:00:00Z`） |
| `disable` | 立即關閉視窗 |
| `status` | 回報 autopilot 是否作用中 |

### `veles secret {set,get,list,delete}`
由 OS 鑰匙圈支援的機密（API 金鑰、機器人權杖）。

| 子命令 | 用途 |
|---|---|
| `set <name> [value]` | 儲存（省略 value 則互動／stdin 輸入） |
| `get <name> [--reveal] [--no-env-fallback]` | 查詢（預設會退回環境變數） |
| `list` | 顯示已設定的標準機密 |
| `delete <name>` | 移除一個機密 |

---

## Daemon 與 channel

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
執行／控制 HTTP+WS daemon。單獨執行 `veles daemon` 會開啟 **daemon 選擇器** TUI（專案 → daemon → channel）。參見[作為 daemon 執行](../how-to/run-as-daemon.md)。

| 子命令 | 用途 |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | 啟動一個 daemon（預設會脫離 shell） |
| `stop [--name N]` / `status [--name N]` | 停止／檢視 |
| `list` | 列出所有專案中的 daemon |
| `restart [target] [--name N]` | 停止並在相同 host/port 上重新生成 |
| `delete <target> [-y]` | 停止並從登錄庫移除 |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | 宣告一個具名 daemon 工作階段 |
| `session list [--all]` / `session delete <name>` | 管理具名工作階段 |
| `token add <name>` / `token list` / `token remove <name>` | Bearer 權杖 CRUD |

`start` 也接受共用代理迴圈旗標；對 daemon 而言，`--model` / `--provider` 預設取自專案設定，且在 daemon 的整個生命週期內固定不變。

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
與 daemon 通訊的外部聊天閘道（Telegram…）。參見[連接 Telegram](../how-to/connect-telegram.md)。

| 子命令 | 用途 |
|---|---|
| `list` | 列出已註冊的 channel 平台＋工作階段數 |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | 在前景啟動一個閘道 |
| `list-sessions [--channel C]` | 顯示 `chat_id → session_id` 對應 |
| `reset-session <chat_id> [--channel C]` | 遺忘某對應（下一則訊息將重新開始） |
| `add [--channel C] [--session S]` | 將 channel 附掛到某 daemon（精靈；憑證 → 鑰匙圈） |
| `remove <channel> [--session S]` | 移除某 channel 綁定 |

---

## MCP（外部工具伺服器）

### `veles mcp {list,test}`
檢視在 `[mcp.servers.*]` 下設定的外部 MCP 伺服器。參見[外部 MCP 伺服器](../how-to/external-mcp-servers.md)。

| 子命令 | 用途 |
|---|---|
| `list [--connect-timeout f]` | 顯示已設定的伺服器、連線狀態、工具數量 |
| `test <server>` | 連接某伺服器並列出其工具 |

---

## 共用代理迴圈旗標

由 `run`、`add`、`tui`、`curate`、`research`、`job tick` 與 `daemon start` 接受：

| 旗標 | 預設 | 用途 |
|---|---|---|
| `--model <id>` | 由專案 `[provider]` model → 使用者 `default_model` 解析（無硬寫死的預設） | 模型 ID |
| `--provider <name>` | `openrouter` | 供應商（見下方） |
| `--max-tokens-total <n>` | `100000` | 累積 token 預算；`0` 表停用 |
| `--max-iterations <n>` | `30` | 每輪最多的工具呼叫迭代數 |
| `--stream` | 關閉 | 逐 token 串流回應 |
| `--verbose` / `-v` | 關閉 | 將逐輪進度輸出到 stderr |
| `--project-root <path>` | 從 cwd 探索 | 對其他位置的專案進行操作 |

## 供應商名稱

`openrouter`（預設）· `anthropic` · `openai` · `gemini` · `claude-cli` · `gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

本機供應商（`ollama`、`llamacpp`、`openai-compat`）不需 API 金鑰。參見[供應商參考](providers.md)與[設定供應商](../how-to/configure-providers.md)。
