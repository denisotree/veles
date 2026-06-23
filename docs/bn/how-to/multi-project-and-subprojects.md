# একাধিক প্রকল্প ও subproject নিয়ে কীভাবে কাজ করবেন

> 🌐 **ভাষা:** [English](../../en/how-to/multi-project-and-subprojects.md) · [简体中文](../../zh-CN/how-to/multi-project-and-subprojects.md) · [繁體中文](../../zh-TW/how-to/multi-project-and-subprojects.md) · [日本語](../../ja/how-to/multi-project-and-subprojects.md) · [한국어](../../ko/how-to/multi-project-and-subprojects.md) · [Español](../../es/how-to/multi-project-and-subprojects.md) · [Français](../../fr/how-to/multi-project-and-subprojects.md) · [Italiano](../../it/how-to/multi-project-and-subprojects.md) · [Português (BR)](../../pt-BR/how-to/multi-project-and-subprojects.md) · [Português (PT)](../../pt-PT/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · [العربية](../../ar/how-to/multi-project-and-subprojects.md) · [हिन्दी](../../hi/how-to/multi-project-and-subprojects.md) · **বাংলা** · [Tiếng Việt](../../vi/how-to/multi-project-and-subprojects.md)

Veles একটি এজেন্ট লুপে অনেক প্রকল্প চালায়। প্রতিটি প্রকল্পের নিজস্ব মেমরি, skill, ও tool থাকে। **Subproject** হলো একটি parent-এর অধীনে nested প্রকল্প — একটি বড় monorepo বা knowledge base-কে scoped মেমরিতে ভাগ করার জন্য উপযোগী।

## Projects

Veles আপনার cwd থেকে উপরের দিকে একটি `.veles/` ডিরেক্টরি পর্যন্ত হেঁটে (`git`-এর মতো) সক্রিয় প্রকল্প খুঁজে বের করে। registry পরিচালনা করুন:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` একটি path প্রিন্ট করে, তাই আপনি একটি প্রকল্পে `cd` করতে পারেন:

```bash
cd "$(veles project switch web)"
```

`cd` ছাড়াই অন্য কোথাও থাকা একটি প্রকল্পের বিরুদ্ধে একটি command চালান:

```bash
veles run --project-root /path/to/project "..."
```

## Subprojects

একটি subproject হলো একটি parent-এর ভেতরে একটি child Veles প্রকল্প। একটি তৈরি করুন:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Veles-কে একটি বিভাজনের পরামর্শ দিতে দিন

যখন একটি প্রকল্পের wiki বাড়ে, তখন Veles থিমভিত্তিক cluster শনাক্ত করতে পারে এবং সেগুলোকে subproject হিসেবে প্রস্তাব করতে পারে:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## কখন কোনটি ব্যবহার করবেন

- **আলাদা প্রকল্প** — অসম্পর্কিত knowledge base / codebase।
- **Subproject** — একটি বৃহত্তর জিনিসের অংশ যা scoped মেমরি থেকে উপকৃত হয় কিন্তু একটি parent context শেয়ার করে।

multi-project context কীভাবে একটি monolithic dump হিসেবে নয় বরং প্রয়োজন অনুযায়ী লোড হয় তা জানতে দেখুন [architecture](../explanation/architecture.md)।
