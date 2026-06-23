# নিরাপত্তা ব্যবস্থাপনা: trust, autopilot, secrets

> 🌐 **Languages:** [English](../../en/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · **বাংলা**

Veles বিপজ্জনক কাজগুলোকে একটি **trust ladder**-এর পেছনে আটকে রাখে, ফাইল অ্যাক্সেসকে sandbox-এ সীমাবদ্ধ করে, এবং secrets গুলোকে OS keychain-এ রাখে। এর যুক্তি জানতে দেখুন
[trust ও sandbox](../explanation/trust-and-sandbox.md)।

## trust ladder

সংবেদনশীল tool-গুলো (`run_shell`, `write_file`, `fetch_url`, …) চালানোর আগে অনুমতি চায়।
আপনি বেছে নেন: **একবারের জন্য** allow করা, **এই প্রজেক্টের জন্য সবসময়**, **সর্বত্র সবসময়**, নাকি
**প্রত্যাখ্যান**। অনুমতিগুলো (grants) সংরক্ষিত থাকে, ফলে আপনাকে আর বারবার জিজ্ঞাসা করা হয় না।

prompt-এর জন্য অপেক্ষা না করেই grant-গুলো পরিচালনা করুন:

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

কিছু কাজ grant থাকা সত্ত্বেও **সবসময় নিশ্চিতকরণ চায়** — ফাইল মুছে ফেলা, URL fetch করা,
নতুন skill/tool/module ইনস্টল করা, channel সংযুক্ত করা, এবং প্রজেক্টের বাইরে কিছু লেখা।

## Autopilot — একটি সময়-সীমাবদ্ধ bypass

কোনো তত্ত্বাবধানহীন run-এর জন্য (যেমন রাতভর চলা একটি batch), এমন একটি সময়সীমা (window) খুলুন যেখানে trust prompt-গুলো
স্বয়ংক্রিয়ভাবে allow হয়ে যায়:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

প্রতিটি autopilot কাজ পরবর্তী পর্যালোচনার জন্য log করা হয়। non-interactive পরিবেশ
(daemon, batch) autopilot সক্রিয় না থাকলে ডিফল্টভাবে প্রত্যাখ্যান করে।

## Secrets

API key ও bot token গুলো OS keychain-এ থাকে, কখনোই config ফাইলে নয়:

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
```

আপনি `--no-env-fallback` না দিলে, lookup সংশ্লিষ্ট [environment variable](../reference/environment-variables.md)-এ
fallback করে।

## sandbox

Tool-গুলো সক্রিয় প্রজেক্ট ও `~/.veles/`-এর ভেতরে পড়তে পারে, এবং কেবল
layout-এর writable অঞ্চলগুলোতেই লিখতে পারে (ডিফল্টভাবে `wiki/`, `.veles/`)। উন্নত setup-এর জন্য
`VELES_SANDBOX_ROOTS` (`:`-দিয়ে আলাদা করা) ব্যবহার করে root-গুলো override করুন। URL fetch-এর ক্ষেত্রে
একটি SSRF deny-list বজায় থাকে; `VELES_FETCH_ALLOW_PRIVATE=1` private-network ব্লক তুলে দেয়।
