# লেআউট প্যাক ও LLM-Wiki

> 🌐 **ভাষা:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · **বাংলা** · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

একটি **লেআউট প্যাক** নির্ধারণ করে একটি প্রোজেক্টের *user content* কীভাবে সংগঠিত হবে — কোন
ডিরেক্টরিগুলো থাকবে, এজেন্ট কোনগুলোতে লিখতে পারবে, এবং এটি কোন অপারেশন অফার করে। ডিফল্ট হলো
**`bare`**, যা আপনার ডিরেক্টরিতে `.veles/` ও `AGENTS.md` ছাড়া কিছুই যোগ করে না।
**LLM-Wiki** এক্সটেনশন রেজিস্ট্রির একটি অপশন, Veles-এর কোনো কোর নীতি **নয়**।

## একটি লেআউট প্যাক কী

একটি লেআউট প্যাক হলো একটি ডিরেক্টরি যেখানে একটি `layout.toml` manifest থাকে (সাথে ঐচ্ছিক
skill ও template ফাইল)। manifest ঘোষণা করে:

- **Writable zones** — যে ডিরেক্টরিগুলোতে এজেন্ট কন্টেন্ট লিখতে পারে
  (প্রতিটি `write_file`-এ প্রয়োগ করা হয়)।
- **Read-only zones** — যে উপাদান এজেন্ট পড়ে কিন্তু কখনো পরিবর্তন করে না।
- **Operations** — নামকরণকৃত ওয়ার্কফ্লো, প্যাকের ভেতরে skills হিসেবে শিপ করা হয়।
- **Scaffold** (`[layout.scaffold]`) — `veles init` কী তৈরি করে: ডিরেক্টরি
  এবং একটি ঐচ্ছিক `AGENTS.md` template (`{name}` প্রতিস্থাপিত হয়)।
- **Engines** (`[layout.engines]`) — প্যাক কোন কন্টেন্ট machinery
  চায়। engine সরবরাহ করে একটি module (রেজিস্ট্রির `wiki` module `wiki` সরবরাহ করে)।
  এটি ছাড়া প্রোজেক্টে কোনো wiki tools, কোনো wiki recall, কোনো INDEX injection থাকে না।
- **Context file** (`context_file`) — একটি ফাইল যা এজেন্টের stable system prompt-এ
  inject করা হয় (LLM-Wiki `INDEX.md` ব্যবহার করে)।

## উপলব্ধ প্যাক

| Pack | কোথা থেকে | `veles init --layout <name>` কী তৈরি করে |
|---|---|---|
| `bare` *(ডিফল্ট)* | বিল্টইন | কোনো কন্টেন্ট scaffold-ই নেই — কোড রিপোজিটরি ও মুক্ত-ধারার কাজের জন্য। প্রোজেক্ট রুটের ভেতরে writes অনুমোদনপ্রবণ (তবুও trust ladder-এর অধীন)। |
| `llm-wiki` | রেজিস্ট্রি (`public:official/llm-wiki`, সাথে `wiki` module আনে) | [Karpathy-style LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (raw, কনভেনশন অনুযায়ী read-only — প্রয়োগ করা হয় না), `wiki/` (agent-writable), prompt-এ inject করা `INDEX.md`, `ingest`/`query`/`lint`/`organize`/`structure_design` skills, wiki engine চালু, `veles add` ও `/wiki`। লেআউট-ঘোষিত একটি behavioural prompt (`templates/behaviour.md`) sources/wiki শৃঙ্খলা এবং migration/log-patch নিয়ম বহন করে। |
| `notes` | রেজিস্ট্রি (`public:official/notes`) | একটিমাত্র সমতল `notes/` ডিরেক্টরি যেখানে এজেন্ট লেখে। কোনো wiki machinery নেই। |

টার্মিনালে `veles init` জিজ্ঞেস করে কোন প্যাক ব্যবহার করবেন (ইনস্টল করা প্যাক এবং আপনার
রেজিস্ট্রিগুলোর প্যাক); ইনস্টল না থাকা প্যাক বেছে নিলে ইনস্টলের প্রস্তাব আসে।
`veles registry install llm-wiki` আগেভাগে ইনস্টল করে।

## ১.২.৩-এর আগের প্রোজেক্ট

যে প্রোজেক্টের লেআউট ইনস্টল করা নেই (আপগ্রেডের পর একটি `llm-wiki` প্রোজেক্ট, বা `layout` key
ছাড়া প্রোজেক্ট — এগুলো সবই wiki প্রোজেক্ট ছিল) সেটিও খোলে। টার্মিনালে `veles` ও
`veles run` একটিমাত্র নিশ্চিতকরণে প্যাকটি (এর প্রয়োজনীয় engine সহ) ইনস্টলের প্রস্তাব দেয়;
অন্যত্র — daemon, চ্যানেল, অন্য verb-এ — Veles ইনস্টল কমান্ডটি একবার প্রিন্ট করে এবং wiki ছাড়াই
চলে। `wiki/`-এর কিছুই স্পর্শ করা হয় না।

## কাস্টম লেআউট

`~/.veles/layouts/<name>/layout.toml` (user-global) বা
`<project>/.veles/layouts/<name>/`-এ (project-local; একই নামের user ও builtin
প্যাককে ছায়া দেয়) একটি প্যাক রাখুন এবং `veles init --layout <name>` পাস করুন। কপি করার জন্য
রেজিস্ট্রির `notes` প্যাক হলো ন্যূনতম উদাহরণ। যে প্যাক এমন engine চায় যা কোনো ইনস্টল করা
module সরবরাহ করে না, সেও একই ইনস্টল প্রস্তাব পায়। আপনি `AGENTS.md`-এ কনভেনশনও বর্ণনা করতে পারেন — লেআউট
zones প্রয়োগ করে, AGENTS.md আচরণ পরিচালনা করে।

## এটি যা *নয়*

লেআউট কেবল **আপনার কন্টেন্ট** পরিচালনা করে। Veles-এর নিজস্ব প্রোজেক্ট মেমরি —
`memory.db` এবং `.veles/memory/` আর্টিফ্যাক্ট ট্রি (insights, session
digests, proposals, system-ops journal) — system-side এবং যেকোনো লেআউটের অধীনে
অভিন্নভাবে কাজ করে। লেআউট পরিবর্তন কখনো learning
loop, sessions, বা registries স্পর্শ করে না। দেখুন [আর্কিটেকচার](architecture.md) এবং
[প্রোজেক্ট লেআউট](../reference/project-layout.md)।
