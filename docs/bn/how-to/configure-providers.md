# প্রোভাইডার কীভাবে কনফিগার করবেন

> 🌐 **ভাষা:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · **বাংলা** · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Veles-কে OpenRouter, Anthropic, OpenAI, Gemini, লোকাল মডেল, বা একটি CLI
সাবস্ক্রিপশনের মধ্যে স্যুইচ করুন। সম্পূর্ণ প্রোভাইডার তালিকা: [প্রোভাইডার রেফারেন্স](../reference/providers.md)।

## প্রতি কমান্ডে একটি প্রোভাইডার বেছে নিন

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## প্রজেক্টের জন্য একটি ডিফল্ট সেট করুন

`<project>/.veles/config.toml`-এ একটি বেস রাখুন:

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

অথবা `~/.veles/config.toml`-এ একটি ইউজার-গ্লোবাল ডিফল্ট:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## API কী প্রদান করুন

ক্লাউড প্রোভাইডারের একটি কী প্রয়োজন। OS keychain-এ একবার সংরক্ষণ করুন:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…অথবা [এনভায়রনমেন্ট ভ্যারিয়েবল](../reference/environment-variables.md) এক্সপোর্ট করুন:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

লুকআপ ক্রম: keychain (project scope) → keychain (default) → env var। কী **কখনোই**
কনফিগ ফাইলে লেখা হয় না।

## একটি সম্পূর্ণ লোকাল মডেল ব্যবহার করুন (কোনো কী নেই)

[Ollama](https://ollama.com) ইনস্টল করুন, একটি মডেল পুল করুন, এবং Veles-কে সেদিকে নির্দেশ করুন:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

টুল কলিং সার্ভার যা জানায় তা থেকে **শনাক্ত করা হয়**। `VELES_LOCAL_TOOLS=1` দিয়ে
এটি জোর করে চালু করুন (বা `=0` দিয়ে বন্ধ)।

আপনার সার্ভার ডিফল্ট পোর্টে না থাকলে এন্ডপয়েন্ট ওভাররাইড করুন:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## নিজের প্রোভাইডার যোগ করুন

যেকোনো হোস্টেড OpenAI-সামঞ্জস্যপূর্ণ API, বা আপনার চালানো একটি সার্ভার,
`~/.veles/providers.toml`-এ একটি এন্ট্রির মাধ্যমে প্রোভাইডার হয়ে যায় — কোনো কোড
লাগে না। id হলো টেবিলের নাম:

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

তারপর যেকোনো বিল্টইনের মতোই ব্যবহার করুন:

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| Key | অর্থ |
|---|---|
| `kind` | `openai-api` (একটি হোস্টেড API) বা `local` (আপনার চালানো একটি সার্ভার) |
| `base_url` | OpenAI-সামঞ্জস্যপূর্ণ এন্ডপয়েন্ট, যা `/v1` (বা প্রোভাইডারের সমতুল্য) দিয়ে শেষ হয় |
| `base_url_env` | একটি env var, যা সেট থাকলে `base_url` ওভাররাইড করে |
| `key_env` | যে env var-এর নাম থেকে কী পড়া হয়; আগে keychain চেষ্টা করা হয় |
| `label`, `tagline` | উইজার্ডে এটি কীভাবে দেখানো হবে |
| `tools` | `auto` (ডিফল্ট), `on` বা `off` — মডেল টুল কল পাবে কি না |

বিল্টইন id-সহ একটি এন্ট্রি (`[providers.ollama]`) সেই প্রোভাইডারের সেটিংস বদলায় —
যেমন তার `base_url` — কিন্তু তার kind নয়। ত্রুটিপূর্ণ ফাইল একবার রিপোর্ট করা হয়, এবং
Veles বিল্টইন প্রোভাইডার নিয়েই চলতে থাকে; `veles doctor` তাতে কী ভুল আছে তা তালিকাভুক্ত করে।

জনপ্রিয় API-গুলোর শুরুর মান — **Veles টিম যাচাই করেনি**, বর্তমান এন্ডপয়েন্টের জন্য
প্রোভাইডারের ডকুমেন্টেশন দেখুন:

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## একটি Claude / ChatGPT / Google সাবস্ক্রিপশনে ডেলিগেট করুন

আপনার `claude` CLI অথেনটিকেট করা থাকলে, Veles এটি চালাতে পারে:

```bash
veles run --provider claude-cli "..."
```

ChatGPT সাবস্ক্রিপশনের জন্য, Codex CLI ইনস্টল করে একবার লগ ইন করুন (`codex login`):

```bash
veles run --provider codex --model gpt-6-luna "..."
veles models codex      # the models your account has
```

Google সাবস্ক্রিপশনের জন্য, Antigravity CLI (`agy`) একবার ইনস্টল করে লগ ইন করুন,
তারপর তার প্রোভাইডারের নাম দিন — `antigravity-cli` মডিউলটি সেই রানেই আপনার সংযুক্ত
রেজিস্ট্রি থেকে নিজে ইনস্টল হয়ে যায়:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
```

কোনো API কী প্রয়োজন নেই — CLI অথ সামলায়।

## উপলব্ধ মডেল তালিকাভুক্ত করুন

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## এরপর

- [বিভিন্ন টাস্ক বিভিন্ন মডেলে রাউট করুন](per-task-routing.md) — কম্প্রেশনের জন্য
  সস্তা মডেল, প্ল্যানিং-এর জন্য শক্তিশালী মডেল।
