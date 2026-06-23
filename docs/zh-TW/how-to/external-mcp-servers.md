# 如何連接外部 MCP 伺服器

> 🌐 **語言：** [English](../../en/how-to/external-mcp-servers.md) · [简体中文](../../zh-CN/how-to/external-mcp-servers.md) · **繁體中文** · [日本語](../../ja/how-to/external-mcp-servers.md) · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · [Français](../../fr/how-to/external-mcp-servers.md) · [Italiano](../../it/how-to/external-mcp-servers.md) · [Português (BR)](../../pt-BR/how-to/external-mcp-servers.md) · [Português (PT)](../../pt-PT/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · [العربية](../../ar/how-to/external-mcp-servers.md) · [हिन्दी](../../hi/how-to/external-mcp-servers.md) · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

Veles 是一個 [MCP](https://modelcontextprotocol.io/) **用戶端**：它可以連接到
外部 MCP 伺服器，並把它們的 tools 暴露給 agent，彷彿這些 tools 是內建的一樣
（GitHub、函式庫文件、網路搜尋、你自己的服務……）。

## 設定一個伺服器

在 `<project>/.veles/config.toml`（或 user-global 的
`~/.veles/config.toml`）中新增一個 `[mcp.servers.<name>]` 區塊。`<name>` 必須符合
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` — 它會成為每個 tool 名稱的一部分。支援三種
傳輸方式：`stdio`（預設）、`http`、`sse`。

| 鍵 | 傳輸方式 | 預設值 | 用途 |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio（必填） | — | 要啟動的可執行檔 — **僅程式本身，不含參數** |
| `args` | stdio | `[]` | 參數列表，每個項目一個 token |
| `env` | stdio | `{}` | 子行程的額外環境變數（會合併覆蓋在繼承的環境之上） |
| `url` | http/sse（必填） | — | 伺服器端點 |
| `timeout_s` | — | `120` | 單次 tool 呼叫的時間預算 |
| `connect_timeout_s` | — | `30` | 初始連線的時間預算 |
| `enabled` | — | `true` | 設為 `false` 可保留該項目但跳過連線 |

`command`、`args`、`env` 和 `url` 中的字串值會從環境變數插補 `${VAR}`
（未設定的變數會變成空字串並附帶警告）— 請把機密資訊放在檔案之外。

> **`command` 與 `args` 的區別。** Veles 直接執行程式（不經過 shell），因此
> 可執行檔與它的參數是**分開的**欄位。請寫成
> `command = "npx"`、`args = ["-y", "pkg"]` — **不要**寫成 `command = "npx -y pkg"`。

### stdio（本機子行程）

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

你自己執行的伺服器運作方式相同 — 把 `command`/`args` 指向它即可：

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### 需要 API key 的伺服器（context7）

[Context7](https://context7.com) 提供最新的函式庫文件。把 key 當作參數傳入，
讓 `${VAR}` 把它保留在檔案之外：

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse（遠端）

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **（目前）不支援自訂標頭。** `http`/`sse` 傳輸方式只會送出 `url` —
> Veles 無法附加 `Authorization` 標頭。對於需要 key 的遠端伺服器，建議改用它的
> `stdio`（例如 `npx`）變體，把 key 放在 `args`/`env` 中，或使用一個能在 URL
> 中接受 key 的端點。

## 隱藏特定 tools

設定 `[mcp] disabled_tools` — 一個把每個伺服器對應到要跳過的 tool 名稱的表：

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## 檢視與測試

```bash
veles mcp list              # every configured server: transport, status, tool count
veles mcp test github       # connect to one server and list its tools
```

`veles mcp list` 永遠以 0 退出 — 它是檢視工具，不是健康檢查閘門。
`veles mcp test` 在連線失敗時以 1 退出，伺服器名稱未知時以 2 退出。

## tools 如何呈現

設定完成後，伺服器會在下一次 `veles run` / TUI / daemon 啟動時**自動**掛載 —
沒有獨立的「啟用 MCP」旗標，設定的存在本身就是開關。每個 tool 會以
`mcp_<server>_<tool>` 的形式進入一般的 registry，並能像任何內建 tool 一樣被 agent
呼叫。Schema 會經過淨化（名稱/長度限制、去除控制字元），讓不受信任的伺服器無法
注入到 prompt 中。Tool hints 會對應到 trust ladder：破壞性的 tools 一律需要確認，
唯讀的 tools 不會詢問，其餘的則走一般的
[trust](security-and-permissions.md) 流程 — 如果你不想每次都被詢問，可以用
`veles trust set` 授予常駐核可。

## 失敗處理

連線失敗的伺服器 — 缺少 `command`、錯誤的 `url`，或任何無效的項目 — 會被記錄為
警告並跳過。它永遠不會阻擋啟動或 agent。重新執行 `veles mcp list` 即可查看狀態與
錯誤。
