# 如何接入 Telegram 频道

> 🌐 **语言：** [English](../../en/how-to/connect-telegram.md) · **简体中文** · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · [Español](../../es/how-to/connect-telegram.md) · [Français](../../fr/how-to/connect-telegram.md) · [Italiano](../../it/how-to/connect-telegram.md) · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

从 Telegram 与 Veles 项目对话。频道是一个网关，它把消息转发给[守护进程](run-as-daemon.md)，并将回复流式返回。每个聊天都拥有自己独立的对话会话。

Telegram 是官方扩展注册表中的一个模块（`official/telegram`），不属于 Veles 核心。你无需手动安装：`veles channel add` 会提供安装，配置中的 `[channels.telegram]` 块会在下一次 `veles daemon start` 时安装它——你已声明了该频道，这就是许可。它只会从你已连接的注册表安装。

## 前置条件

- 一个 Veles 项目（守护进程只有在存在可用频道时才会启动——这就是一个）。
- 一个来自 [@BotFather](https://t.me/BotFather) 的 Telegram 机器人令牌。

## 方案 A——通过向导接入（推荐）

在项目中运行频道向导；它会写入配置并把令牌存入操作系统钥匙串：

```bash
veles channel add --channel telegram
```

或者接入到某个指定命名的守护进程会话：

```bash
veles channel add --channel telegram --session api
```

你也可以从[守护进程选择器 TUI](run-as-daemon.md#the-daemon-picker-tui) 完成此操作：在某个守护进程上按 `c` 并按提示操作。

这会生成一个配置块：

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

**whitelist** 限制了机器人会回应哪些人（Telegram `@username` 或数字用户 id）。留空则会回应所有人——不推荐这样做，因为每条消息都会消耗模型 token。

启动（或重启）守护进程以应用：

```bash
veles daemon start      # or: veles daemon restart
```

手动编写该块的效果相同。用 `veles channel add` 把令牌存入钥匙串，或在块中写成 `bot_token = "…"`；如果缺少令牌，守护进程会拒绝启动，并指出用于修复的命令。

## 方案 B——运行独立网关

如果你更倾向于使用独立进程（而非内置于守护进程的频道），运行：

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...   # or pass --secret
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

`veles channel run --channel telegram` 在模块缺失时会先安装它。

## 管理聊天会话

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## 聊天中的智能体模式

`/mode` 切换聊天的智能体模式：`default`（智能体直接回答，与切换前相同）、`auto`
（对每条消息决定是否先做计划）、`planning`（只做计划，不做任何修改）和 `writing`
（使用工具直接执行）。当前模式会打勾。所选模式在守护进程重启前有效。模式的状态行
（例如 *auto → plan*）显示在回答上方。

`/goal <任务>` 在聊天中运行一个目标。智能体会询问需要了解的信息，并展示将要执行的
计划。你回复 `yes` 后，它会自行工作，每完成一步发送一行进度，直到目标达成或预算
用尽。审批请求仍以按钮形式发来。`/goal` 显示进度，`/goal cancel` 在当前步骤后
停止，`/goal resume` 继续已停止的目标。

当智能体需要只有你能提供的信息时，它会在聊天中提问。点选一个建议的回答，或输入你
自己的回答。如果五分钟内没有回复，它会按最合理的假设继续，并说明做了什么假设。

`/settings` 在一条消息中显示模型（由守护进程的配置固定）、该聊天的会话、其 token 用量以及模式按钮。`/tokens` 显示自守护进程启动以来该会话的 token 用量；`/context` 显示模型上下文窗口的占用程度。

## 多模态限制

目前发送**照片或语音消息**会返回一条“未配置”的提示。Veles 定义了 `VisionAdapter` / STT 适配器协议以及一个注册表（`modules/vision.py`、`modules/stt.py`），但**没有任何具体适配器随附发布，也没有在守护进程启动时注册任何适配器**，所以图像和音频暂时不会被分析。文本聊天功能完整可用。参见[提供方参考](../reference/providers.md#multimodal-status-vision--speech-to-text)。
