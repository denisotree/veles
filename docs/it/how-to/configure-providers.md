# Come configurare i provider

> 🌐 **Lingue:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Sposta Veles tra OpenRouter, Anthropic, OpenAI, Gemini, modelli locali o un
abbonamento CLI. Elenco completo dei provider: [riferimento dei provider](../reference/providers.md).

## Scegliere un provider per comando

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Impostare un default per il progetto

Metti una base in `<project>/.veles/config.toml`:

```toml
[provider]
default = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

Oppure un default globale utente in `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Fornire la chiave API

I provider cloud richiedono una chiave. Conservala una volta nel keychain del
sistema operativo:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…oppure esporta la [variabile d'ambiente](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Ordine di ricerca: keychain (scope di progetto) → keychain (default) → variabile
d'ambiente. Le chiavi non vengono **mai** scritte nei file di config.

## Usare un modello completamente locale (senza chiave)

Installa [Ollama](https://ollama.com), scarica un modello e punta Veles su di
esso:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

La chiamata-tool è **disattivata di default** sui provider locali. Abilitala una
volta scelto un modello capace di gestire i tool:

```bash
export VELES_LOCAL_TOOLS=1
```

Sovrascrivi gli endpoint se il tuo server non è sulla porta di default:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Delegare a un abbonamento CLI di Claude / Gemini

Se hai la CLI `claude` o `gemini` autenticata, Veles può pilotarla:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

Nessuna chiave API necessaria — l'autenticazione la gestisce la CLI.

## Elencare i modelli disponibili

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## Passo successivo

- [Instradare task diversi verso modelli diversi](per-task-routing.md) — modello
  economico per la compressione, modello potente per la pianificazione.
