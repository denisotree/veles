# TUI 按鍵綁定與 slash 指令

> 🌐 **語言：** **English** · [Русский](../../ru/reference/tui.md)

`veles tui`（或直接執行 `veles`）會開啟互動式 REPL。它是一個帶有多行 composer、狀態列以及可摺疊 inspector 的捲動聊天介面。

## 按鍵綁定

| Key | Action |
|---|---|
| `Ctrl+D` | 退出 |
| `Ctrl+C` | 複製最後一則 assistant 回覆；於 1.5 秒內按兩次則退出 |
| `Ctrl+V` | 從剪貼簿貼上 |
| `Ctrl+Shift+C` / `⌘C` | 複製目前的選取內容（OSC52）。在 macOS 的 Terminal.app 上，原生的拖曳選取 + ⌘C 可直接運作 |
| `Ctrl+I` | 切換 inspector（推理、tool 活動、token/error 日誌） |
| `Ctrl+R` | 開啟 session picker（恢復過去的 session） |
| `Ctrl+T` | 開啟主題選擇器 |
| `Shift+Tab` | 循環切換 run mode：`auto → planning → writing → goal` |
| `Tab` | 循環 slash 指令補全 |
| `Up` / `Down` | 歷史（並彈出排入佇列的 prompts） |

Run modes 的說明請見 [Run modes](../explanation/modes.md)。

## Slash 指令

在 composer 中輸入 `/`；以 `Tab` 補全。已註冊的指令如下：

| Command | Purpose |
|---|---|
| `/help` | 列出可用指令 |
| `/quit`, `/q`, `/exit` | 退出 REPL |
| `/clear` | 清除聊天記錄 |
| `/model` | 開啟模型選擇器 |
| `/mode` | 切換 run mode（auto/planning/writing/goal） |
| `/session` | 開啟 session picker（恢復） |
| `/save` | 儲存／命名目前的 session |
| `/history` | 顯示 session 歷史 |
| `/tokens` | Token 用量（輸入／輸出／每 turn／每 session） |
| `/context` | 目前的 context 大小與上限對比 |
| `/status` | 快照：模型、provider、mode、session、忙碌狀態、佇列 |
| `/insights` | 顯示專案學到的 insights |
| `/rules` | 顯示專案的 rules 摘要 |
| `/schema` | 驗證／修正 `AGENTS.md` |
| `/wiki` | 針對目前 layout 的 wiki 操作 |
| `/daemon` | 開啟 daemon 控制面板（project → daemons → channels） |

> 無論你是直接啟動 TUI 或從另一個畫面推送過來，這組 slash 指令都相同。Channels（例如 Telegram）會公開它們自己、各自獨立的指令集。

## 主題

內建主題：`everforest`（預設）、`dracula`、`gruvbox`、`tokyo-night`、`catppuccin`。以 `Ctrl+T`、`veles tui --theme <name>`，或在 `~/.veles/config.toml` 的 `[user] tui_theme` 來選擇。
