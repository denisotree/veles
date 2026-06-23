# Providers কীভাবে কনফিগার করবেন

> 🌐 **Languages:** [English](../../en/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · **বাংলা**

Veles-কে OpenRouter, Anthropic, OpenAI, Gemini, লোকাল মডেল, কিংবা একটি CLI সাবস্ক্রিপশনের মধ্যে
সুইচ করুন। সম্পূর্ণ provider তালিকা: [providers reference](../reference/providers.md)।

## প্রতি কমান্ডে একটি provider বেছে নিন

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## প্রজেক্টের জন্য একটি ডিফল্ট সেট করুন

`<project>/.veles/config.toml`-এ একটি base রাখুন:

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
```

অথবা `~/.veles/config.toml`-এ একটি user-global ডিফল্ট:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## API key সরবরাহ করুন

Cloud provider-গুলোর একটি key দরকার। এটি একবার OS keychain-এ সংরক্ষণ করুন:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…অথবা [environment variable](../reference/environment-variables.md) export করুন:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Lookup ক্রম: keychain (project scope) → keychain (default) → env var. Key **কখনোই**
config ফাইলে লেখা হয় না।

## সম্পূর্ণ লোকাল মডেল ব্যবহার করুন (key ছাড়া)

[Ollama](https://ollama.com) ইনস্টল করুন, একটি মডেল pull করুন, এবং Veles-কে সেদিকে নির্দেশ করুন:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

লোকাল provider-গুলোতে tool calling **ডিফল্টভাবে বন্ধ**। একটি tool-সক্ষম মডেল বেছে নেওয়ার পর এটি
চালু করুন:

```bash
export VELES_LOCAL_TOOLS=1
```

আপনার সার্ভার ডিফল্ট পোর্টে না থাকলে endpoint ওভাররাইড করুন:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## একটি Claude / Gemini CLI সাবস্ক্রিপশনে delegate করুন

আপনার যদি `claude` বা `gemini` CLI authenticated থাকে, Veles সেটি চালাতে পারে:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

কোনো API key দরকার নেই — CLI-ই auth সামলায়।

## উপলব্ধ মডেল তালিকাভুক্ত করুন

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## এরপর

- [বিভিন্ন task বিভিন্ন মডেলে route করুন](per-task-routing.md) — compression-এর জন্য সস্তা মডেল,
  পরিকল্পনার জন্য শক্তিশালী মডেল।
