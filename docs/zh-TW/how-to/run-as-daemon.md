# 如何將 Veles 作為 daemon 執行

> 🌐 **語言：** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

daemon 是一個可選的長駐 HTTP+WS 伺服器，將 agent 以 API 形式公開——這是
[channels](connect-telegram.md)（Telegram 等）、排程
[jobs](long-running-tasks.md) 以及遠端／無頭使用的基礎。

## 啟動與停止

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` 會脫離終端並把 shell 還給你。若需要前景行程（systemd
`Type=simple`、Docker、除錯），請傳入 `--foreground`。覆寫綁定位址：

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

daemon 的模型與 provider 來自專案設定，並在**整個生命週期內固定不變**——
請在啟動前設定好：

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## 驗證 token

API 用戶端以 bearer token 進行驗證：

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## daemon 選擇器（TUI）

執行 `veles daemon` 而不帶任何子命令，會開啟控制面板——一棵呈現你
專案中各 daemon 以及每個 daemon 之 channels 的樹狀結構：

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

按鍵：`Enter` 開啟某個 daemon 的日誌；`s`/`t`/`r` 啟動／停止／重啟；`d` 刪除；
`c`/`x` 新增／移除 channel；`q` 退出。

## 每個專案的多個 daemon（具名 session）

一個專案可以同時執行多個採用不同模型／連接埠的 daemon。先宣告一個
具名 session，再啟動它：

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

每個具名 session 都有自己的 `[daemon.<name>]` 設定區塊以及自己的
channels（`[daemon.<name>.channels.*]`）。

## 列出跨專案的 daemon

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## 下一步

- [連接 Telegram channel](connect-telegram.md)
- [排程 jobs](long-running-tasks.md)
