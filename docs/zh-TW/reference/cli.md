# CLI 參考

> 🌐 **語言：** **English** · [Русский](../../ru/reference/cli.md)

每一個 Veles 命令、子命令與旗標。執行 `veles <command> --help` 可取得
權威且永遠最新的簽章——本頁面對應 `src/veles/cli/_parsers/` 中的
引數解析器。

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — 即使 `~/.veles/config.toml` 不存在也跳過首次執行的設定精靈
  （同時受 TTY 與 `VELES_NO_WIZARD=1` 條件限制）。
- 不帶任何引數時，`veles` 會啟動互動式 [TUI](tui.md)。

大多數 agent 命令都接受底部列出的[共用 agent-loop 旗標](#shared-agent-loop-flags)
與 [provider 名稱](#provider-names)。

---

## 專案生命週期

### `veles init [name]`
在目前目錄建立一個新的 Veles 專案（一個 `.veles/` 狀態目錄
＋ `AGENTS.md` ＋ 所選 layout pack 的內容 scaffold）。

| Flag | Default | Purpose |
|---|---|---|
| `name` (positional) | cwd basename | 專案名稱 |
| `--layout <name>` | `llm-wiki` | 內容 scaffold 所用的 layout pack（`llm-wiki`、`notes`、`bare`，或來自 `~/.veles/layouts/` 的自訂 pack） |
| `--force` | off | 即使 `.veles/` 已存在也重新建立 |

### `veles schema {validate,edit,fix}`
驗證或編輯 `AGENTS.md`（專案 context 檔案）。

- `validate` — 檢查是否含有必要的 H2 區段。
- `edit` — 以 `$EDITOR`（預設 `vi`）開啟 `AGENTS.md`，退出時進行驗證。
- `fix` — 透過 LLM 精靈以互動方式補上缺漏的區段。

### `veles self-doc [refresh|show]`
產生並顯示專案自我說明文件（`wiki/self-doc/overview.md`）。
單獨的 `veles self-doc` 會顯示目前頁面；`refresh` 則重新產生。

### `veles doctor`
對使用者層級的全域狀態與使用中專案執行健康檢查。無論是否有
使用中專案皆可運作。

| Flag | Default | Purpose |
|---|---|---|
| `--json` | off | 輸出 JSON 報告 |
| `--strict` | off | 出現任何警告即以非零碼退出（用於 CI 把關） |

### `veles export {full,template} <path>`
將專案打包成 `.tar.gz` bundle。參閱[備份與分享](../how-to/backup-and-share.md)。

- `full <path>` — 整個專案（`.veles/` ＋ `AGENTS.md`），不含執行期暫存內容。
- `template <path>` — 經過清理的子集（schema ＋ skills ＋ modules ＋ 非 session
  wiki 頁面）；移除 `memory.db`、`sources/`、`sessions/`、`trust` 授權，並
  對文字進行 PII 遮蔽。

### `veles import <path>`
還原由 `veles export` 建立的 bundle。

| Flag | Default | Purpose |
|---|---|---|
| `path` (positional) | — | bundle 路徑（`.tar.gz`） |
| `--into <dir>` | cwd | 目標目錄 |
| `--force` | off | 覆寫目標位置現有的 `.veles/` |

---

## 執行 agent

### `veles run "<prompt>"`
端到端執行單一 prompt，具備記憶體保存以及 curator／學習
觸發機制。接受所有[共用 agent-loop 旗標](#shared-agent-loop-flags)，外加：

| Flag | Default | Purpose |
|---|---|---|
| `--resume <session_id>` | new session | 接續一個既有的 session |
| `--manager` | off | 透過 multi-agent manager 進行任務拆解（亦可用 `VELES_MANAGER_MODE=1`） |
| `--plan` | off | 規劃模式：允許讀取／搜尋／草擬，封鎖變動操作 |
| `--no-agents-md` | off | 不將 `AGENTS.md` 注入系統 prompt |
| `--no-index` | off | 不注入 `wiki/INDEX.md` |
| `--no-compress` | off | 停用滑動視窗式的 context 壓縮 |
| `--no-curator` | off | 為本次執行停用 curator 觸發 |
| `--no-insights` | off | 停用執行後的 insight 抽取 |
| `--no-proposer` | off | 停用 subproject proposer 的自動觸發 |
| `--no-route-refresh` | off | 停用從 `AGENTS.md` 進行的 NL routing 重新整理 |
| `--no-suggest-promote` | off | 停用自動 promote 建議器 |
| `--compressor-model <id>` | routed | 覆寫壓縮模型 |
| `--compress-threshold-tokens <n>` | `50000` | 觸發壓縮的歷史大小 |

### `veles tui`
開啟互動式 REPL。參閱 [TUI 參考](tui.md)。接受共用的
agent-loop 旗標、`--resume`、上述 `--no-*` 注入／壓縮旗標，以及：

| Flag | Default | Purpose |
|---|---|---|
| `--theme <name>` | config or `everforest` | 配色主題（everforest、dracula、gruvbox、tokyo-night、catppuccin） |

### `veles add <source>`
讀取一個來源（本機檔案或 `http(s)://` URL）並將其綜整為一個 wiki
頁面。接受共用的 agent-loop 旗標。

### `veles curate`
執行一輪 curator 處理：將未處理的 session 壓縮為 `wiki/sessions/` 頁面。

| Flag | Default | Purpose |
|---|---|---|
| `--limit <n>` | a small default | 本次執行最多處理的 session 數 |

外加共用的 agent-loop 旗標。

### `veles research "<question>"`
深度研究：拆解為子問題 → 並行探索網路 →
綜整出一份附引用的報告。

| Flag | Default | Purpose |
|---|---|---|
| `--max-subquestions <n>` | `4` | 並行的研究切入角度數量 |

外加共用的 agent-loop 旗標。

### `veles dream`
執行一輪背景記憶整合循環（insights → skill dedup → promote
建議 → wiki lint，可選擇性地進行 LLM 整合）。

| Flag | Default | Purpose |
|---|---|---|
| `--include-consolidation` | off | 執行昂貴的 LLM 整合（需要 API 金鑰） |
| `--dry-run` | off | 執行所有步驟但跳過 `wiki/state` 的寫入 |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | 跳過個別步驟 |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | 覆寫整合模型 |
| `--provider <name>` | `openrouter` | 整合 sub-agent 所用的 provider |
| `--project-root <path>` | discover | 覆寫專案 |

---

## 知識：skills、tools、modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcommand | Purpose |
|---|---|
| `list` | 列出使用中專案的 skills（附遙測資料） |
| `show <name>` | 列印某個 skill 的 `SKILL.md` |
| `add <source> [--name N] [--scope project\|user] [-y]` | 從 git URL 或本機路徑安裝 |
| `remove <name> [--scope project\|user] [-y]` | 刪除已安裝的 skill |
| `promote <name> [--keep-telemetry]` | 將專案 skill 複製到 user 範圍（`~/.veles/skills/`） |
| `demote <name> [-y]` | 將 user skill 複製到使用中專案 |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | 找出近乎重複的 skills |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | 列出達到自動 promote 門檻的 skills |

### `veles tool {list,show,promote}`

| Subcommand | Purpose |
|---|---|
| `list` | 列出本專案 `memory.db` 中編目的 tools |
| `show <name>` | 列印某個 tool 的 manifest ＋ 遙測資料 |
| `promote <name> [-y]` | 將專案 tool 移到 `~/.veles/tools/`（跨專案） |

### `veles module {list,show,add,remove}`

| Subcommand | Purpose |
|---|---|
| `list` | 列出已安裝的 modules |
| `show <name>` | 列印某個 module 的 manifest |
| `add <source> [--name N] [-y]` | 從 git URL 或本機路徑安裝 module |
| `remove <name> [-y]` | 刪除已安裝的 module |

### `veles browse {modules,skills} [query]`
瀏覽經整理的 registries。

| Flag | Default | Purpose |
|---|---|---|
| `query` (positional) | `""` | 子字串篩選 |
| `--source <url>` | canonical | 覆寫 registry 來源 |
| `--json` | off | 輸出 JSON |

---

## Sessions 與記憶體

### `veles sessions {list,show,delete,search}`

| Subcommand | Purpose |
|---|---|
| `list [--limit n]` | 列出近期 session（預設 20 筆） |
| `show <session_id>` | 列印某個 session 的完整輪次歷史 |
| `delete <session_id>` | 刪除一個 session 及其輪次 |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | 對輪次內容進行全文（FTS5）搜尋 |

---

## 多專案

### `veles project {list,add,remove,switch}`

| Subcommand | Purpose |
|---|---|
| `list` | 列出已註冊的專案，最近使用者優先 |
| `add <path> [--slug S]` | 註冊一個既有的專案目錄 |
| `remove <slug>` | 取消註冊一個專案（檔案不動） |
| `switch <slug>` | 列印該專案的絕對路徑（用法：`cd $(veles project switch <slug>)`） |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcommand | Purpose |
|---|---|
| `init <subdir> [--name N] [--description D]` | 建立並註冊一個 subproject |
| `list` | 列出使用中專案的 subprojects |
| `switch <slug>` | 列印某個 subproject 的絕對路徑 |
| `remove <slug>` | 取消註冊一個 subproject |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | 偵測主題群集並提出 subproject 建議 |

---

## Routing 與模型

### `veles route {show,set,reset,refresh}`
各任務的集成 routing——由哪個 `provider:model` 處理每種任務類型
（`default`、`curator`、`compressor`、`insights`、`skills`、`advisor`、`vision`、
`embedding`）。參閱[各任務 routing](../how-to/per-task-routing.md)。

| Subcommand | Purpose |
|---|---|
| `show` | 列印使用中專案已解析的 routing 表 |
| `set <task> <provider:model>` | 將某個任務釘選到一個 spec |
| `reset [task]` | 將一個（或全部）任務重設為預設值 |
| `refresh [--force]` | 重新解析 `AGENTS.md` 中的自然語言 routing 提示 |

### `veles models <provider>`
列出某個 provider 的模型。雲端 provider（openrouter/openai/gemini）會快取
24 小時；本機 provider 一律即時取得。

| Flag | Default | Purpose |
|---|---|---|
| `provider` (positional) | — | [provider 名稱](#provider-names)之一 |
| `--refresh` | off | 略過磁碟快取（僅限雲端） |
| `--json` | off | 以 JSON 形式輸出 `{provider, source, models}` |

---

## 長時間執行的任務

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
具備預算與 checkpoint 的長程目標。

| Subcommand | Purpose |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | 列出 goals |
| `show <id> [--json]` | 顯示一個 goal |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | 建立一個 goal |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | 追加進度 |
| `pause <id>` / `resume <id>` | 暫停／恢復 |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | 完成／取消 |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
排程的 agent jobs。

| Subcommand | Purpose |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | 建立一個 job（schedule = cron、`<N><s\|m\|h\|d>` 或 ISO 時間戳） |
| `list [--json]` / `show <id>` | 檢視 jobs |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | 生命週期管理 |
| `history <id> [--limit n]` | 近期執行紀錄 |
| `tick` | 同步執行所有到期的 job 一次（不需 daemon；接受 agent-loop 旗標） |

---

## 安全性與存取控制

### `veles trust {list,set,revoke,clear}`
針對敏感工具（`run_shell`、`write_file`、`fetch_url` 等）持久化的授權。
參閱[安全性](../how-to/security-and-permissions.md)。

| Subcommand | Purpose |
|---|---|
| `list` | 顯示授權（user ＋ project 範圍） |
| `set <tool> [--scope project\|user]` | 授權一個工具 |
| `revoke <tool> [--scope project\|user\|both]` | 移除一個授權 |
| `clear [--scope project\|user\|all]` | 清除某個範圍內的授權 |

### `veles autopilot {enable,disable,status}`
一個讓 trust ladder 提示自動允許的有時限時間窗。

| Subcommand | Purpose |
|---|---|
| `enable --until <DUR>` | 開啟一個時間窗（`+30m`、`+2h`、`+1d` 或 ISO `2026-05-12T18:00:00Z`） |
| `disable` | 立即關閉時間窗 |
| `status` | 回報 autopilot 是否啟用中 |

### `veles secret {set,get,list,delete}`
以作業系統 keychain 為後盾的 secrets（API 金鑰、bot token）。

| Subcommand | Purpose |
|---|---|
| `set <name> [value]` | 儲存（省略 value 則採互動／stdin 輸入） |
| `get <name> [--reveal] [--no-env-fallback]` | 查找（預設退而求其次使用環境變數） |
| `list` | 顯示已設定哪些標準 secrets |
| `delete <name>` | 移除一個 secret |

---

## Daemon 與 channels

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
執行／控制 HTTP+WS daemon。單獨的 `veles daemon` 會開啟 **daemon 選擇器**
TUI（project → daemons → channels）。參閱[作為 daemon 執行](../how-to/run-as-daemon.md)。

| Subcommand | Purpose |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | 啟動一個 daemon（預設脫離終端） |
| `stop [--name N]` / `status [--name N]` | 停止／檢視 |
| `list` | 列出所有專案的 daemon |
| `restart [target] [--name N]` | 停止後在相同 host/port 重新啟動 |
| `delete <target> [-y]` | 停止並從 registry 移除 |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | 宣告一個具名 daemon session |
| `session list [--all]` / `session delete <name>` | 管理具名 session |
| `token add <name>` / `token list` / `token remove <name>` | bearer-token 的增刪查 |

`start` 也接受共用的 agent-loop 旗標；對 daemon 而言，`--model` /
`--provider` 預設取自專案設定，並在 daemon 的整個生命週期內固定不變。

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
與 daemon 對接的外部聊天 gateway（Telegram 等）。參閱
[連接 Telegram](../how-to/connect-telegram.md)。

| Subcommand | Purpose |
|---|---|
| `list` | 列出已註冊的 channel 平台 ＋ session 計數 |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | 在前景啟動一個 gateway |
| `list-sessions [--channel C]` | 顯示 `chat_id → session_id` 對應關係 |
| `reset-session <chat_id> [--channel C]` | 遺忘一個對應關係（下一則訊息將重新開始） |
| `add [--channel C] [--session S]` | 將一個 channel 附加到某個 daemon（精靈；憑證 → keychain） |
| `remove <channel> [--session S]` | 移除一個 channel 綁定 |

---

## MCP（外部 tool 伺服器）

### `veles mcp {list,test}`
檢視在 `[mcp.servers.*]` 下設定的外部 MCP 伺服器。參閱
[外部 MCP 伺服器](../how-to/external-mcp-servers.md)。

| Subcommand | Purpose |
|---|---|
| `list [--connect-timeout f]` | 顯示已設定的伺服器、連線狀態、tool 計數 |
| `test <server>` | 連接一個伺服器並列出其 tools |

---

## 共用 agent-loop 旗標

由 `run`、`add`、`tui`、`curate`、`research`、`job tick` 與 `daemon
start` 接受：

| Flag | Default | Purpose |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: persisted) | 模型 ID |
| `--provider <name>` | `openrouter` | provider（見下方） |
| `--max-tokens-total <n>` | `100000` | 累計 token 預算；`0` 表停用 |
| `--max-iterations <n>` | `30` | 每輪最多的 tool-calling 次數 |
| `--stream` | off | 逐 token 串流回應 |
| `--verbose` / `-v` | off | 將每輪進度輸出到 stderr |
| `--project-root <path>` | discover from cwd | 對其他位置的專案進行操作 |

## Provider 名稱

`openrouter`（預設）· `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

本機 provider（`ollama`、`llamacpp`、`openai-compat`）不需要 API 金鑰。參閱
[providers 參考](providers.md)與[設定 providers](../how-to/configure-providers.md)。
