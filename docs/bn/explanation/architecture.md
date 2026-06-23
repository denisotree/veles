# আর্কিটেকচার ওভারভিউ

> 🌐 **ভাষা:** [English](../../en/explanation/architecture.md) · [简体中文](../../zh-CN/explanation/architecture.md) · [繁體中文](../../zh-TW/explanation/architecture.md) · [日本語](../../ja/explanation/architecture.md) · [한국어](../../ko/explanation/architecture.md) · [Español](../../es/explanation/architecture.md) · [Français](../../fr/explanation/architecture.md) · [Italiano](../../it/explanation/architecture.md) · [Português (BR)](../../pt-BR/explanation/architecture.md) · [Português (PT)](../../pt-PT/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md) · [العربية](../../ar/explanation/architecture.md) · [हिन्दी](../../hi/explanation/architecture.md) · **বাংলা** · [Tiếng Việt](../../vi/explanation/architecture.md)

এই পেজে ব্যাখ্যা করা হয়েছে Veles আসলে *কী* এবং এর অংশগুলো কীভাবে একসাথে কাজ করে, যাতে বাকি
ডকুমেন্টেশন বোধগম্য হয়। আনুষ্ঠানিক প্রোডাক্ট ভিশনের জন্য রিপোর রুটে থাকা `VISION.md`
দেখুন।

## ডিজাইনের উদ্দেশ্য

Veles ইচ্ছাকৃতভাবে **মিনিমালিস্ট এবং পরিচ্ছন্নভাবে বিভাজিত** — single-responsibility
মডিউল, কোনো god-file নেই। এটি **local-first**: আপনি এটিকে আপনার মেশিনের একটি ডিরেক্টরির
বিরুদ্ধে চালান, এবং এটি সেখানেই নিজের স্ট্রাকচারড মেমরি রাখে।

## পাঁচটি স্তম্ভ (কোর)

কোরের প্রতিটি জিনিস এই পাঁচটি কাজের যেকোনো একটি করে:

1. **প্রোজেক্ট মেমরি** — একটি স্ট্রাকচারড আর্টিফ্যাক্ট (আপনার কন্টেন্ট থেকে আলাদা) যা
   সেশন লগ, শেখা rules/insights, একটি প্রোজেক্ট ফাইল ম্যাপ, এবং telemetry সহ skill/tool
   রেজিস্ট্রি ধারণ করে। দেখুন [প্রোজেক্ট মেমরি ও লার্নিং লুপ](project-memory-and-learning-loop.md)।
2. **লার্নিং লুপ** — curator, insight extractor, এবং dreaming যা মেমরিকে তাজা রাখে এবং
   অভিজ্ঞতাকে পুনঃব্যবহারযোগ্য rules-এ রূপান্তরিত করে।
3. **মাল্টি-এজেন্ট অর্কেস্ট্রেশন** — একটি ম্যানেজার যা একটি টাস্ককে বিভাজিত করে এবং
   বিশেষায়িত workers স্পন করে। দেখুন [মাল্টি-এজেন্ট অর্কেস্ট্রেশন](multi-agent-orchestration.md)।
4. **একটি provider protocol** — অনেক LLM ব্যাকএন্ডের (cloud, local,
   CLI delegation) উপর একটিমাত্র ইন্টারফেস। দেখুন [providers](../reference/providers.md)।
5. **মিনিমাল tools ও skills** — একটি ছোট বুটস্ট্র্যাপ সেট যা **জমা হয়** যখন Veles
   নিজের tools লেখে এবং পুনরাবৃত্ত প্রক্রিয়াগুলোকে skills-এ আনুষ্ঠানিক রূপ দেয়। দেখুন
   [skills ও tools](skills-and-tools.md)।

## বাকি সবকিছু একটি ঐচ্ছিক মডিউল

Gateways/channels, daemon, scheduler, TUI, vision/STT — সবগুলোই
**pluggable** এবং কেবল ব্যবহৃত হলেই লোড হয়। Veles ন্যূনতম সেট নিয়ে বুট করে এবং প্রয়োজন
অনুযায়ী সম্প্রসারিত হয়, ফলে একটি সাধারণ `veles run` সাধারণই থেকে যায়।

## একটি টার্ন কীভাবে প্রবাহিত হয়

```
your prompt
   │
   ▼
context: AGENTS.md (small) + on-demand recall from project memory
   │
   ▼
agent loop  ──►  provider (routed per task)  ──►  tool calls
   │                                               │
   │            (trust ladder gates sensitive tools)
   ▼
response  ──►  saved to memory  ──►  learning triggers (insights, curator)
```

কন্টেক্সট ফাইল (`AGENTS.md`) ইচ্ছাকৃতভাবে ছোট রাখা হয়; আনুষঙ্গিক জ্ঞান
(wiki pages, প্রোজেক্ট ফাইল ম্যাপ, প্রাসঙ্গিক অতীত টার্ন) **প্রয়োজন অনুযায়ী** টেনে আনা হয়,
আগে থেকে গাদা করে ফেলা হয় না।

## state কোথায় থাকে

- `<project>/.veles/` — এই প্রোজেক্টের মেমরি, config, local skills/tools।
- `~/.veles/` — user-global config, cross-project skills/tools, caches, trust।
- `<project>/AGENTS.md`, `wiki/`, `sources/` — আপনার কন্টেন্ট (LLM-Wiki লেআউট)।

দেখুন [প্রোজেক্ট লেআউট](../reference/project-layout.md)।

## এক লুপে মাল্টি-প্রোজেক্ট

একটিমাত্র agent loop অনেক প্রোজেক্টকে সার্ভ করে। প্রতিটি প্রোজেক্ট তার নিজস্ব কন্টেক্সট ও
মেমরি সহ নিজের ডিরেক্টরি পায়; `AGENTS.md` কে `CLAUDE.md`/`GEMINI.md`-এ symlink করা হয় যাতে
সেখানে চালু করা একটি external CLI একই কন্টেক্সট দেখতে পায়। দেখুন
[একাধিক প্রোজেক্ট](../how-to/multi-project-and-subprojects.md)।

## surfaces

- **CLI** (`veles run`, `veles add`, …) — one-shot এবং স্ক্রিপ্টেড ব্যবহার।
- **TUI** (`veles tui`) — [run modes](modes.md) সহ ইন্টারঅ্যাক্টিভ REPL।
- **Daemon + channels** — headless API, Telegram, scheduled jobs।

তিনটিই একই কোর agent loop চালায়।
