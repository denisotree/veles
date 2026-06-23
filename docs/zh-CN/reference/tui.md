# TUI 快捷键与斜杠命令

> 🌐 **Languages:** [English](../../en/reference/tui.md) · [Русский](../../ru/reference/tui.md) · **简体中文**

`veles tui`（或直接 `veles`）会打开交互式 REPL。它是一个带回滚的聊天界面，
包含一个多行输入框、一个状态栏和一个可折叠的检查器。

## 快捷键

| 按键 | 操作 |
|---|---|
| `Ctrl+D` | 退出 |
| `Ctrl+C` | 复制最后一条助手回复；在 1.5 秒内按两次可退出 |
| `Ctrl+V` | 从剪贴板粘贴 |
| `Ctrl+Shift+C` / `⌘C` | 复制当前选区（OSC52）。在 macOS 的 Terminal.app 上，原生拖选 + ⌘C 可直接使用 |
| `Ctrl+I` | 切换检查器（推理、工具活动、令牌/错误日志） |
| `Ctrl+R` | 打开会话选择器（恢复过去的会话） |
| `Ctrl+T` | 打开主题选择器 |
| `Shift+Tab` | 循环切换运行模式：`auto → planning → writing → goal` |
| `Tab` | 循环切换斜杠命令补全 |
| `Up` / `Down` | 历史记录（并取出排队的提示） |

运行模式的说明见[运行模式](../explanation/modes.md)。

## 斜杠命令

在输入框中输入 `/`；`Tab` 进行补全。已注册的命令有：

| 命令 | 用途 |
|---|---|
| `/help` | 列出可用命令 |
| `/quit`、`/q`、`/exit` | 退出 REPL |
| `/clear` | 清空聊天日志 |
| `/model` | 打开模型选择器 |
| `/mode` | 切换运行模式（auto/planning/writing/goal） |
| `/session` | 打开会话选择器（恢复） |
| `/save` | 保存 / 命名当前会话 |
| `/history` | 显示会话历史 |
| `/tokens` | 令牌用量（输入 / 输出 / 每轮 / 每会话） |
| `/context` | 当前上下文大小与上限对比 |
| `/status` | 快照：模型、提供商、模式、会话、繁忙状态、队列 |
| `/insights` | 显示该项目习得的洞察 |
| `/rules` | 显示项目的规则摘要 |
| `/schema` | 校验 / 修复 `AGENTS.md` |
| `/wiki` | 针对当前布局的 wiki 操作 |
| `/daemon` | 打开守护进程控制面板（项目 → 守护进程 → 通道） |

> 无论你是直接启动 TUI 还是从另一个屏幕推入，斜杠命令集都是相同的。
> 通道（例如 Telegram）会暴露它们自己独立的命令集。

## 主题

内置主题：`everforest`（默认）、`dracula`、`gruvbox`、`tokyo-night`、
`catppuccin`。用 `Ctrl+T`、`veles tui --theme <name>`，或
`~/.veles/config.toml` 中的 `[user] tui_theme` 来选择。
