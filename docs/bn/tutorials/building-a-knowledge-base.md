# একটি knowledge base তৈরি করা

> 🌐 **ভাষা:** [English](../../en/tutorials/building-a-knowledge-base.md) · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · [日本語](../../ja/tutorials/building-a-knowledge-base.md) · [한국어](../../ko/tutorials/building-a-knowledge-base.md) · [Español](../../es/tutorials/building-a-knowledge-base.md) · [Français](../../fr/tutorials/building-a-knowledge-base.md) · [Italiano](../../it/tutorials/building-a-knowledge-base.md) · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · [Português (PT)](../../pt-PT/tutorials/building-a-knowledge-base.md) · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · [العربية](../../ar/tutorials/building-a-knowledge-base.md) · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · **বাংলা** · [Tiếng Việt](../../vi/tutorials/building-a-knowledge-base.md)

এই টিউটোরিয়ালে আপনি একটি Veles প্রজেক্টকে একটি জীবন্ত knowledge base-এ পরিণত করবেন: কয়েকটি source ingest করবেন, Veles-কে wiki page লিখতে দেবেন, প্রশ্ন করবেন, এবং যা শিখলেন তা একত্রিত করবেন। এটাই হলো ডিফল্ট **LLM-Wiki** workflow। প্রায় ১৫ মিনিট।

এর আগে আপনার [Getting started](getting-started.md) শেষ করা থাকা উচিত।

## ধারণাটি

একটি Veles প্রজেক্টের দুটি content zone থাকে:

- `sources/` — কাঁচা, অপরিবর্তনীয় উপাদান যা আপনি দেন (agent-এর জন্য read-only)।
- `wiki/` — agent-এর নিজস্ব, LLM-generated জ্ঞান (একমাত্র এই zone-এ-ই এটি content লেখে)।

আপনি source খাওয়ান; Veles সেগুলোকে linked wiki page-এ সংক্ষিপ্ত করে; আপনি স্বাভাবিক ভাষায় wiki-তে query করেন। কেন তা জানতে দেখুন [layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)।

## ১. একটি source ingest করা

`veles add` একটি ফাইল বা URL পড়ে এবং তার সারসংক্ষেপসহ একটি wiki page লেখে:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

প্রতিটি `add` `wiki/`-এর অধীনে একটি page তৈরি করে এবং তা wiki graph-এ লিঙ্ক করে।

## ২. wiki-কে বাড়তে দেখা

যা লেখা হলো তা দেখুন:

```bash
ls wiki/concepts wiki/entities wiki/sources
```

Page-গুলো একে অপরকে cross-reference করে। on-demand `wiki/INDEX.md` ক্যাটালগ একটি map রাখে যা agent প্রয়োজন হলে লোড করে (এক বিশাল monolithic context dump নয়)।

## ৩. প্রশ্ন করা

এবার স্বাভাবিক ভাষায় আপনার knowledge base-এ query করুন:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles wiki-তে খোঁজে, প্রাসঙ্গিক page পড়ে, এবং উত্তর দেয় — শুধু তার training data নয়, বরং আপনি যা ingest করেছেন তার ভিত্তিতে।

ইন্টারঅ্যাক্টিভ আলোচনার জন্য TUI-তে একই কাজ করুন (`veles tui`)।

## ৪. session একত্রিত করা

কাজ করতে করতে কথোপকথন জমা হয়। সেগুলোকে স্থায়ী wiki page-এ সংকুচিত করতে এবং শিক্ষা বের করতে curator চালান:

```bash
veles curate
```

এটি `wiki/sessions/` page লেখে এবং প্রজেক্টের insight ও rules আপডেট করে। Veles সময়ের সঙ্গে এটি স্বয়ংক্রিয়ভাবেও করে — দেখুন [project memory & the learning loop](../explanation/project-memory-and-learning-loop.md)।

## ৫. wiki-কে সুস্থ রাখা

সময়ের সঙ্গে page বাসি হয়ে যায় বা orphan হয়ে পড়ে। `lint` অপারেশন সেগুলো খুঁজে বের করে:

```bash
veles run "lint"
```

(`ingest`, `query`, এবং `lint` হলো LLM-Wiki layout-এর সঙ্গে বান্ডিল করা skill; আপনি সেগুলোকে `veles run "<operation>"` দিয়ে invoke করেন অথবা agent-কে কল করতে দেন।)

## আপনি যা তৈরি করলেন

একটি স্ব-সংগঠিত knowledge base: source ভেতরে যায়, linked wiki page বেরিয়ে আসে, স্বাভাবিক ভাষায় query করা যায়, এবং Veles যত একত্রিত করে তত পরিপাটি হয়। এখান থেকে:

- **[Manage skills, tools, and modules](../how-to/manage-skills-and-tools.md)** — Veles-কে পুনঃব্যবহারযোগ্য workflow শেখান।
- **[Run as a daemon](../how-to/run-as-daemon.md)** + **[connect Telegram](../how-to/connect-telegram.md)** — আপনার ফোন থেকে knowledge base-এর সঙ্গে কথা বলুন।
- **[Multiple projects & subprojects](../how-to/multi-project-and-subprojects.md)** — অনেক knowledge base পর্যন্ত scale করুন।
