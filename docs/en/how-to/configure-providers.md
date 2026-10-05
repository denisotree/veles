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
[engine]
provider = "openrouter"                # provider name
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

Tool calling is **detected** from what the server advertises. Force it with
`VELES_LOCAL_TOOLS=1` (or off with `=0`).

Override endpoints if your server isn't on the default port:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Add your own provider

Any hosted OpenAI-compatible API, or a server you run, becomes a provider with an
entry in `~/.veles/providers.toml` — no code. The id is the table name:

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

Then use it like any builtin:

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| Key | Meaning |
|---|---|
| `kind` | `openai-api` (a hosted API) or `local` (a server you run) |
| `base_url` | the OpenAI-compatible endpoint, ending in `/v1` (or the provider's equivalent) |
| `base_url_env` | an env var that overrides `base_url` when set |
| `key_env` | env var names the key is read from; the keychain is tried first |
| `label`, `tagline` | how the wizards show it |
| `tools` | `auto` (default), `on` or `off` — whether the model gets tool calls |

An entry with a builtin id (`[providers.ollama]`) changes that provider's settings —
its `base_url`, say — but not its kind. A broken file is reported once, and Veles goes
on with the builtin providers; `veles doctor` lists what is wrong with it.

Starting points for common APIs — **not verified by the Veles team**, check the
provider's documentation for the current endpoint:

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

## Delegate to a Claude / Google subscription

If you have the `claude` CLI authenticated, Veles can drive it:

```bash
veles run --provider claude-cli "..."
```

For a Google subscription, install and log in to the Antigravity CLI (`agy`) once,
then name its provider — the `antigravity-cli` module installs itself from your
connected registries on that run:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
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
