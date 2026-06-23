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
[provider]
default = "openrouter"                               # provider name for the main agent + routing base
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
| `[provider]` | 基礎供應商（`default` = 供應商名稱）＋模型（`model` = 模型 ID），供主代理與路由串接使用 |
| `[routing.tasks]` | 逐任務的 `provider:model` 覆寫——參見[逐任務路由](../how-to/per-task-routing.md) |
| `[permissions]` | 逐工具的權限策略（專案範圍） |
| `[daemon]` | 未具名／「預設」daemon 的綁定＋自動啟動 |
| `[daemon.<name>]` | 一個具名 daemon 工作階段（自己的 model/provider/host/port/mode） |
| `[channels.<type>]` | 由未具名 daemon 服務的 channel（例如 `telegram`） |
| `[daemon.<name>.channels.<type>]` | 綁定至某具名 daemon 工作階段的 channel |
| `[mcp.servers.<name>]` | 一個外部 MCP 伺服器（工具來源） |

`[routing.tasks]` 的任務類型：`default`、`curator`、`compressor`、`insights`、`skills`、`advisor`、`vision`、`embedding`。

> `AGENTS.md` 中的自然語言路由提示會被解析進一個自動產生的 `routing.nl.toml`；明確的 `[routing.tasks]` 條目永遠優先。執行 `veles route refresh` 可重新解析。參見[逐任務路由](../how-to/per-task-routing.md)。

### `project.toml`

`<project>/.veles/project.toml` 保存不可變的專案中繼資料（`name`、`created_at`、`schema_version`、`layout`）。一般情況下不需手動編輯。

---

## AGENTS.md

位於專案根目錄的專案脈絡檔。它會在啟動時注入代理的系統提示，並以符號連結指向 `CLAUDE.md` 與 `GEMINI.md`，因此在該目錄中啟動的 `claude` 或 `gemini` CLI 會取得相同的脈絡。

請保持精簡——輔助的 `.md` 檔（例如 `wiki/INDEX.md`）會按需載入。以 `veles schema validate` 驗證必要章節。參見[版面套件與 LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)。
