# প্রোভাইডার কীভাবে কনফিগার করবেন

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/configure-providers.md)

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
[provider]
default = "openrouter"                 # provider name
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

লোকাল প্রোভাইডারে টুল কলিং **ডিফল্টভাবে বন্ধ**। একটি টুল-সক্ষম মডেল বেছে নেওয়ার
পরে এটি সক্রিয় করুন:

```bash
export VELES_LOCAL_TOOLS=1
```

আপনার সার্ভার ডিফল্ট পোর্টে না থাকলে এন্ডপয়েন্ট ওভাররাইড করুন:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## একটি Claude / Gemini CLI সাবস্ক্রিপশনে ডেলিগেট করুন

আপনার `claude` বা `gemini` CLI অথেনটিকেট করা থাকলে, Veles এটি চালাতে পারে:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
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
