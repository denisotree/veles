# মাল্টি-এজেন্ট অর্কেস্ট্রেশন

> 🌐 **ভাষা:** [English](../../en/explanation/multi-agent-orchestration.md) · [简体中文](../../zh-CN/explanation/multi-agent-orchestration.md) · [繁體中文](../../zh-TW/explanation/multi-agent-orchestration.md) · [日本語](../../ja/explanation/multi-agent-orchestration.md) · [한국어](../../ko/explanation/multi-agent-orchestration.md) · [Español](../../es/explanation/multi-agent-orchestration.md) · [Français](../../fr/explanation/multi-agent-orchestration.md) · [Italiano](../../it/explanation/multi-agent-orchestration.md) · [Português (BR)](../../pt-BR/explanation/multi-agent-orchestration.md) · [Português (PT)](../../pt-PT/explanation/multi-agent-orchestration.md) · [Русский](../../ru/explanation/multi-agent-orchestration.md) · [العربية](../../ar/explanation/multi-agent-orchestration.md) · [हिन्दी](../../hi/explanation/multi-agent-orchestration.md) · **বাংলা** · [Tiếng Việt](../../vi/explanation/multi-agent-orchestration.md)

জটিল কাজের জন্য, Veles একটি টাস্ককে একটিমাত্র কন্টেক্সটে সবকিছু করার বদলে একটি **manager**
এবং বিশেষায়িত **worker** সাব-এজেন্টের মধ্যে ভাগ করতে পারে। এই পেজে মডেলটি ব্যাখ্যা করা হয়েছে;
এটি চালু করতে দেখুন
[manager mode](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt)।

## আকৃতি

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- **manager** বিভাজন পরিকল্পনা করে এবং সমন্বয় করে — কিন্তু সে নিজে চূড়ান্ত
  deliverable লেখে **না**।
- **Workers**-এর role-নির্দিষ্ট system prompts থাকে: `explorer` সংগ্রহ করে, `writer`
  উত্তর তৈরি করে, `advisor` পর্যালোচনা করে। সেটটি সম্প্রসারণযোগ্য।
- শেষে, manager মেমরিতে একটি সংক্ষিপ্ত রিপোর্ট লেখে।

## কোনো telephone game নেই

একটি মূল নিয়ম: মধ্যবর্তী আর্টিফ্যাক্টগুলো synthesiser-এর কাছে **হুবহু** পৌঁছায়, manager-এর
paraphrase হিসেবে নয়। একজন explorer-এর findings সরাসরি writer-কে দেওয়া হয়, তাই
সারাংশের শৃঙ্খলের মধ্য দিয়ে বিস্তারিত হারিয়ে যায় না। এটিই বিভাজনকে গুণ যোগ করায়, পাতলা
করার বদলে।

## কেন "manager কখনো লেখে না"

যদি coordinator উত্তরটিও লিখত, তবে সে workers-কে শর্টকাট করার এবং বিশেষায়নের সুবিধা হারানোর
প্রলোভনে পড়ত। synthesis একটি নিবেদিত `writer`-এ রাখা (হুবহু inputs দিয়ে খাওয়ানো)
শ্রমবিভাজন প্রয়োগ করে। Veles এটিকে একটি runtime গ্যারান্টি বানায়।

## কখন এটি সাহায্য করে — আর কখন করে না

বিস্তৃত বা বহুমুখী কাজের জন্য বিভাজন লাভজনক (এই কোডবেস অডিট করো, এই প্রশ্নটি কয়েকটি কোণ
থেকে গবেষণা করো)। একটি দ্রুত, single-context অনুরোধের জন্য এটি কেবল overhead যোগ করে — যে
কারণে manager mode **সুস্পষ্ট opt-in**, ডিফল্টে বন্ধ (`veles run --manager` বা
`VELES_MANAGER_MODE=1`)।
