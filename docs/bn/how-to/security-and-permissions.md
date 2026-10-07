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
`.gemini/`, `.agents/`, `.codex/`, `.vscode/`, `.devcontainer/`, `.husky/`-এর অধীনে সবকিছু, এবং `.envrc`, `.mcp.json`,
`.pre-commit-config.yaml`, `lefthook.yml`, যেকোনো গভীরতায়, সেই সঙ্গে রিপোর `core.hooksPath` ডিরেক্টরি এবং
symlink করা `.git` যেখানে নির্দেশ করে — agent-এর file tool সেখানে কেবল আপনি সেই লেখা নিশ্চিত করার পরেই লেখে।
Trust grant ও autopilot এটি কভার করে না; daemon চ্যানেলে জিজ্ঞাসা করে, আর জিজ্ঞাসা করার কেউ না থাকলে
batch run প্রত্যাখ্যান করে।

`claude-cli`, `codex` ও `antigravity-cli` provider শুধু Veles-এর tool সহ একটি model হিসেবে চলে: তাদের নিজস্ব shell,
file-edit ও web tool, প্রজেক্টের `.claude/` settings ও hook, এবং অন্য MCP server প্রযোজ্য হয় না, আর
তারা যে Veles tool-ই কল করে তা উপরের trust ladder-এর মধ্য দিয়ে যায় (সেখানে prompt-এর উত্তর দেওয়ার কেউ
নেই, তাই আগে থেকে grant না করা সবকিছু প্রত্যাখ্যাত হয়)। তাদের MCP config থাকে
`.veles/tmp/delegate-<pid>/`-এ, প্রতিটি চলমান প্রসেসের জন্য একটি করে, যেখানে agent-এর file tool
লিখতে পারে না। `agy` প্রজেক্টের বাইরে, `~/.veles/tmp/`-এর অধীনে, একটি scratch workspace-এ চলে,
তাই প্রজেক্টের নিজস্ব `.agents/` hook ও MCP server কখনও তার কাছে পৌঁছায় না। Veles-এর tool পেলে
সে `--dangerously-skip-permissions` সহ চলে — অন্যথায় agy headless অবস্থায় MCP কল প্রত্যাখ্যান করে —
এবং সেই workspace-এর একটি hook তার নিজস্ব প্রতিটি tool বাতিল করে; যে hook ব্যর্থ হয় সেটিও বাতিল করে।
Veles-এর file tool প্রজেক্টের বাইরে লিখতে পারে না, তাই agy সেগুলো দিয়ে ওই hook বদলাতে পারে না। `codex`-ও প্রজেক্টের বাইরে চলে; আপনার codex config উপেক্ষা
করা হয়, sandbox হয় read-only, আর তার নিজস্ব tool বন্ধ থাকে feature flag দিয়ে, যেগুলোর নাম Veles প্রতিটি
প্রথম run-এর আগে যাচাই করে — যে codex নিজের নির্ভরশীল কোনো flag-এর নাম বদলে ফেলেছে সেটি প্রত্যাখ্যাত হয়,
খোলা অবস্থায় চালানো হয় না। এর MCP server যায় আর্গুমেন্টে (কোনো config file ছাড়া), শুধু ওই server-এর
tool-ই approve করা হয়, আর ওই server যে environment পায় তা নাম ধরে forward করা হয় — `VELES_TRUST_AUTO_ALLOW`
কখনও নয়।

### OS sandbox-এ `run_shell`

এজেন্ট `run_shell` দিয়ে যে কমান্ড চালায় সেগুলো একটি OS sandbox-এ চলে — macOS-এ `sandbox-exec`,
Linux-এ `bwrap` (bubblewrap) — যা এই পাথগুলো তাদের জন্য read-only করে দেয়: প্রজেক্টের প্রতিটি repo-র hook ও
config (worktree বা submodule-এর ক্ষেত্রে মূল repo-র), git যে প্রতিটি config ফাইল পড়ে (তার include,
`~/.gitconfig`, সিস্টেমেরটি) এবং `core.hooksPath` ডিরেক্টরি; উপরে উল্লিখিত auto-run নামগুলো (`.envrc`, `.claude/`, `.mcp.json`, …)
যেকোনো গভীরতায়; প্রজেক্টের `.veles/`, কেবল `skills/`, `tools/`, `tmp/`, `plans/`, `memory/` ও
`artifacts/` বাদে; `~/.veles/` (approval, trust, আপনার module); shell start-up ফাইল (`~/.zshrc`,
`~/.bashrc`, …), `~/.ssh/`, LaunchAgents ও autostart এন্ট্রি; এবং `~/.claude/`,
`~/.codex/`, `~/.gemini/`। এই পাথ, তাদের parent ডিরেক্টরি ও repo-গুলোও rename করে এড়ানো যায় না।
বাকি সবকিছু আগের মতোই কাজ করে: প্রজেক্ট, `git commit`, নতুন repo (`git init`, `git clone`), package cache,
temp ডিরেক্টরি ও নেটওয়ার্ক। কোনো write প্রত্যাখ্যাত হলে এজেন্টকে আপনাকে জিজ্ঞেস করতে বলা হয়।

`veles doctor` দেখায় sandbox সক্রিয় আছে কি না। এটি বন্ধ করতে `~/.veles/config.toml`-এ
`[sandbox] enabled = false` সেট করুন — প্রজেক্টের নিজস্ব config তা পারে না।

Linux-এ `bwrap`-এর জন্য unprivileged user namespace লাগে। Ubuntu 24.04 ও তার পরের সংস্করণ AppArmor
দিয়ে সেগুলো সীমিত করে; একটি profile দিয়ে শুধু `bwrap`-এর জন্য অনুমতি দিন:

```
# /etc/apparmor.d/bwrap — then: sudo apparmor_parser -r /etc/apparmor.d/bwrap
abi <abi/4.0>,
include <tunables/global>
profile bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
}
```

Docker-এ sandbox-এর জন্য `--security-opt seccomp=unconfined --security-opt apparmor=unconfined` লাগে।
যেখানে এটি চালু হতে পারে না, সেখানে `run_shell` আগের মতোই চলে এবং Veles একবার সতর্ক করে।

জানা সীমাবদ্ধতা:

- যেখানে sandbox সক্রিয় নয়, সেখানে `run_shell` একটি shell: আপনি এটি grant করলে (বা autopilot-এ) এটি
  প্রতি-ফাইল নিশ্চিতকরণ ছাড়াই উপরের যেকোনো ফাইলে লিখতে পারে — এবং `~/.veles/`-এর approval store-গুলোতেও। `veles … approve`-এর জন্য
  টার্মিনাল বা রিভিউ করা হ্যাশ (`--sha256`) লাগে, এবং এজেন্টের shell যে কমান্ড শুরু করেছে তা এটি
  প্রত্যাখ্যান করে, কিন্তু grant করা shell সেই চিহ্ন সরিয়ে দিতে বা ফাইলগুলো সরাসরি লিখতে পারে।
- sandbox write সুরক্ষিত রাখে, read বা নেটওয়ার্ক নয়। আপনার `PATH`-এর ডিরেক্টরিগুলো (`~/.local/bin`)
  writable-ই থাকে।
- এটি কমান্ডের নিজস্ব প্রসেস থামায়, এমন কোনো service নয় যাকে কমান্ড নিজের হয়ে কাজ করতে বলে:
  `docker run -v …`, `systemd-run`, `launchctl` বা `osascript` দিয়ে চালু করা container আপনার পরিচয়ে লেখে।
- কমান্ড যে repo তৈরি করে (`git init`) পরের কমান্ড পর্যন্ত তা সুরক্ষিত নয়; প্রজেক্টের root-এ নতুন repo
  হলে Veles আপনাকে জানায়।
- Linux-এ sandbox কেবল বিদ্যমান পাথ সুরক্ষিত রাখতে পারে, এবং প্রজেক্টের ভেতরে ছয় স্তর গভীর পর্যন্ত সুরক্ষিত
  নাম খুঁজে পায়: root-এ নতুন `.envrc` বা হোমে নতুন start-up ফাইল (`~/.bash_profile`) তৈরি করা যায় — Veles
  আপনাকে তা জানায় ও memory log-এ লিখে রাখে — এবং প্রজেক্টে যাওয়ার পথের কোনো symlink (`~/code` →
  `/Volumes/…`) বদলে দেওয়া যায়। macOS দুটোই প্রত্যাখ্যান করে।
- MCP approval `command`/`args`-এ উল্লিখিত প্রজেক্ট script এবং `-m` দিয়ে চালানো module (root-এ বা `src/`-এর
  নিচে) কভার করে, সেগুলো যে ফাইল import করে সেগুলো নয়।
- CLI provider-এর ক্ষেত্রে, যে run কেবল নিজেদের জন্য tool আগে থেকে authorise করে (daemon-এর
  background job, `veles research`) সেগুলো তা delegate করা CLI-কে দেয় না: আগে থেকে authorise করা
  Veles প্রসেসের ভেতরেই থাকে, আর CLI যে MCP server চালু করে সেটি আলাদা একটি, তাই তার Veles tool-গুলোর জন্য
  স্থায়ী `veles trust set` grant বা autopilot উইন্ডো লাগে। parent run-এর planning mode-ও তাদের কাছে পৌঁছায় না।
- `antigravity-cli` ধরে নেয় agy তার workspace-এর `.agents/hooks.json` মানে; যে agy রিলিজ workspace hook
  পড়া বন্ধ করবে, সেটি `--dangerously-skip-permissions`-এর অধীনে তার নিজস্ব tool খোলা রেখে দেবে।

control character (terminal escape, bidi override) সহ path প্রত্যাখ্যাত হয়, এবং confirmation, trust prompt ও
diff preview এমন অক্ষর escape করে দেখায় — কোনো tool call আপনার approve করা লেখা জাল করতে পারে না।

কোনো config-এর MCP server আপনি approve করার পরেই চালু হয় — দেখুন
[বাহ্যিক MCP server](external-mcp-servers.md)।
