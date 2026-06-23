# 如何接入 Telegram 频道

> 🌐 **语言：** [English](../../en/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · **简体中文**

从 Telegram 与 Veles 项目对话。频道是一个网关，它把消息转发给[守护进程](run-as-daemon.md)，并将回复流式返回。每个聊天都拥有自己独立的对话会话。

## 前置条件

- 一个正在运行的守护进程（参见[作为守护进程运行](run-as-daemon.md)）。
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

重启守护进程以应用：

```bash
veles daemon restart
```

## 方案 B——运行独立网关

如果你更倾向于使用独立进程（而非内置于守护进程的频道），运行：

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## 管理聊天会话

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## 多模态限制

目前发送**照片或语音消息**会返回一条“未配置”的提示。Veles 定义了 `VisionAdapter` / STT 适配器协议以及一个注册表（`modules/vision.py`、`modules/stt.py`），但**没有任何具体适配器随附发布，也没有在守护进程启动时注册任何适配器**，所以图像和音频暂时不会被分析。文本聊天功能完整可用。参见[提供方参考](../reference/providers.md#multimodal-status-vision--speech-to-text)。
