# 如何将 Veles 作为守护进程运行

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

守护进程是一个可选的、长期运行的 HTTP+WS 服务器，它将智能体以 API 的形式
暴露出来 —— 它是[频道](connect-telegram.md)（Telegram 等）、定时
[任务](long-running-tasks.md)以及远程／无界面使用的基础。

## 启动与停止

```bash
veles daemon start              # 默认以分离模式运行；绑定 127.0.0.1:8765
veles daemon status             # 它在运行吗？
veles daemon stop               # 通过 pid 文件发送 SIGTERM
```

`start` 会分离并把 shell 交还给你。若需要前台进程（systemd
`Type=simple`、Docker、调试），请传入 `--foreground`。覆盖绑定地址：

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

守护进程的模型和提供方来自项目配置，并在**其整个生命周期内固定不变** ——
请在启动前设置好：

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## 认证令牌

API 客户端使用 bearer 令牌进行认证：

```bash
veles daemon token add tui-client     # 生成一个令牌
veles daemon token list               # 列出（已掩码）
veles daemon token remove tui-client
```

## 守护进程选择器（TUI）

不带任何子命令运行 `veles daemon` 即可打开控制面板 —— 一棵展示你项目的
守护进程以及每个守护进程频道的树：

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

按键：`Enter` 打开某个守护进程的日志；`s`/`t`/`r` 启动/停止/重启；`d` 删除；
`c`/`x` 添加/移除一个频道；`q` 退出。

## 每个项目运行多个守护进程（命名会话）

一个项目可以同时运行多个使用不同模型/端口的守护进程。先声明一个命名
会话，再启动它：

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

每个命名会话都有自己的 `[daemon.<name>]` 配置块以及自己的频道
（`[daemon.<name>.channels.*]`）。

## 列出跨项目的守护进程

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## 下一步

- [接入 Telegram 频道](connect-telegram.md)
- [安排定时任务](long-running-tasks.md)
