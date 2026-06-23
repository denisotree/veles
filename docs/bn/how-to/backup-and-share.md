# একটি প্রজেক্ট কীভাবে ব্যাকআপ ও শেয়ার করবেন

> 🌐 **ভাষা:** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · [Italiano](../../it/how-to/backup-and-share.md) · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · **বাংলা** · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

Veles প্রজেক্টগুলো পোর্টেবল। ব্যাকআপ বা migration-এর জন্য একটি প্রজেক্টকে একটিমাত্র `.tar.gz`
bundle-এ export করুন, অথবা আপনার ডেটা ফাঁস না করে শেয়ার করার জন্য একটি sanitised template export করুন।

## পূর্ণ ব্যাকআপ

পুরো প্রজেক্ট (`.veles/` + `AGENTS.md`) প্যাক করে, runtime ephemera (lock, budget state) বাদ দিয়ে:

```bash
veles export full ./my-project-backup.tar.gz
```

এটি যেকোনো জায়গায় restore করুন:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

একটি পূর্ণ bundle-এ আপনার `memory.db` (sessions, insights) অন্তর্ভুক্ত থাকে, তাই এটিকে
ব্যক্তিগত ডেটার মতো বিবেচনা করুন।

## শেয়ারযোগ্য template

শুধুমাত্র পুনঃব্যবহারযোগ্য কাঠামো প্যাক করে — schema, skills, modules, এবং non-session
wiki পেজ। এটি `memory.db`, `sources/`, `sessions/`, trust grant **বাদ দেয়**, এবং টেক্সট
PII-redact করে:

```bash
veles export template ./my-template.tar.gz
```

Template-টি একজন সহকর্মীকে দিন; তিনি এটি `veles import` করেন এবং আপনার কথোপকথনের ইতিহাস বা কাঁচা
source ছাড়াই আপনার কাঠামো ও skills পান।

## কোনটি ব্যবহার করবেন

| লক্ষ্য | কমান্ড |
|---|---|
| একটি প্রজেক্ট অক্ষত রেখে ব্যাকআপ / সরানো | `veles export full` |
| কাঠামো + skills শেয়ার করা, ডেটা নয় | `veles export template` |
