# প্রোভাইডার

> 🌐 **ভাষা:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · **বাংলা** · [Tiếng Việt](../../vi/reference/providers.md)

Veles প্রোভাইডার-অজ্ঞেয়বাদী। যেকোনো এজেন্ট কমান্ডে `--provider <name>` দিন, অথবা
কনফিগে একটি ডিফল্ট সেট করুন। মডেল ID প্রোভাইডারের নিজস্ব নামকরণ ব্যবহার করে।

| প্রোভাইডার | ধরন | API কী | নোট |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **ডিফল্ট।** শত শত মডেল রিলে করে; মডেল ID যেমন `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API, প্রম্পট ক্যাশিং |
| `openai` | Cloud direct | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocess | — (CLI session) | JSON-stream মোডে একটি লোকাল `claude` CLI-তে ডেলিগেট করে |
| `gemini-cli` | Subprocess | — (CLI session) | একটি লোকাল `gemini` CLI-তে ডেলিগেট করে |
| `ollama` | Local | none | `OLLAMA_BASE_URL` (ডিফল্ট `http://localhost:11434/v1`) |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL` (ডিফল্ট `http://localhost:8080/v1`) |
| `openai-compat` | Local/custom | none | `OPENAI_COMPAT_BASE_URL` (প্রয়োজনীয়, কোনো ডিফল্ট নেই) |

ডিফল্ট প্রোভাইডার: `openrouter`। **কোনো হার্ডকোডেড ডিফল্ট মডেল নেই** — সেটআপ
উইজার্ড, `[engine] model`, বা `--model`-এর মাধ্যমে একটি সেট করুন (অন্যথায় এজেন্ট
"no model configured" রিপোর্ট করে)। পার-টাস্ক রাউট `[routing.tasks]`-এ ওভাররাইড না
করা পর্যন্ত `[engine]`-কে তাদের বেস হিসেবে উত্তরাধিকার সূত্রে পায় — দেখুন
[পার-টাস্ক রাউটিং](../how-to/per-task-routing.md)।

## লোকাল প্রোভাইডার

`ollama`, `llamacpp`, এবং `openai-compat`-এর কোনো API কী লাগে না। `veles models <provider>`
দিয়ে ইনস্টল করা মডেল তালিকাভুক্ত করুন (লোকাল প্রোভাইডারের জন্য সর্বদা লাইভ)।

লোকাল প্রোভাইডারে **টুল কলিং ডিফল্টভাবে বন্ধ থাকে** — অনেক লোকাল মডেল ত্রুটিপূর্ণ
টুল কল তৈরি করে। একটি টুল-সক্ষম মডেল বেছে নেওয়ার পরে এটি সক্রিয় করুন:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

`*_BASE_URL` env var দিয়ে এন্ডপয়েন্ট ওভাররাইড করুন (দেখুন
[এনভায়রনমেন্ট ভ্যারিয়েবল](environment-variables.md))।

## CLI ডেলিগেশন (`claude-cli`, `gemini-cli`)

আপনার যদি Claude বা Gemini CLI সাবস্ক্রিপশন থাকে, Veles বাইনারিটি JSON-স্ট্রিমিং
মোডে চালাতে এবং কোঅর্ডিনেটর হিসেবে কাজ করতে পারে — আলাদা API কী ছাড়াই লুপটিকে
local-first রেখে। MCP ব্রিজ কনফিগার করা থাকলে তবেই Veles tools সাবপ্রসেসে পৌঁছায়।

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
