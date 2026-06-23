# How to configure providers

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Switch Veles between OpenRouter, Anthropic, OpenAI, Gemini, local models, or a CLI
subscription. Full provider list: [providers reference](../reference/providers.md).

## Pick a provider per command

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Set a default for the project

Put a base in `<project>/.veles/config.toml`:

```toml
[provider]
default = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

Or a user-global default in `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Provide the API key

Cloud providers need a key. Store it once in the OS keychain:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…or export the [environment variable](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Lookup order: keychain (project scope) → keychain (default) → env var. Keys are
**never** written to config files.

## Use a fully local model (no key)

Install [Ollama](https://ollama.com), pull a model, and point Veles at it:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

Tool calling is **off by default** on local providers. Enable it once you've
picked a tool-capable model:

```bash
export VELES_LOCAL_TOOLS=1
```

Override endpoints if your server isn't on the default port:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Delegate to a Claude / Gemini CLI subscription

If you have the `claude` or `gemini` CLI authenticated, Veles can drive it:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

No API key needed — the CLI handles auth.

## List available models

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## Next

- [Route different tasks to different models](per-task-routing.md) — cheap model
  for compression, strong model for planning.
