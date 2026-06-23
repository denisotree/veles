# প্রোজেক্ট মেমরি ও লার্নিং লুপ

> 🌐 **ভাষা:** [English](../../en/explanation/project-memory-and-learning-loop.md) · [Русский](../../ru/explanation/project-memory-and-learning-loop.md) · **বাংলা**

Veles-এর সংজ্ঞায়ক বৈশিষ্ট্য হলো এটি প্রতি প্রোজেক্টে **মনে রাখে** এবং **শেখে**। এই
পেজে ব্যাখ্যা করা হয়েছে সেই মেমরিটি কী এবং লার্নিং লুপ কীভাবে এটিকে কার্যকর রাখে।

## মেমরি একটি স্ট্রাকচারড আর্টিফ্যাক্ট

প্রোজেক্ট মেমরি থাকে `<project>/.veles/`-এ — `memory.db` (SQLite, সত্যের উৎস)
এবং একটি human-readable `.veles/memory/` ট্রি (rendered insight views,
session digests, proposals, একটি system-ops journal)। এটি **আপনার কন্টেন্ট থেকে আলাদা**
এবং যেকোনো লেআউটের (wiki, notes, বা bare) অধীনে অভিন্নভাবে কাজ করে। এটি একটি চ্যাট
ট্রান্সক্রিপ্টের গাদা নয় — এটি স্ট্রাকচারড স্তরের একটি সেট:

- **Session log** — প্রতিটি কথোপকথন, প্রতি টার্নে একটি row, full-text indexed।
- **Rules** — সংক্ষিপ্ত নির্দেশ যা এজেন্টের অনুসরণ করা উচিত (`format`, `do`, `don't`,
  `preference`), stable system prompt-এ inject করা।
- **Insights** — sessions থেকে নিষ্কাশিত শিক্ষা। SQL row-টি canonical
  (recall, aging, এবং dedup এর উপর কাজ করে); মানুষ ও exports-এর জন্য একটি markdown view
  `.veles/memory/insights/`-এ render করা হয়।
- **Project tree map** — একটি cached, semantically-tagged ফাইল ম্যাপ যাতে এজেন্ট
  পুরো ট্রি নয়, ৩–৫টি প্রাসঙ্গিক ফাইল পড়ে।
- **Skill ও tool registries** — telemetry সহ (use/success/error counts) যা
  ranking ও dedup ব্যবহার করে।

দেখুন [প্রোজেক্ট লেআউট](../reference/project-layout.md#project-memory-velesmemorydb)-এ টেবিল তালিকা।

## Recall: ছোট কন্টেক্সট, প্রয়োজন অনুযায়ী টানা

`AGENTS.md` ইচ্ছাকৃতভাবে ছোট। আপনি যখন কিছু জিজ্ঞাসা করেন, Veles কেবল প্রাসঙ্গিক যা তা-ই
টেনে আনে: মিলে যাওয়া অতীত টার্ন (full-text + ঐচ্ছিক vector reranking),
প্রযোজ্য rules ও insights, এবং project-tree ম্যাপ যে ফাইলগুলোকে সর্বোচ্চ স্কোর দেয়।
এটি প্রতিটি মডেল কলকে সবকিছু গাদা করার বদলে কেন্দ্রীভূত ও সাশ্রয়ী রাখে।

## লার্নিং লুপ

অভিজ্ঞতা তিনটি মেকানিজমের মাধ্যমে টেকসই জ্ঞানে পরিণত হয়:

### Insights — শিক্ষা ধরে রাখা
একটি run-এর পর, একটি extractor মনে রাখার যোগ্য জিনিস খোঁজে: সুস্পষ্ট "remember
X" / "never Y" feedback, এবং tool-error→recovery প্যাটার্ন (একটি ব্যর্থতা যার পরে একটি
fix)। এটি এগুলোকে insights ও rules-এ পরিশোধিত করে যাতে একই ভুল পুনরাবৃত্ত না হয়।

### Curator — sessions একত্রীকরণ
Curator পুরোনো sessions-কে টেকসই মেমরিতে পরিশোধিত করে: SQL insights ও rules
সর্বদা; অতিরিক্তভাবে একটি `wiki/sessions/` পেজ যখন প্রোজেক্টের লেআউট
wiki engine সক্রিয় করে। এটি idle/post-turn timers-এ চলে, অথবা `veles curate` দিয়ে প্রয়োজন অনুযায়ী।

### Dreaming — ব্যাকগ্রাউন্ড রক্ষণাবেক্ষণ
`veles dream` (এবং daemon যখন idle) insights নিষ্কাশন করে, skills ও insights
deduplicate করে, promotions প্রস্তাব করে, এবং (একটি wiki layout-এর অধীনে) wiki lint করে —
আপনাকে ব্লক না করে মেমরিকে তাজা রেখে। আরও গভীর LLM পাসের জন্য `--include-consolidation` যোগ করুন।

## কন্টেক্সট কম্প্রেশন

দীর্ঘ কথোপকথন একটি sliding-window compressor দিয়ে মডেলের কন্টেক্সট সীমার নিচে রাখা
হয়: in-memory history যখন একটি token threshold পার করে, মধ্যভাগ একটি সস্তা routed model দিয়ে
সারাংশ করা হয় এবং `.veles/memory/sessions/`-এ সংরক্ষিত সারাংশের একটি pointer দিয়ে প্রতিস্থাপিত
করা হয়। সম্পূর্ণ history সর্বদা `memory.db`-তে থেকে যায় — কেবল in-memory window
কম্প্রেস করা হয়, তাই এটি disk-এ lossless।

## এটি কেন গুরুত্বপূর্ণ

যেহেতু মেমরি স্ট্রাকচারড এবং লুপ ধারাবাহিকভাবে চলে, একটি Veles প্রোজেক্ট
**যত বেশি ব্যবহার করবেন তত বেশি কার্যকর** হয় — এটি আপনার কনভেনশন শেখে, পুনরাবৃত্ত
ভুল এড়ায়, এবং উত্তরগুলোকে এটি বাস্তবে যা দেখেছে তার উপর ভিত্তি করে।
