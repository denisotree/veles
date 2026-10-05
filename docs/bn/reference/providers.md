# প্রোভাইডার

> 🌐 **ভাষা:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · **বাংলা** · [Tiếng Việt](../../vi/reference/providers.md)

Veles প্রোভাইডার-অজ্ঞেয়বাদী। যেকোনো এজেন্ট কমান্ডে `--provider <id>` দিন, অথবা
কনফিগে একটি ডিফল্ট সেট করুন। মডেল ID প্রোভাইডারের নিজস্ব নামকরণ ব্যবহার করে।

## প্রোভাইডার ক্যাটালগ

Veles যত প্রোভাইডার চেনে, প্রতিটি একটি ক্যাটালগের এন্ট্রি, যা তিনটি উৎস থেকে তৈরি হয়:

1. **বিল্টইন** — নিচের টেবিল, Veles-এর সাথে শিপ করা।
2. **আপনার নিজের** — `~/.veles/providers.toml`: একটি এন্ট্রি যোগ করে একটি হোস্টেড
   OpenAI-সামঞ্জস্যপূর্ণ API বা আপনার চালানো একটি সার্ভার (দেখুন
   [নিজের প্রোভাইডার যোগ করুন](../how-to/configure-providers.md#নিজের-প্রোভাইডার-যোগ-করুন))।
   বিল্টইন id-সহ একটি এন্ট্রি সেই প্রোভাইডারের সেটিংস ওভাররাইড করে (যেমন তার `base_url`)।
3. **মডিউল** — একটি রেজিস্ট্রি মডিউল একটি প্রোভাইডার যোগ করে (`antigravity-cli`)।
   `[engine] provider`, একটি রুট বা `--provider`-এ এটির নাম দিলে পরের রানে আপনার
   সংযুক্ত রেজিস্ট্রি থেকে এটি ইনস্টল হয়ে যায়, ঘোষিত চ্যানেলের মতোই।

`--provider`, `veles models`, সেটআপ উইজার্ড, রাউটিং এবং `veles doctor` সবাই ক্যাটালগ
পড়ে, তাই যেকোনো উৎসের প্রোভাইডার বিল্টইনের মতোই সর্বত্র কাজ করে। অজানা id হলে
কী কী আছে তার তালিকাসহ এক লাইনের ত্রুটি দেখায়; `veles doctor` আরও পরীক্ষা করে
`~/.veles/providers.toml` এবং আপনার রুটগুলো যে প্রতিটি প্রোভাইডারের নাম দেয়।

| প্রোভাইডার | ধরন | API কী | নোট |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **ডিফল্ট।** শত শত মডেল রিলে করে; মডেল ID যেমন `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API, প্রম্পট ক্যাশিং |
| `openai` | Cloud direct | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI delegate | — (CLI session) | JSON-stream মোডে একটি লোকাল `claude` CLI-তে ডেলিগেট করে |
| `ollama` | Local | none | `OLLAMA_BASE_URL` (ডিফল্ট `http://localhost:11434/v1`) |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL` (ডিফল্ট `http://localhost:8080/v1`) |
| `openai-compat` | Local/custom | ঐচ্ছিক `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL` (প্রয়োজনীয়, কোনো ডিফল্ট নেই) |

`gemini-cli` 1.2.6-এ সরানো হয়েছে — Google আর ব্যক্তিগত অ্যাকাউন্টে Gemini CLI সরবরাহ
করে না। API কী-সহ `gemini` ব্যবহার করুন, অথবা `antigravity-cli` মডিউল।

ডিফল্ট প্রোভাইডার: `openrouter`। **কোনো হার্ডকোডেড ডিফল্ট মডেল নেই** — সেটআপ
উইজার্ড, `[engine] model`, বা `--model`-এর মাধ্যমে একটি সেট করুন (অন্যথায় এজেন্ট
"no model configured" রিপোর্ট করে)। পার-টাস্ক রাউট `[routing.tasks]`-এ ওভাররাইড না
করা পর্যন্ত `[engine]`-কে তাদের বেস হিসেবে উত্তরাধিকার সূত্রে পায় — দেখুন
[পার-টাস্ক রাউটিং](../how-to/per-task-routing.md)।

## লোকাল প্রোভাইডার

`ollama`, `llamacpp`, এবং `openai-compat`-এর কোনো API কী লাগে না। `veles models <provider>`
দিয়ে ইনস্টল করা মডেল তালিকাভুক্ত করুন (লোকাল প্রোভাইডারের জন্য সর্বদা লাইভ)।

**টুল কলিং শনাক্ত করা হয়** ব্যাকএন্ড যা জানায় তা থেকে: ollama প্রতিটি মডেলের সক্ষমতা
জানায়, llama.cpp সার্ভার জানায় তার চ্যাট টেমপ্লেটের সক্ষমতা। `VELES_LOCAL_TOOLS=1`
টুল কলিং জোর করে চালু করে, `=0` বন্ধ করে; সেট না থাকলে শনাক্ত করা হয়।

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

`*_BASE_URL` env var দিয়ে এন্ডপয়েন্ট ওভাররাইড করুন (দেখুন
[এনভায়রনমেন্ট ভ্যারিয়েবল](environment-variables.md))।

## CLI ডেলিগেশন (`claude-cli`, `antigravity-cli`)

আপনার যদি Claude বা Google সাবস্ক্রিপশন থাকে, Veles তার CLI হেডলেস চালাতে এবং
কোঅর্ডিনেটর হিসেবে কাজ করতে পারে — আলাদা API কী লাগে না। `claude-cli` বিল্টইন;
`antigravity-cli` (`agy` CLI) একটি রেজিস্ট্রি মডিউল, যার নাম দিলে নিজে থেকেই ইনস্টল হয়।

ডেলিগেট কেবল মডেলের কাজ করে: Veles-এর tools তার কাছে একটি MCP ব্রিজের মাধ্যমে পৌঁছায়,
এবং প্রতিটি কল Veles-এর ট্রাস্ট ল্যাডারের মধ্য দিয়ে যায়। ব্রিজের কনফিগ থাকে চলমান
প্রসেসের নিজস্ব একটি ডিরেক্টরিতে, `.veles/tmp/delegate-<pid>/`, প্রসেস শেষ হলে সেটি মুছে
যায়। `agy` সেখানে একটি স্ক্র্যাচ ওয়ার্কস্পেসে চলে, আপনার প্রজেক্টে নয়, এমন একটি গেটের
পেছনে যা তার নিজস্ব শেল ও ফাইল টুল বাতিল করে।

## মাল্টিমোডাল স্ট্যাটাস (vision / speech-to-text)

Veles একটি `VisionAdapter` এবং একটি STT অ্যাডাপ্টার প্রোটোকল (`modules/vision.py`,
`modules/stt.py`) এবং একটি প্রসেস-গ্লোবাল রেজিস্ট্রি সংজ্ঞায়িত করে, **কিন্তু কোনো
কংক্রিট অ্যাডাপ্টার শিপ করে না এবং ডিমন স্টার্টআপে কোনোটি রেজিস্টার হয় না**। তাই কোনো
চ্যানেলে পাঠানো একটি ছবি বা ভয়েস মেসেজ বর্তমানে বিশ্লেষণ করার পরিবর্তে একটি
"not configured" নোটিশ ফেরত দেয়। অ্যাডাপ্টার ওয়্যার করা হলে ব্যবহারের জন্য
`vision` রাউটিং টাস্ক বিদ্যমান। দেখুন
[Telegram সংযুক্ত করুন](../how-to/connect-telegram.md#multimodal-limitation)।

## একটি মডেল বেছে নেওয়া

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

বিভিন্ন কাজের জন্য বিভিন্ন মডেল ব্যবহার করতে (কম্প্রেশনের জন্য সস্তা, প্ল্যানিং-এর
জন্য শক্তিশালী), দেখুন [পার-টাস্ক রাউটিং](../how-to/per-task-routing.md)।
