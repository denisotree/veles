# Veles কীভাবে daemon হিসেবে চালাবেন

> 🌐 **Languages:** [English](../../en/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · **বাংলা**

daemon হলো একটি ঐচ্ছিক দীর্ঘ-জীবী HTTP+WS সার্ভার যা এজেন্টকে একটি API হিসেবে তুলে ধরে — যা হলো [channels](connect-telegram.md) (Telegram, …), scheduled [jobs](long-running-tasks.md), এবং remote/headless ব্যবহারের ভিত্তি।

## চালু ও বন্ধ করা

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` detach হয়ে আপনার shell ফিরিয়ে দেয়। একটি foreground প্রসেসের জন্য (systemd `Type=simple`, Docker, debugging) `--foreground` পাস করুন। bind ওভাররাইড করুন:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

daemon-এর মডেল ও provider প্রকল্প কনফিগ থেকে আসে এবং **এর জীবনকালের জন্য নির্দিষ্ট** — চালু করার আগে সেগুলো সেট করুন:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## Authentication token

API client-গুলো একটি bearer token দিয়ে authenticate করে:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## daemon picker (TUI)

কোনো subcommand ছাড়াই `veles daemon` চালান control panel খুলতে — আপনার প্রকল্পের daemon-গুলো এবং প্রতিটি daemon-এর channel-গুলোর একটি tree:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Key: `Enter` একটি daemon-এর log খোলে; `s`/`t`/`r` start/stop/restart; `d` delete; `c`/`x` একটি channel add/remove করে; `q` quit।

## প্রতি প্রকল্পে একাধিক daemon (named session)

একটি প্রকল্প একসাথে ভিন্ন মডেল/পোর্টসহ একাধিক daemon চালাতে পারে। একটি named session ঘোষণা করুন, তারপর সেটি চালু করুন:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

প্রতিটি named session-এর নিজস্ব `[daemon.<name>]` কনফিগ ব্লক এবং নিজস্ব channel (`[daemon.<name>.channels.*]`) থাকে।

## প্রকল্পজুড়ে daemon-এর তালিকা

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## পরবর্তী

- [একটি Telegram channel সংযুক্ত করুন](connect-telegram.md)
- [Job schedule করুন](long-running-tasks.md)
