# Providers कैसे configure करें

> 🌐 **भाषाएँ:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · **हिन्दी** · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Veles को OpenRouter, Anthropic, OpenAI, Gemini, local models, या एक CLI subscription
के बीच switch करें। पूरी provider सूची: [providers संदर्भ](../reference/providers.md)।

## प्रति command एक provider चुनें

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## प्रोजेक्ट के लिए एक default set करें

`<project>/.veles/config.toml` में एक base डालें:

```toml
[provider]
default = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

या `~/.veles/config.toml` में एक user-global default:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## API key प्रदान करें

Cloud providers को एक key चाहिए। इसे OS keychain में एक बार संग्रहित करें:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…या [environment variable](../reference/environment-variables.md) export करें:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Lookup क्रम: keychain (project scope) → keychain (default) → env var। Keys config
files में **कभी** नहीं लिखे जाते।

## एक पूरी तरह local model का उपयोग करें (बिना key)

[Ollama](https://ollama.com) install करें, एक model pull करें, और Veles को उस पर इंगित करें:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

local providers पर tool calling **default रूप से off है**। जब आप एक tool-सक्षम model
चुन लें तो इसे सक्षम करें:

```bash
export VELES_LOCAL_TOOLS=1
```

यदि आपका server default port पर नहीं है तो endpoints override करें:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## एक Claude / Gemini CLI subscription को delegate करें

यदि आपके पास `claude` या `gemini` CLI authenticated है, तो Veles उसे चला सकता है:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

कोई API key नहीं चाहिए — CLI auth संभालता है।

## उपलब्ध models सूचीबद्ध करें

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## आगे

- [विभिन्न tasks को विभिन्न models पर route करें](per-task-routing.md) — compression
  के लिए सस्ता model, planning के लिए मज़बूत model।
