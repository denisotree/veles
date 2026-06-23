# 設定參考

> 🌐 **語言：** **English** · [Русский](../../ru/reference/configuration.md)

Veles 由兩個 TOML 檔案與一組狀態目錄進行設定。Secrets
（API 金鑰、bot token）**絕不會**寫進這些檔案——它們存放於作業系統的
keychain 或環境變數中（參閱[環境變數](environment-variables.md)）。

## 狀態存放於何處

| Path | Scope | Contents |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`、trust 授權、跨專案 skills/tools、模型快取、locales、registry |
| `<project>/.veles/` | Project-local | `project.toml`、`config.toml`、`memory.db`、專案 skills/tools、plans、執行期暫存物 |
| `<project>/AGENTS.md` | Project | 注入 agent 的 context 檔案（symlink 到 `CLAUDE.md` / `GEMINI.md`） |
| `<project>/wiki/`, `sources/` | Project | 使用者內容（預設的 LLM-Wiki layout） |

`VELES_USER_HOME` 會重新導向 `~`（使得 user 狀態落在 `<override>/.veles/`）。
完整的目錄樹請參閱[專案 layout](project-layout.md)。

---

## User 設定——`~/.veles/config.toml`

由首次執行的精靈寫入；可安全地手動編輯。

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Key | Type | Purpose |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI 字串的 locale（可用 `VELES_LOCALE` 覆寫） |
| `[user] default_provider` | string | 未指定時使用的 provider |
| `[user] default_model` | string | 未指定時使用的模型 |
| `[user] tui_theme` | string | 預設 TUI 配色主題 |
| `[permissions] <tool>` | policy | 各工具的權限政策（參閱 [trust 與沙箱](../explanation/trust-and-sandbox.md)） |

---

## 專案設定——`<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base for the main agent + routing

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

### 區段

| Section | Purpose |
|---|---|
| `[provider]` | 主 agent 與 routing 串接所用的基礎 provider／模型 |
| `[routing.tasks]` | 各任務的 `provider:model` 覆寫——參閱[各任務 routing](../how-to/per-task-routing.md) |
| `[permissions]` | 各工具的權限政策（專案範圍） |
| `[daemon]` | 未具名／「default」daemon 的綁定位址 ＋ autostart |
| `[daemon.<name>]` | 一個具名 daemon session（擁有自己的 model/provider/host/port/mode） |
| `[channels.<type>]` | 由未具名 daemon 服務的 channel（例如 `telegram`） |
| `[daemon.<name>.channels.<type>]` | 綁定到某個具名 daemon session 的 channel |
| `[mcp.servers.<name>]` | 一個外部 MCP 伺服器（tool 來源） |

`[routing.tasks]` 的任務類型：`default`、`curator`、`compressor`、`insights`、
`skills`、`advisor`、`vision`、`embedding`。

> `AGENTS.md` 中的自然語言 routing 提示會被解析成自動產生的
> `routing.nl.toml`；明確的 `[routing.tasks]` 條目永遠優先。執行
> `veles route refresh` 可重新解析。參閱[各任務 routing](../how-to/per-task-routing.md)。

### `project.toml`

`<project>/.veles/project.toml` 保存不可變的專案中繼資料（`name`、
`created_at`、`schema_version`、`layout`）。一般不需要手動編輯它。

---

## AGENTS.md

位於專案根目錄的專案 context 檔案。它會在啟動時注入 agent 的
系統 prompt，並 symlink 到 `CLAUDE.md` 與 `GEMINI.md`，使得在該目錄啟動的
`claude` 或 `gemini` CLI 也能接收到相同的 context。

請保持它精簡——輔助的 `.md` 檔案（例如 `wiki/INDEX.md`）會按需載入。
以 `veles schema validate` 驗證必要的區段。參閱
[layout packs 與 LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)。
