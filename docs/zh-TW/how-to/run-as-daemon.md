# 如何將 Veles 作為 daemon 執行

> 🌐 **語言：** [English](../../en/how-to/run-as-daemon.md) · [简体中文](../../zh-CN/how-to/run-as-daemon.md) · **繁體中文** · [日本語](../../ja/how-to/run-as-daemon.md) · [한국어](../../ko/how-to/run-as-daemon.md) · [Español](../../es/how-to/run-as-daemon.md) · [Français](../../fr/how-to/run-as-daemon.md) · [Italiano](../../it/how-to/run-as-daemon.md) · [Português (BR)](../../pt-BR/how-to/run-as-daemon.md) · [Português (PT)](../../pt-PT/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · [العربية](../../ar/how-to/run-as-daemon.md) · [हिन्दी](../../hi/how-to/run-as-daemon.md) · [বাংলা](../../bn/how-to/run-as-daemon.md) · [Tiếng Việt](../../vi/how-to/run-as-daemon.md)

daemon 是一個可選的、長時間存活的 HTTP+WS 伺服器，將代理以 API 形式對外提供——是 [channel](connect-telegram.md)（Telegram…）、排程[工作](long-running-tasks.md)以及遠端／無頭使用的基礎。

## 啟動與停止

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` 會脫離並交還你的 shell。若要前景行程（systemd `Type=simple`、Docker、除錯），請傳入 `--foreground`。覆寫綁定：

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

daemon 的模型與供應商取自專案設定，且在其**整個生命週期內固定不變**——請在啟動前設定好：

```toml
# <project>/.veles/config.toml
[engine]
provider = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## 驗證權杖

API 用戶端以 bearer 權杖進行驗證：

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## daemon 選擇器（TUI）

不帶子命令執行 `veles daemon` 可開啟控制面板——一棵呈現你專案的 daemon 以及每個 daemon channel 的樹：

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

按鍵：`Enter` 開啟某 daemon 的 log；`s`/`t`/`r` 啟動／停止／重啟；`d` 刪除；`c`/`x` 新增／移除 channel；`q` 離開。

## 每個專案多個 daemon（具名工作階段）

一個專案可同時執行多個使用不同模型／連接埠的 daemon。先宣告一個具名工作階段，再啟動它：

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

每個具名工作階段都有自己的 `[daemon.<name>]` 設定區段與自己的 channel（`[daemon.<name>.channels.*]`）。

## 列出跨專案的 daemon

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## 接下來

- [連接 Telegram channel](connect-telegram.md)
- [排程工作](long-running-tasks.md)
