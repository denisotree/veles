# How to connect a Telegram channel

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/connect-telegram.md)

Talk to a Veles project from Telegram. A channel is a gateway that forwards
messages to a [daemon](run-as-daemon.md) and streams replies back. Each chat gets
its own conversation session.

## Prerequisites

- A running daemon (see [run as a daemon](run-as-daemon.md)).
- A Telegram bot token from [@BotFather](https://t.me/BotFather).

## Option A — attach via the wizard (recommended)

From the project, run the channel wizard; it writes the config and stores the
token in the OS keychain:

```bash
veles channel add --channel telegram
```

Or attach to a specific named daemon session:

```bash
veles channel add --channel telegram --session api
```

You can also do this from the [daemon picker TUI](run-as-daemon.md#the-daemon-picker-tui):
press `c` on a daemon and follow the prompts.

This produces a config block:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

The **whitelist** restricts who the bot answers (Telegram `@username` or numeric
user id). Leave it empty to answer everyone — not recommended, since every
message spends model tokens.

Restart the daemon to apply:

```bash
veles daemon restart
```

## Option B — run a standalone gateway

If you prefer a separate process (instead of the in-daemon channel), run:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## Manage chat sessions

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Multimodal limitation

Sending a **photo or voice message** currently returns a "not configured" notice.
Veles defines `VisionAdapter` / STT adapter protocols and a registry
(`modules/vision.py`, `modules/stt.py`), but **no concrete adapter ships and none
is registered at daemon startup**, so images and audio aren't analysed yet. Text
chat works fully. See the [providers reference](../reference/providers.md#multimodal-status-vision--speech-to-text).
