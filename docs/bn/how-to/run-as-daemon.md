# Veles কীভাবে ডিমন হিসেবে চালাবেন

> 🌐 **ভাষা:** [English](../../en/how-to/run-as-daemon.md) · [简体中文](../../zh-CN/how-to/run-as-daemon.md) · [繁體中文](../../zh-TW/how-to/run-as-daemon.md) · [日本語](../../ja/how-to/run-as-daemon.md) · [한국어](../../ko/how-to/run-as-daemon.md) · [Español](../../es/how-to/run-as-daemon.md) · [Français](../../fr/how-to/run-as-daemon.md) · [Italiano](../../it/how-to/run-as-daemon.md) · [Português (BR)](../../pt-BR/how-to/run-as-daemon.md) · [Português (PT)](../../pt-PT/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · [العربية](../../ar/how-to/run-as-daemon.md) · [हिन्दी](../../hi/how-to/run-as-daemon.md) · **বাংলা** · [Tiếng Việt](../../vi/how-to/run-as-daemon.md)

ডিমন হলো একটি ঐচ্ছিক দীর্ঘজীবী HTTP+WS সার্ভার যা এজেন্টকে একটি API হিসেবে প্রকাশ
করে — [চ্যানেল](connect-telegram.md) (Telegram, …), শিডিউল করা
[জব](long-running-tasks.md), এবং রিমোট/হেডলেস ব্যবহারের ভিত্তি।

## চালু ও বন্ধ করা

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` ডিট্যাচ করে এবং আপনার শেল ফেরত দেয়। একটি ফোরগ্রাউন্ড প্রসেসের জন্য (systemd
`Type=simple`, Docker, ডিবাগিং) `--foreground` দিন। bind ওভাররাইড করুন:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

ডিমনের মডেল ও প্রোভাইডার প্রজেক্ট কনফিগ থেকে আসে এবং **এর পুরো জীবনকালের জন্য
নির্দিষ্ট থাকে** — চালু করার আগে সেগুলো সেট করুন:

```toml
# <project>/.veles/config.toml
[engine]
provider = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## অথেনটিকেশন টোকেন

API ক্লায়েন্ট একটি bearer টোকেন দিয়ে অথেনটিকেট করে:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## ডিমন পিকার (TUI)

কোনো সাবকমান্ড ছাড়া `veles daemon` চালালে কন্ট্রোল প্যানেল খোলে — আপনার প্রজেক্টের
ডিমন এবং প্রতিটি ডিমনের চ্যানেলের একটি ট্রি:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

কী: `Enter` একটি ডিমনের লগ খোলে; `s`/`t`/`r` start/stop/restart; `d` delete;
`c`/`x` একটি চ্যানেল add/remove; `q` quit।

## প্রতি প্রজেক্টে একাধিক ডিমন (নামকৃত সেশন)

একটি প্রজেক্ট একসাথে ভিন্ন মডেল/পোর্টসহ একাধিক ডিমন চালাতে পারে। একটি নামকৃত সেশন
ঘোষণা করুন, তারপর এটি চালু করুন:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

প্রতিটি নামকৃত সেশনের নিজস্ব `[daemon.<name>]` কনফিগ ব্লক এবং নিজস্ব চ্যানেল আছে
(`[daemon.<name>.channels.*]`)।

## প্রজেক্ট জুড়ে ডিমন তালিকাভুক্ত করুন

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## এরপর

- [একটি Telegram চ্যানেল সংযুক্ত করুন](connect-telegram.md)
- [জব শিডিউল করুন](long-running-tasks.md)
