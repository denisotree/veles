# 如何将 Veles 作为守护进程运行

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

daemon 是一个可选的、长期运行的 HTTP+WS 服务器，它将 agent 暴露为 API——这是 [channels](connect-telegram.md)（Telegram 等）、定时[任务](long-running-tasks.md)以及远程/无头使用的基础。

## 启动与停止

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` 会分离运行并把 shell 交还给你。如需前台进程（systemd `Type=simple`、Docker、调试），传入 `--foreground`。覆盖绑定地址：

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

daemon 的模型和提供方取自项目配置，并在其**整个生命周期内固定不变**——在启动前设置好：

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## 认证 token

API 客户端使用 bearer token 进行认证：

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## daemon 选择器（TUI）

不带子命令运行 `veles daemon` 会打开控制面板——一棵展示你项目的 daemons 以及每个 daemon 的 channels 的树：

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

按键：`Enter` 打开某个 daemon 的日志；`s`/`t`/`r` 启动/停止/重启；`d` 删除；`c`/`x` 添加/移除一个 channel；`q` 退出。

## 每个项目多个 daemon（具名 sessions）

一个项目可以同时运行多个使用不同模型/端口的 daemon。先声明一个具名 session，然后启动它：

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

每个具名 session 都有自己的 `[daemon.<name>]` 配置块和自己的 channels（`[daemon.<name>.channels.*]`）。

## 列出跨项目的 daemons

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## 下一步

- [连接一个 Telegram channel](connect-telegram.md)
- [调度任务](long-running-tasks.md)
