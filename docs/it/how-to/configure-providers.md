# Come configurare i provider

> 🌐 **Lingue:** [English](../../en/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · **Italiano**

Passa Veles tra OpenRouter, Anthropic, OpenAI, Gemini, modelli locali o un abbonamento
CLI. Elenco completo dei provider: [riferimento provider](../reference/providers.md).

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
default = "openrouter:anthropic/claude-sonnet-4.6"
```

Oppure un default globale per l'utente in `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Fornire la chiave API

I provider cloud richiedono una chiave. Salvala una volta nel portachiavi del sistema operativo:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…oppure esporta la [variabile d'ambiente](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Ordine di ricerca: portachiavi (ambito progetto) → portachiavi (default) → variabile d'ambiente. Le chiavi
**non vengono mai** scritte nei file di configurazione.

## Usare un modello completamente locale (senza chiave)

Installa [Ollama](https://ollama.com), scarica un modello e indirizza Veles ad esso:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

Il tool calling è **disattivato di default** sui provider locali. Abilitalo una volta che hai
scelto un modello capace di usare i tool:

```bash
export VELES_LOCAL_TOOLS=1
```

Sovrascrivi gli endpoint se il tuo server non è sulla porta di default:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Delegare a un abbonamento CLI Claude / Gemini

Se hai la CLI `claude` o `gemini` autenticata, Veles può pilotarla:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

Nessuna chiave API necessaria — la CLI gestisce l'autenticazione.

## Elencare i modelli disponibili

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## Prossimi passi

- [Instradare task diversi verso modelli diversi](per-task-routing.md) — modello economico
  per la compressione, modello potente per la pianificazione.
