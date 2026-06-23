# একটি Telegram channel কীভাবে যুক্ত করবেন

> 🌐 **ভাষা:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · [Español](../../es/how-to/connect-telegram.md) · [Français](../../fr/how-to/connect-telegram.md) · [Italiano](../../it/how-to/connect-telegram.md) · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · **বাংলা** · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

Telegram থেকে একটি Veles প্রজেক্টের সাথে কথা বলুন। একটি channel হলো একটি gateway যা মেসেজ একটি
[daemon](run-as-daemon.md)-এ ফরোয়ার্ড করে এবং উত্তর stream করে ফিরিয়ে আনে। প্রতিটি chat তার
নিজস্ব কথোপকথন session পায়।

## পূর্বশর্ত

- একটি চালু daemon (দেখুন [run as a daemon](run-as-daemon.md))।
- [@BotFather](https://t.me/BotFather) থেকে একটি Telegram bot token।

## বিকল্প A — wizard-এর মাধ্যমে যুক্ত করুন (প্রস্তাবিত)

প্রজেক্ট থেকে channel wizard চালান; এটি config লেখে এবং token-টি OS keychain-এ সংরক্ষণ করে:

```bash
veles channel add --channel telegram
```

অথবা একটি নির্দিষ্ট named daemon session-এ যুক্ত করুন:

```bash
veles channel add --channel telegram --session api
```

আপনি এটি [daemon picker TUI](run-as-daemon.md#the-daemon-picker-tui) থেকেও করতে পারেন:
একটি daemon-এর উপর `c` চাপুন এবং prompt অনুসরণ করুন।

এটি একটি config block তৈরি করে:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

**whitelist** নিয়ন্ত্রণ করে bot কাকে উত্তর দেবে (Telegram `@username` বা numeric user id)।
সবাইকে উত্তর দিতে এটি খালি রাখুন — যা প্রস্তাবিত নয়, কারণ প্রতিটি মেসেজ মডেল token খরচ করে।

প্রয়োগ করতে daemon restart করুন:

```bash
veles daemon restart
```

## বিকল্প B — একটি standalone gateway চালান

আপনি যদি একটি আলাদা প্রসেস পছন্দ করেন (in-daemon channel-এর পরিবর্তে), চালান:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## Chat session পরিচালনা করুন

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Multimodal সীমাবদ্ধতা

একটি **photo বা voice message** পাঠালে বর্তমানে একটি "not configured" নোটিশ ফেরত আসে।
Veles `VisionAdapter` / STT adapter protocol এবং একটি registry সংজ্ঞায়িত করে
(`modules/vision.py`, `modules/stt.py`), কিন্তু **কোনো concrete adapter ship করে না এবং daemon
startup-এ কোনোটিই register হয় না**, তাই image ও audio এখনও বিশ্লেষণ করা হয় না। Text chat
সম্পূর্ণভাবে কাজ করে। দেখুন [providers reference](../reference/providers.md#multimodal-status-vision--speech-to-text)।
