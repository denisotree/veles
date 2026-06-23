# Providers कैसे configure करें

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/how-to/configure-providers.md)

Veles को OpenRouter, Anthropic, OpenAI, Gemini, local models, या किसी CLI
subscription के बीच switch करें। पूरी provider list: [providers reference](../reference/providers.md)।

## हर command के लिए provider चुनें

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## project के लिए default सेट करें

`<project>/.veles/config.toml` में एक base डालें:

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
```

या `~/.veles/config.toml` में एक user-global default:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## API key दें

Cloud providers को एक key चाहिए। इसे एक बार OS keychain में store करें:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…या [environment variable](../reference/environment-variables.md) export करें:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Lookup क्रम: keychain (project scope) → keychain (default) → env var। Keys
config files में **कभी** नहीं लिखी जातीं।

## पूरी तरह local model इस्तेमाल करें (बिना key)

[Ollama](https://ollama.com) install करें, एक model pull करें, और Veles को उस पर point करें:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

Local providers पर tool calling **default रूप से बंद** है। एक बार
tool-capable model चुन लेने के बाद इसे enable करें:

```bash
export VELES_LOCAL_TOOLS=1
```

अगर आपका server default port पर नहीं है तो endpoints override करें:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## किसी Claude / Gemini CLI subscription को delegate करें

अगर आपके पास authenticated `claude` या `gemini` CLI है, तो Veles उसे drive कर सकता है:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

किसी API key की ज़रूरत नहीं — auth CLI खुद संभालता है।

## उपलब्ध models की list देखें

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## आगे

- [अलग-अलग tasks को अलग-अलग models पर route करें](per-task-routing.md) — compression के लिए
  सस्ता model, planning के लिए मज़बूत model।
