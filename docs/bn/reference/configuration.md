# কনফিগারেশন রেফারেন্স

> 🌐 **ভাষা:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · **বাংলা** · [Tiếng Việt](../../vi/reference/configuration.md)

Veles দুটি TOML ফাইল এবং কয়েকটি স্টেট ডিরেক্টরি দিয়ে কনফিগার করা হয়। সিক্রেট
(API কী, বট টোকেন) **কখনোই** এই ফাইলগুলোতে লেখা হয় না — সেগুলো OS
keychain বা এনভায়রনমেন্ট ভ্যারিয়েবলে থাকে (দেখুন [এনভায়রনমেন্ট ভ্যারিয়েবল](environment-variables.md))।

## স্টেট কোথায় থাকে

| পাথ | স্কোপ | বিষয়বস্তু |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, trust গ্রান্ট, ক্রস-প্রজেক্ট skills/tools, মডেল ক্যাশ, locales, registry |
| `<project>/.veles/` | Project-local | `project.toml`, `config.toml`, `memory.db`, প্রজেক্ট skills/tools, plans, রানটাইম আর্টিফ্যাক্ট |
| `<project>/AGENTS.md` | Project | এজেন্টে ইনজেক্ট করা কনটেক্সট ফাইল (`CLAUDE.md` / `GEMINI.md`-এ symlink করা) |
| `<project>/wiki/`, `sources/` | Project | ইউজার কন্টেন্ট (ডিফল্ট LLM-Wiki লেআউট) |

`VELES_USER_HOME` `~` রিডাইরেক্ট করে (ফলে ইউজার স্টেট `<override>/.veles/`-এ যায়)।
সম্পূর্ণ ট্রির জন্য দেখুন [প্রজেক্ট লেআউট](project-layout.md)।

---

## ইউজার কনফিগ — `~/.veles/config.toml`

প্রথম-রানের উইজার্ড লেখে; হাতে সম্পাদনা করা নিরাপদ।

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| কী | টাইপ | উদ্দেশ্য |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI স্ট্রিং-এর জন্য locale (`VELES_LOCALE` দিয়ে ওভাররাইডযোগ্য) |
| `[user] default_provider` | string | কোনোটি না দিলে যে প্রোভাইডার ব্যবহৃত হয় |
| `[user] default_model` | string | কোনোটি না দিলে যে মডেল ব্যবহৃত হয় |
| `[user] tui_theme` | string | ডিফল্ট TUI কালার থিম |
| `[permissions] <tool>` | policy | পার-টুল পারমিশন পলিসি (দেখুন [trust ও sandbox](../explanation/trust-and-sandbox.md)) |

---

## প্রজেক্ট কনফিগ — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### সেকশনসমূহ

| সেকশন | উদ্দেশ্য |
|---|---|
| `[engine]` | মূল এজেন্ট এবং রাউটিং ক্যাসকেডের জন্য বেস প্রোভাইডার (`provider` = provider name) + মডেল (`model` = model id) |
| `[routing.tasks]` | পার-টাস্ক `provider:model` ওভাররাইড — দেখুন [পার-টাস্ক রাউটিং](../how-to/per-task-routing.md) |
| `[permissions]` | পার-টুল পারমিশন পলিসি (প্রজেক্ট স্কোপ) |
| `[daemon]` | unnamed/"default" ডিমনের bind + autostart |
| `[daemon.<name>]` | একটি নামকৃত ডিমন সেশন (নিজস্ব model/provider/host/port/mode) |
| `[channels.<type>]` | unnamed ডিমন দ্বারা পরিবেশিত একটি চ্যানেল (যেমন `telegram`) |
| `[daemon.<name>.channels.<type>]` | একটি নামকৃত ডিমন সেশনে বাইন্ড করা একটি চ্যানেল |
| `[mcp.servers.<name>]` | একটি এক্সটার্নাল MCP সার্ভার (টুল সোর্স) |

`[routing.tasks]`-এর টাস্ক টাইপ: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`।

> `AGENTS.md`-এর ন্যাচারাল-ল্যাঙ্গুয়েজ রাউটিং হিন্ট একটি অটো-জেনারেটেড
> `routing.nl.toml`-এ পার্স হয়; স্পষ্ট `[routing.tasks]` এন্ট্রি সর্বদা জেতে। পুনরায়
> পার্স করতে `veles route refresh` চালান। দেখুন [পার-টাস্ক রাউটিং](../how-to/per-task-routing.md)।

### ব্যাকএন্ড পিন করা এবং রিকোয়েস্ট বডির অন্যান্য কী

`[engine.request.<provider>]` সেই প্রোভাইডারের রিকোয়েস্ট বডিতে **হুবহু** পাঠানো হয়।
Veles আপস্ট্রিমের স্কিমা মডেল করে না, তাই প্রোভাইডার যা-ই গ্রহণ করে তা সঙ্গে সঙ্গে কাজ
করে — Veles তা জানা পর্যন্ত অপেক্ষা করতে হয় না:

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

সেকশনটি **প্রোভাইডারের নাম** দিয়ে কী করা (`openrouter`, `anthropic`, `openai`,
`gemini`, `ollama`, `llamacpp`, `openai-compat`), যাতে একটিই প্রজেক্ট কনফিগ ব্যাকএন্ড
বদলের পরেও টিকে থাকে: OpenRouter-এর `provider` ব্লক llama.cpp-তে পাঠালে 400 হবে, তাই
প্রতিটি ব্যাকএন্ড কেবল নিজের সাব-সেকশনই পড়ে। সেকশন ঘোষণা না করলে রিকোয়েস্টগুলো
বাইট-বাই-বাইট আগের মতোই থাকে।

**কখন দরকার: পুনরুৎপাদনযোগ্য পরিমাপ।** OpenRouter-এর মতো রিলে একই মডেলকে ভিন্ন ভিন্ন
কোয়ান্টাইজেশনের অনেক ব্যাকএন্ডে ছড়িয়ে দেয়, ফলে একই ইনপুটে দুটি রান এমন কারণে আলাদা
হতে পারে যার সঙ্গে ইনপুটের কোনো সম্পর্ক নেই। `session_id` ভিত্তিক স্টিকি রাউটিং একটি
কথোপকথনকে একটি ব্যাকএন্ডে ধরে রাখে, কিন্তু সেটি **কোনটি** তা বলে না।

`quantizations` দিয়ে নয়, `order` দিয়ে পিন করুন। ১৮-০৯-২০২৬ পর্যন্ত
`z-ai/glm-5.3-flash`-এর ২৯টি এন্ডপয়েন্ট: ১৬টি `fp8`, ৩টি `fp4`, একটি `nvfp4`,
**৯টি কোনো কোয়ান্টাইজেশনই ঘোষণা করে না**, আর `bf16`-এ একটিও নয়। অর্থাৎ
`quantizations = ["fp8"]`-এর পরেও ১৬টি প্রার্থী থেকে যায়, যাদের কনটেক্সট উইন্ডো
262144 থেকে 1310720 টোকেন পর্যন্ত; অথচ একটিমাত্র উপাদানের `order` আর
`allow_fallbacks = false` মিলে ব্যাকএন্ড নির্দিষ্ট করে দেয়। কোনো মডেলের এন্ডপয়েন্ট
তালিকা দেখতে:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

পিন কেবল পরিমাপের প্রজেক্টেই রাখুন — প্রোডাকশনের দরকার স্টিকি রাউটিং, যা প্রাপ্যতা ও
ফলব্যাক বজায় রাখে।

**পিন টিকল কি না যাচাই।** প্রতিটি মডেল-কলে উদ্দেশ্য ও ফলাফল দুটোই
`.veles/traces.jsonl`-এ লেখা হয়: `request_extra` হলো যা পাঠানো হয়েছিল,
`upstream_provider` হলো যে ব্যাকএন্ড উত্তর দিয়েছে। একটি লাইনই যথেষ্ট:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

একের বেশি লাইন মানে ওই রান ব্যাকএন্ড মিশিয়ে ফেলেছে। একই রেকর্ডে
`reasoning_tokens` (বাজেটের কতটা চিন্তায় গেল) এবং `est_cost_usd` (আপস্ট্রিমের জানানো
প্রকৃত খরচ)ও থাকে।

**ভুলগুলো ইচ্ছাকৃতভাবেই সরব।** প্রোভাইডারের নামের বানান ভুল কিংবা সেকশন পাথে টাইপো
(`[engine.reqest.…]`) হলে রান `ConfigError` দিয়ে থেমে যায়, যা ফাইল ও পরিচিত
প্রোভাইডারদের নাম জানায়: যে পিন তার পর্যন্ত পৌঁছালই না, সেটি নীরবে সেই পরিমাপকেই
অকেজো করে দিত যার জন্য তা লেখা হয়েছিল। প্রোভাইডারের সাব-সেকশনের *ভিতরের* কী Veles
যাচাই করে না, কারণ আপস্ট্রিম করে: OpenRouter অচেনা কী-তে
`400 provider: Unrecognized key: "quantization"` আর অমিল মানে
`404 No endpoints found …` ফেরত দেয়।

### কথোপকথনের রেকর্ড কত দিন রাখা হয়

```toml
[memory]
turn_retention_days = 90   # 0 মানে চিরকাল রাখা
```

কাঁচা কথোপকথনের টার্নগুলো এই ক'দিন পর মুছে ফেলা হয়; কিন্তু সেগুলো থেকে বের করা
**ইনসাইট** ও নিয়ম চিরকাল রাখা হয়। রেকর্ড হলো কাঁচামাল, আর ইনসাইটই সেই উদ্দেশ্য যার
জন্য তা পড়া হয়েছিল — ফলে `memory.db` সীমাহীনভাবে বাড়া বন্ধ করে, অথচ এজেন্ট তার শেখা
জিনিস ধরে রাখে।

একটি রেকর্ড বাদ দিতে **দুটি** শর্তই মিলতে হবে: উইন্ডোর চেয়ে পুরোনো হওয়া, **এবং**
কিউরেটর ওই সেশনটি ইতিমধ্যে প্রক্রিয়া করে ফেলা। কিউরেটর যে সেশনে পৌঁছায়নি, তা যত
পুরোনোই হোক কখনো মোছা হয় না — নইলে রেকর্ড থেকে কিছু শেখার আগেই তা ধ্বংস হয়ে যেত।

দৃশ্যমান মূল্য: `veles sessions search` কেবল উইন্ডোর ভিতরের লেখা খুঁজে পায়।
`veles sessions list` পুরোনো রানগুলো তবু দেখাতে থাকে, কারণ সেশনের সারি (id, শিরোনাম,
টাইমস্ট্যাম্প) থেকে যায় — কেবল বার্তার মূল অংশ যায়। পরিষ্কারের কাজ `veles dream`-এর
সময় হয়, ইনসাইট বের করার পরে।

### লগ রোটেশন

`traces.jsonl` আর `events.jsonl` 50 MB-তে `<নাম>.<unix_ts>`-এ রোটেট হয়, এবং সবচেয়ে
নতুন **১০**টি রোটেশন রাখা হয় — তার চেয়ে পুরোনোগুলো পরের রোটেশনের সময় মুছে যায়। আগে
সেগুলো চিরকাল রাখা হতো।

সাধারণ ব্যবহারে কিছুই কনফিগার করার দরকার নেই: প্রতি trace রেকর্ডে ~530 বাইট আর
এজেন্টের প্রতি টার্নে ~1.1 KB ইভেন্ট হিসেবে প্রথম রোটেশন বহু বছর দূরে। সেটিংটি আছে
কারণ নীতিহীন সীমাহীন বৃদ্ধি একটি ফাঁস, যা শেষমেশ তাকেই আবিষ্কার করতে হবে যে এই
মেশিনটি উত্তরাধিকারে পাবে।

### ছবি

কোনো চ্যানেলে পাঠানো ছবির বর্ণনা টার্ন শুরু হওয়ার আগেই তৈরি হয় — সেই মডেল দিয়ে
`[routing.tasks].vision` যেটির দিকে নির্দেশ করে, আর স্পষ্ট রুট না থাকলে সেটি আপনার
`[engine]` মডেলই। তাই মাল্টিমোডাল ইঞ্জিনের কোনো কনফিগারেশনই লাগে না।

`[vision] mode` পাইপলাইন বেছে নেয়:

- `model` (ডিফল্ট) — ভিশন মডেল ছবির বর্ণনা দেয়।
- `ocr` — শুধু Tesseract। লোকাল, বিনামূল্যে, কোনো LLM কল নেই; লেখার স্ক্যানের জন্য
  ভালো।
- `ocr+model` — প্রথমে হুবহু লেখা, তারপর মডেলের বর্ণনা।
- `off` — কিছুই পড়া হয় না; ফাইল তবু সংরক্ষিত থাকে এবং এজেন্ট চাইলে নিজেই
  `image_describe` / `image_ocr` ডাকতে পারে।

ইঞ্জিন যখন কেবল টেক্সট সামলায়, তখন `[vision] model` দিন। ভিশন-সক্ষম যেকোনো প্রোভাইডার
চলবে, লোকাল সার্ভারসহ: `ollama:llava`, `llamacpp:…`, `openai-compat:…`।

### `project.toml`

`<project>/.veles/project.toml` অপরিবর্তনীয় প্রজেক্ট মেটাডেটা ধারণ করে (`name`,
`created_at`, `schema_version`, `layout`)। সাধারণত আপনি এটি হাতে সম্পাদনা করবেন না।

---

## AGENTS.md

প্রজেক্ট রুটে থাকা প্রজেক্ট কনটেক্সট ফাইল। এটি স্টার্টআপে এজেন্টের সিস্টেম প্রম্পটে
ইনজেক্ট করা হয় এবং `CLAUDE.md` ও `GEMINI.md`-এ symlink করা হয় যাতে ডিরেক্টরিতে চালু
করা একটি `claude` বা `gemini` CLI একই কনটেক্সট তুলে নেয়।

এটি ছোট রাখুন — সহায়ক `.md` ফাইল (যেমন `wiki/INDEX.md`) প্রয়োজনে লোড হয়।
`veles schema validate` দিয়ে প্রয়োজনীয় সেকশনগুলো যাচাই করুন। দেখুন
[লেআউট প্যাক ও LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)।
