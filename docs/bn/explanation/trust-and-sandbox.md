# Trust ও sandbox

> 🌐 **ভাষা:** [English](../../en/explanation/trust-and-sandbox.md) · [简体中文](../../zh-CN/explanation/trust-and-sandbox.md) · [繁體中文](../../zh-TW/explanation/trust-and-sandbox.md) · [日本語](../../ja/explanation/trust-and-sandbox.md) · [한국어](../../ko/explanation/trust-and-sandbox.md) · [Español](../../es/explanation/trust-and-sandbox.md) · [Français](../../fr/explanation/trust-and-sandbox.md) · [Italiano](../../it/explanation/trust-and-sandbox.md) · [Português (BR)](../../pt-BR/explanation/trust-and-sandbox.md) · [Português (PT)](../../pt-PT/explanation/trust-and-sandbox.md) · [Русский](../../ru/explanation/trust-and-sandbox.md) · [العربية](../../ar/explanation/trust-and-sandbox.md) · [हिन्दी](../../hi/explanation/trust-and-sandbox.md) · **বাংলা** · [Tiếng Việt](../../vi/explanation/trust-and-sandbox.md)

Veles আপনার মেশিনে একটি স্বায়ত্তশাসিত এজেন্ট চালায়, তাই সেই এজেন্ট কী করতে পারবে তা সীমিত করে।
দুটি ব্যবস্থা একসাথে কাজ করে: সংবেদনশীল কাজের জন্য একটি **trust ladder** এবং ফাইলসিস্টেমের জন্য
একটি **sandbox**। কমান্ডগুলোর জন্য দেখুন
[security & permissions](../how-to/security-and-permissions.md)।

## Trust ladder

প্রতিটি tool সমান নয়। একটি ফাইল পড়া ক্ষতিকর নয়; কিন্তু একটি shell কমান্ড চালানো বা ডিস্কে লেখা ক্ষতিকর হতে পারে।
সংবেদনশীল tools (`run_shell`, `write_file`, `fetch_url`, …) চালানোর আগে থেমে গিয়ে জিজ্ঞাসা করে,
চারটি বিকল্প দিয়ে:

- **Once** — শুধু এই একটি call-কে অনুমতি দাও।
- **Always for this project** — একটি project-scoped grant সংরক্ষণ করো।
- **Always everywhere** — একটি user-scoped grant সংরক্ষণ করো।
- **Refuse** — এটি অস্বীকার করো।

Grant-গুলো সংরক্ষিত থাকে যাতে আপনাকে আবার জিজ্ঞাসা করা না হয়। এতে আপনি ধাপে ধাপে নিয়ন্ত্রণ পান:
একটি tool-কে একবার, একটি প্রজেক্টে, কিংবা বিশ্বব্যাপী বিশ্বাস করুন — আপনার পছন্দ, যা প্রথমবার
গুরুত্বপূর্ণ হওয়ার সময় করা হয়।

### সবসময়-নিশ্চিতকরণযোগ্য কাজ

কিছু কাজ যথেষ্ট ঝুঁকিপূর্ণ যে Veles সেগুলো **grant থাকা সত্ত্বেও** নিশ্চিত করে:
ফাইল মুছে ফেলা, URL fetch করা, একটি নতুন skill/tool/module ইনস্টল করা, একটি channel যুক্ত করা,
এবং প্রজেক্টের বাইরে লেখা। এগুলো বহির্মুখী বা ফিরিয়ে আনা কঠিন, তাই একটি স্থায়ী grant-এর নীরবে
এগুলো কভার করা উচিত নয়।

### Non-interactive নিরাপত্তা

একটি daemon, batch, বা অন্য কোনো non-TTY প্রসঙ্গে prompt দেওয়ার মতো কোনো মানুষ থাকে না, তাই Veles
ডিফল্টভাবে সংবেদনশীল কাজ **অস্বীকার** করে — বিপথগামী stdin চুপিসারে কোনো অনুমোদন ঢুকিয়ে দিতে পারে না।
ইচ্ছাকৃতভাবে তত্ত্বাবধান ছাড়া চালাতে একটি [autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass)
উইন্ডো খুলুন; প্রতিটি autopilot কাজ পর্যালোচনার জন্য লগ করা হয়।

## ফাইলসিস্টেম sandbox

একটি path guard সীমাবদ্ধ করে tools কোথায় পড়তে ও লিখতে পারবে:

- **Read** — সক্রিয় প্রজেক্টের ভেতরে (এবং এর subprojects) এবং `~/.veles/`।
- **Write** — শুধুমাত্র layout-এর লেখার-উপযোগী জোনে (যেমন `wiki/`); machine state-এর জন্য
  `.veles/` সবসময় লেখার-উপযোগী।

Sandbox থেকে বেরিয়ে যাওয়া symlink প্রত্যাখ্যান করা হয়, এবং `..` ট্রাভার্সাল resolve হওয়ার আগেই
অস্বীকার করা হয়। URL fetch একটি SSRF deny-list বজায় রাখে। উন্নত সেটআপ `VELES_SANDBOX_ROOTS` দিয়ে
roots ওভাররাইড করতে পারে, কিংবা `VELES_FETCH_ALLOW_PRIVATE=1` দিয়ে private-network ব্লক তুলে দিতে
পারে — উভয়ই opt-in।

## এই নকশা কেন

লক্ষ্য হলো **বিরক্তিকর চমক ছাড়াই কার্যকর স্বায়ত্তশাসন**: এজেন্ট প্রতিটি read-এ prompt ছাড়াই আসল কাজ
করতে পারে, কিন্তু এমন যেকোনো কিছু যা আপনার মেশিনের ক্ষতি করতে পারে, টাকা খরচ করতে পারে, বা box ছেড়ে
বেরিয়ে যেতে পারে — তা gated থাকে — একবার, এবং তারপর আপনার পছন্দ অনুযায়ী মনে রাখা হয়।
