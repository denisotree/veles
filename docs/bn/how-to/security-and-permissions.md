# নিরাপত্তা ব্যবস্থাপনা: trust, autopilot, secrets

> 🌐 **ভাষা:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · **বাংলা** · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

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
veles secret set OPENROUTER_API_KEY --project myproj   # a key for one project only
```

আপনি `--no-env-fallback` না দিলে, lookup সংশ্লিষ্ট [environment variable](../reference/environment-variables.md)-এ
fallback করে।

## sandbox

Tool-গুলো সক্রিয় প্রজেক্ট, `~/.veles/skills/` ও `~/.veles/locales/`-এর ভেতরে পড়তে পারে, এবং
কেবল প্রজেক্টের ভেতরে লিখতে পারে — layout যদি writable অঞ্চল ঘোষণা করে, তবে কেবল সেগুলোতে। উন্নত setup-এর জন্য
`VELES_SANDBOX_ROOTS` (`:`-দিয়ে আলাদা করা) ব্যবহার করে root-গুলো override করুন। URL fetch-এর ক্ষেত্রে
একটি SSRF deny-list বজায় থাকে; `VELES_FETCH_ALLOW_PRIVATE=1` private-network ব্লক তুলে দেয়।

প্রজেক্টের `.veles/`-এর ভেতরে agent-এর file tool-গুলো কেবল `skills/`, `tools/`, `tmp/`, `plans/`,
`memory/` ও `artifacts/`-এ লিখতে পারে। সেখানকার বাকি সবকিছু —
`trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`, `memory.db` —
কেবল `veles` কমান্ড ও Veles-এর নিজস্ব tool-এর মাধ্যমেই বদলায়। file tool-গুলো প্রজেক্টের অন্য যেকোনো
`.veles/` ডিরেক্টরিও (সাবপ্রজেক্টের, বা agent যেটি `wiki/`-এ বসিয়ে দেবে) যেকোনো গভীরতায় প্রত্যাখ্যান করে।
ফলে file tool দিয়ে agent নিজেকে trust দিতে পারে না, বা এমন কোড যোগ করতে পারে না যা Veles চালাবে
(`.veles/tools/`-এ লেখা tool আপনি তার ফাইল approve করার পরেই লোড হয়)। একই ফাইলের অন্য বানানও
(বড়/ছোট হাতের অক্ষর, `..`, symlink) প্রত্যাখ্যাত হয়।

যে ফাইলগুলো স্পষ্ট কমান্ড ছাড়াই চলে বা কোনো agent CLI-কে চালিত করে — `.git/`, `.githooks/`, `.claude/`,
`.gemini/`, `.codex/`, `.vscode/`, `.devcontainer/`, `.husky/`-এর অধীনে সবকিছু, এবং `.envrc`, `.mcp.json`,
`.pre-commit-config.yaml`, `lefthook.yml`, যেকোনো গভীরতায়, সেই সঙ্গে রিপোর `core.hooksPath` ডিরেক্টরি এবং
symlink করা `.git` যেখানে নির্দেশ করে — agent-এর file tool সেখানে কেবল আপনি সেই লেখা নিশ্চিত করার পরেই লেখে।
Trust grant ও autopilot এটি কভার করে না; daemon চ্যানেলে জিজ্ঞাসা করে, আর জিজ্ঞাসা করার কেউ না থাকলে
batch run প্রত্যাখ্যান করে।

`claude-cli` ও `gemini-cli` provider শুধু Veles-এর tool সহ একটি model হিসেবে চলে: তাদের নিজস্ব shell,
file-edit ও web tool, প্রজেক্টের `.claude/` settings ও hook, এবং অন্য MCP server প্রযোজ্য হয় না, আর
তারা যে Veles tool-ই কল করে তা উপরের trust ladder-এর মধ্য দিয়ে যায় (সেখানে prompt-এর উত্তর দেওয়ার কেউ
নেই, তাই আগে থেকে grant না করা সবকিছু প্রত্যাখ্যাত হয়)।

জানা সীমাবদ্ধতা:

- `run_shell` একটি shell: আপনি এটি grant করলে (বা autopilot-এ) এটি প্রতি-ফাইল নিশ্চিতকরণ ছাড়াই উপরের
  যেকোনো ফাইলে লিখতে পারে।
- MCP approval server-এর কমান্ড লাইন pin করে, প্রজেক্ট থেকে সে যে ফাইল চালায় সেগুলো নয়
  (`args`-এ উল্লিখিত script) — সেগুলোও পর্যালোচনা করুন।
- CLI provider-এর ক্ষেত্রে, যে run কেবল নিজেদের জন্য tool আগে থেকে authorise করে (daemon-এর
  background job, `veles research`) সেগুলো তা delegate করা CLI-কে দেয় না: তার Veles tool-গুলোর জন্য
  স্থায়ী `veles trust set` grant বা autopilot উইন্ডো লাগে। parent run-এর planning mode-ও তাদের কাছে পৌঁছায় না।
- `gemini-cli` তার run-এর জন্য প্রজেক্ট ফোল্ডারকে trust করে, তাই gemini প্রজেক্টের `.env`-ও পড়ে — agent যে
  gemini settings চালনা করুক তা চান না, সেগুলো সেখান থেকে সরিয়ে রাখুন।
- managed (system) gemini policy আছে এমন মেশিনে gemini Veles-এর দেওয়া policy উপেক্ষা করে, তাই সেখানে
  `gemini-cli` কেবল Veles-এর tool-এ সীমাবদ্ধ নয়।

control character (terminal escape, bidi override) সহ path প্রত্যাখ্যাত হয়, এবং confirmation, trust prompt ও
diff preview এমন অক্ষর escape করে দেখায় — কোনো tool call আপনার approve করা লেখা জাল করতে পারে না।

কোনো config-এর MCP server আপনি approve করার পরেই চালু হয় — দেখুন
[বাহ্যিক MCP server](external-mcp-servers.md)।
