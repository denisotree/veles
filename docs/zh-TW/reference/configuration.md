# 設定參考

> 🌐 **語言：** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · **繁體中文** · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

Veles 由兩個 TOML 檔案與一組狀態目錄來設定。機密（API 金鑰、機器人權杖）**絕不會**寫入這些檔案——它們存放在 OS 鑰匙圈或環境變數中（參見[環境變數](environment-variables.md)）。

## 狀態存放位置

| 路徑 | 範圍 | 內容 |
|---|---|---|
| `~/.veles/` | 使用者全域 | `config.toml`、信任授權、跨專案技能／工具、模型快取、語系、登錄庫 |
| `<project>/.veles/` | 專案本地 | `project.toml`、`config.toml`、`memory.db`、專案技能／工具、計畫、執行期暫態檔 |
| `<project>/AGENTS.md` | 專案 | 注入代理的脈絡檔（以符號連結指向 `CLAUDE.md` / `GEMINI.md`） |
| `<project>/wiki/`、`sources/` | 專案 | 使用者內容（預設的 LLM-Wiki 版面） |

`VELES_USER_HOME` 會重新導向 `~`（因此使用者狀態會落在 `<override>/.veles/`）。完整的目錄樹參見[專案版面](project-layout.md)。

---

## 使用者設定——`~/.veles/config.toml`

由首次執行的精靈寫入；可安全地手動編輯。

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| 鍵 | 型別 | 用途 |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI 字串的語系（可透過 `VELES_LOCALE` 覆寫） |
| `[user] default_provider` | string | 未指定時所用的供應商 |
| `[user] default_model` | string | 未指定時所用的模型 |
| `[user] tui_theme` | string | 預設的 TUI 色彩主題 |
| `[permissions] <tool>` | policy | 逐工具的權限策略（參見[信任與沙箱](../explanation/trust-and-sandbox.md)） |

---

## 專案設定——`<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### 各區段

| 區段 | 用途 |
|---|---|
| `[engine]` | 基礎供應商（`provider` = 供應商名稱）＋模型（`model` = 模型 ID），供主代理與路由串接使用 |
| `[routing.tasks]` | 逐任務的 `provider:model` 覆寫——參見[逐任務路由](../how-to/per-task-routing.md) |
| `[permissions]` | 逐工具的權限策略（專案範圍） |
| `[daemon]` | 未具名／「預設」daemon 的綁定＋自動啟動 |
| `[daemon.<name>]` | 一個具名 daemon 工作階段（自己的 model/provider/host/port/mode） |
| `[channels.<type>]` | 由未具名 daemon 服務的 channel（例如 `telegram`） |
| `[daemon.<name>.channels.<type>]` | 綁定至某具名 daemon 工作階段的 channel |
| `[mcp.servers.<name>]` | 一個外部 MCP 伺服器（工具來源） |

`[routing.tasks]` 的任務類型：`default`、`curator`、`compressor`、`insights`、`skills`、`advisor`、`vision`、`embedding`。

> `AGENTS.md` 中的自然語言路由提示會被解析進一個自動產生的 `routing.nl.toml`；明確的 `[routing.tasks]` 條目永遠優先。執行 `veles route refresh` 可重新解析。參見[逐任務路由](../how-to/per-task-routing.md)。

### 固定後端，以及其他請求主體鍵

`[engine.request.<provider>]` 會**原樣**轉送到該供應商的請求主體中。Veles 不去建模
上游的 schema，因此供應商接受的任何選項都能直接生效，無需等待 Veles 支援：

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

該小節以**供應商名稱**為鍵（`openrouter`、`anthropic`、`openai`、`gemini`、
`ollama`、`llamacpp`、`openai-compat`），這樣同一份專案設定就能跨越後端切換：把
OpenRouter 的 `provider` 區塊送給 llama.cpp 會得到 400，所以每個後端只讀自己的子小節。
未宣告該小節時，請求與之前逐位元組相同。

**什麼時候需要它：可重現的量測。** 像 OpenRouter 這樣的中繼會把同一個模型分派到許多
量化方式不同的後端，於是相同輸入的兩次執行可能因為與輸入無關的原因而不一致。以
`session_id` 為基礎的黏性路由能把一次對話固定在同一個後端，卻不會告訴你是**哪一個**。

請用 `order` 固定，而不是 `quantizations`。截至 2026-09-18，`z-ai/glm-5.3-flash`
有 29 個端點：`fp8` 16 個、`fp4` 3 個、`nvfp4` 1 個、**完全不宣告量化方式的有 9 個**，
`bf16` 一個也沒有。因此 `quantizations = ["fp8"]` 仍會留下 16 個候選，脈絡視窗
從 262144 到 1310720 token 不等；而只含一個元素的 `order` 加上
`allow_fallbacks = false` 則能唯一決定後端。列出某個模型的端點：

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

固定只保留在量測專案裡——正式環境需要黏性路由，它保住了可用性與回退。

**驗證固定是否生效。** 每次模型呼叫都會把意圖與結果一起寫入
`.veles/traces.jsonl`：`request_extra` 是送出去的內容，`upstream_provider` 是真正
回應的後端。一行指令即可：

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

輸出多於一行，代表這次執行混用了後端。同樣的紀錄還帶有 `reasoning_tokens`（預算中
用於推理的部分）與 `est_cost_usd`（上游回報的實際計費成本）。

**錯誤是刻意吵鬧的。** 供應商名稱拼錯，或小節路徑寫錯（`[engine.reqest.…]`），都會以
`ConfigError` 中斷執行，並指出檔名與已知的供應商：一個從未到達線路的固定，會悄悄
讓它原本要服務的量測失效。供應商子小節*內部*的鍵 Veles 不做驗證，因為上游會驗證：
OpenRouter 對未知鍵回傳 `400 provider: Unrecognized key: "quantization"`，對無法對應
的值回傳 `404 No endpoints found …`。

### 對話紀錄保留多久

```toml
[memory]
turn_retention_days = 90   # 0 表示永久保留
```

原始對話輪次會在超過該天數後刪除，而從中萃取出的**洞察**與規則則永久保留。紀錄是
原料，洞察才是閱讀它的目的——於是 `memory.db` 不再無限成長，而代理仍保有它學到的
東西。

一份紀錄要被丟棄需要**同時**滿足兩個條件：早於保留視窗，**而且**策展器已經處理過該
工作階段。策展器尚未觸及的工作階段永遠不會被刪除，無論多舊——否則紀錄會在還沒從中
學到任何東西之前就被銷毀。

可見的代價：`veles sessions search` 只能找到視窗之內的文字。`veles sessions list`
仍然會列出更早的執行，因為工作階段列（id、標題、時間戳記）會保留，消失的只是訊息
內文。清理發生在 `veles dream` 期間，位於洞察萃取之後。

### 日誌輪替

`traces.jsonl` 與 `events.jsonl` 在 50 MB 時輪替為 `<名稱>.<unix_ts>`，並保留最近的
**10** 份，更早的會在下一次輪替時刪除。此前它們會被永久保存。

在一般用量下無需任何設定：每筆 trace 紀錄約 530 位元組，代理每輪約 1.1 KB 事件，
距離第一次輪替還有數年。這個設定之所以存在，是因為沒有政策的無限成長是一處洩漏，
最終得由接手這台機器的人去發現。

### 圖片

傳送到頻道的照片會在這一輪開始之前先被描述，使用的是 `[routing.tasks].vision` 指向的
模型——若未明確設定路由，即你的 `[engine]` 模型。因此多模態引擎完全不需要設定。

`[vision] mode` 選擇處理流程：

- `model`（預設）——由視覺模型描述圖片。
- `ocr` —— 僅用 Tesseract。本機、免費、不呼叫 LLM；適合文字掃描件。
- `ocr+model` —— 先給出逐字文字，再給出模型的描述。
- `off` —— 什麼都不讀；檔案仍會儲存，代理如果需要可以自行呼叫
  `image_describe` / `image_ocr`。

當引擎只支援文字時，請設定 `[vision] model`。任何具備視覺能力的供應商都可以，包括
本機伺服器：`ollama:llava`、`llamacpp:…`、`openai-compat:…`。

### `project.toml`

`<project>/.veles/project.toml` 保存不可變的專案中繼資料（`name`、`created_at`、`schema_version`、`layout`）。一般情況下不需手動編輯。

---

## AGENTS.md

位於專案根目錄的專案脈絡檔。它會在啟動時注入代理的系統提示，並以符號連結指向 `CLAUDE.md` 與 `GEMINI.md`，因此在該目錄中啟動的 `claude` 或 `gemini` CLI 會取得相同的脈絡。

請保持精簡——輔助的 `.md` 檔（例如 `wiki/INDEX.md`）會按需載入。以 `veles schema validate` 驗證必要章節。參見[版面套件與 LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)。
