# TUI কীবাইন্ডিং ও slash কমান্ড

> 🌐 **ভাষা:** [English](../../en/reference/tui.md) · [Русский](../../ru/reference/tui.md)

`veles tui` (অথবা শুধু `veles`) ইন্টারঅ্যাক্টিভ REPL খোলে। এটি একটি scrollback চ্যাট — সঙ্গে থাকে মাল্টি-লাইন composer, একটি status bar এবং একটি collapsible inspector।

## কীবাইন্ডিং

| কী | কাজ |
|---|---|
| `Ctrl+D` | বের হওয়া |
| `Ctrl+C` | শেষ assistant রিপ্লাই কপি করা; ১.৫ সেকেন্ডের মধ্যে দুবার চাপলে বের হয়ে যায় |
| `Ctrl+V` | ক্লিপবোর্ড থেকে পেস্ট করা |
| `Ctrl+Shift+C` / `⌘C` | বর্তমান নির্বাচন কপি করা (OSC52)। macOS Terminal.app-এ native drag-select + ⌘C সরাসরি কাজ করে |
| `Ctrl+I` | inspector টগল করা (reasoning, tool activity, token/error log) |
| `Ctrl+R` | session picker খোলা (পুরোনো session পুনরায় চালু করা) |
| `Ctrl+T` | theme picker খোলা |
| `Shift+Tab` | run mode পরিবর্তন: `auto → planning → writing → goal` |
| `Tab` | slash-command completion ঘোরানো |
| `Up` / `Down` | history (এবং queue-এ থাকা prompt বের করা) |

Run mode-গুলো ব্যাখ্যা করা হয়েছে [Run modes](../explanation/modes.md)-এ।

## Slash কমান্ড

composer-এ `/` টাইপ করুন; `Tab` দিয়ে completion হয়। নিবন্ধিত কমান্ডগুলো হলো:

| কমান্ড | উদ্দেশ্য |
|---|---|
| `/help` | উপলব্ধ কমান্ডের তালিকা |
| `/quit`, `/q`, `/exit` | REPL থেকে বের হওয়া |
| `/clear` | চ্যাট লগ পরিষ্কার করা |
| `/model` | model picker খোলা |
| `/mode` | run mode পরিবর্তন (auto/planning/writing/goal) |
| `/session` | session picker খোলা (resume) |
| `/save` | বর্তমান session সংরক্ষণ / নামকরণ করা |
| `/history` | session history দেখানো |
| `/tokens` | token ব্যবহার (in / out / per-turn / per-session) |
| `/context` | লিমিটের তুলনায় বর্তমান context-এর আকার |
| `/status` | স্ন্যাপশট: model, provider, mode, session, busy, queue |
| `/insights` | প্রজেক্টের জন্য শেখা insight দেখানো |
| `/rules` | প্রজেক্টের rules digest দেখানো |
| `/schema` | `AGENTS.md` যাচাই / সংশোধন করা |
| `/wiki` | সক্রিয় layout-এর জন্য wiki অপারেশন |
| `/daemon` | daemon কন্ট্রোল প্যানেল খোলা (project → daemons → channels) |

> আপনি TUI সরাসরি চালু করুন বা অন্য কোনো screen থেকে এটি push করুন — slash সেট একই থাকে। Channel-গুলো (যেমন Telegram) তাদের নিজস্ব, আলাদা কমান্ড সেট প্রকাশ করে।

## Theme

বিল্ট-ইন theme: `everforest` (ডিফল্ট), `dracula`, `gruvbox`, `tokyo-night`, `catppuccin`। `Ctrl+T`, `veles tui --theme <name>`, অথবা `~/.veles/config.toml`-এ `[user] tui_theme` দিয়ে একটি বেছে নিন।
