# বাহ্যিক MCP সার্ভার কীভাবে সংযুক্ত করবেন

> 🌐 **Languages:** [English](../../en/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · **বাংলা**

Veles একটি [MCP](https://modelcontextprotocol.io/) **client**: এটি বাহ্যিক MCP সার্ভারের সাথে সংযোগ করতে পারে এবং তাদের টুলগুলোকে এজেন্টের কাছে এমনভাবে তুলে ধরতে পারে যেন সেগুলো বিল্ট-ইন (GitHub, লাইব্রেরি ডকুমেন্টেশন, ওয়েব সার্চ, আপনার নিজের সার্ভিস, …)।

## একটি সার্ভার কনফিগার করা

`<project>/.veles/config.toml`-এ (অথবা ব্যবহারকারী-গ্লোবাল `~/.veles/config.toml`-এ) একটি `[mcp.servers.<name>]` ব্লক যোগ করুন। `<name>`-কে অবশ্যই `[A-Za-z0-9][A-Za-z0-9_-]{0,31}`-এর সাথে মিলতে হবে — এটি প্রতিটি টুলের নামের অংশ হয়ে যায়। তিনটি transport সমর্থিত: `stdio` (ডিফল্ট), `http`, `sse`।

| Key | Transport | Default | উদ্দেশ্য |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (required) | — | যে executable চালু করতে হবে — **শুধু প্রোগ্রামটি, এর আর্গুমেন্ট নয়** |
| `args` | stdio | `[]` | আর্গুমেন্টের তালিকা, প্রতি আইটেমে একটি টোকেন |
| `env` | stdio | `{}` | সাবপ্রসেসের জন্য অতিরিক্ত environment (উত্তরাধিকারসূত্রে পাওয়া env-এর উপর merge করা হয়) |
| `url` | http/sse (required) | — | সার্ভার endpoint |
| `timeout_s` | — | `120` | একটি একক টুল কলের জন্য বাজেট |
| `connect_timeout_s` | — | `30` | প্রাথমিক সংযোগের জন্য বাজেট |
| `enabled` | — | `true` | এন্ট্রি রেখে দিয়ে সংযোগ এড়াতে `false` সেট করুন |

`command`, `args`, `env`, এবং `url`-এর String মানগুলো environment থেকে `${VAR}` interpolate করে (সেট না করা ভেরিয়েবল একটি সতর্কবার্তাসহ খালি স্ট্রিং হয়ে যায়) — সিক্রেটগুলো ফাইলের বাইরে রাখুন।

> **`command` বনাম `args`।** Veles প্রোগ্রামটি সরাসরি চালায় (কোনো shell ছাড়া), তাই executable এবং তার আর্গুমেন্ট **আলাদা** ফিল্ড। লিখুন `command = "npx"`, `args = ["-y", "pkg"]` — **নয়** `command = "npx -y pkg"`।

### stdio (লোকাল সাবপ্রসেস)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

আপনি নিজে যে সার্ভার চালান সেটিও একইভাবে কাজ করে — `command`/`args` সেটির দিকে নির্দেশ করুন:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### API key লাগে এমন একটি সার্ভার (context7)

[Context7](https://context7.com) হালনাগাদ লাইব্রেরি ডকুমেন্টেশন সরবরাহ করে। key-টি আর্গুমেন্ট হিসেবে পাস করুন যাতে `${VAR}` সেটি ফাইলের বাইরে রাখে:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse (রিমোট)

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **কাস্টম header নেই (এখনো)।** `http`/`sse` transport শুধু `url` পাঠায় — Veles কোনো `Authorization` header সংযুক্ত করতে পারে না। key লাগে এমন একটি রিমোট সার্ভারের জন্য, `args`/`env`-এ key রেখে এর `stdio` (যেমন `npx`) ভ্যারিয়েন্ট, অথবা URL-এ key গ্রহণ করে এমন একটি endpoint বেছে নিন।

## নির্দিষ্ট টুল লুকানো

`[mcp] disabled_tools` সেট করুন — একটি table যা প্রতিটি সার্ভারকে এড়িয়ে যাওয়ার টুল-নামগুলোর সাথে map করে:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## পরিদর্শন ও পরীক্ষা

```bash
veles mcp list              # every configured server: transport, status, tool count
veles mcp test github       # connect to one server and list its tools
```

`veles mcp list` সবসময় 0 দিয়ে exit করে — এটি একটি inspector, কোনো health gate নয়। সংযোগ ব্যর্থ হলে `veles mcp test` 1 দিয়ে এবং অজানা সার্ভার নামের জন্য 2 দিয়ে exit করে।

## টুলগুলো কীভাবে প্রকাশ পায়

কনফিগার করা হয়ে গেলে, পরবর্তী `veles run` / TUI / daemon চালু হওয়ার সময় সার্ভারগুলো **স্বয়ংক্রিয়ভাবে** mount হয় — আলাদা কোনো "enable MCP" ফ্ল্যাগ নেই, কনফিগের উপস্থিতিই হলো সুইচ। প্রতিটি টুল স্বাভাবিক registry-তে `mcp_<server>_<tool>` হিসেবে প্রবেশ করে এবং যেকোনো বিল্ট-ইনের মতোই এজেন্ট দ্বারা কলযোগ্য। Schema-গুলো sanitise করা হয় (নাম/দৈর্ঘ্যের সীমা, control-char অপসারণ) যাতে একটি অবিশ্বস্ত সার্ভার প্রম্পটে inject করতে না পারে। টুলের hint-গুলো trust ladder-এর সাথে map করে: ধ্বংসাত্মক টুল সবসময় নিশ্চিতকরণ চায়, read-only টুল প্রম্পট ছাড়াই চলে, বাকি সবকিছু স্বাভাবিক [trust](security-and-permissions.md) প্রবাহের মধ্য দিয়ে যায় — প্রতিবার জিজ্ঞাসিত হতে না চাইলে `veles trust set` দিয়ে স্থায়ী অনুমোদন দিন।

## ব্যর্থতা সামলানো

যে সার্ভার সংযোগে ব্যর্থ হয় — অনুপস্থিত `command`, ভুল `url`, বা যেকোনো অবৈধ এন্ট্রি — সেটিকে একটি warning হিসেবে লগ করা হয় এবং এড়িয়ে যাওয়া হয়। এটি কখনো startup বা এজেন্টকে block করে না। স্ট্যাটাস ও ত্রুটি দেখতে আবার `veles mcp list` চালান।
