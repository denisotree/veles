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
[engine]
provider = "openrouter"                 # provider name
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

La chiamata-tool viene **rilevata** da ciò che il server dichiara. Forzala con
`VELES_LOCAL_TOOLS=1` (o disattivala con `=0`).

Sovrascrivi gli endpoint se il tuo server non è sulla porta di default:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Aggiungere il tuo provider

Qualsiasi API ospitata compatibile con OpenAI, o un server che gestisci tu, diventa un
provider con una voce in `~/.veles/providers.toml` — nessun codice. L'id è il nome della
tabella:

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

Poi usalo come uno integrato:

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| Chiave | Significato |
|---|---|
| `kind` | `openai-api` (un'API ospitata) o `local` (un server che gestisci tu) |
| `base_url` | l'endpoint compatibile con OpenAI, che termina con `/v1` (o l'equivalente del provider) |
| `base_url_env` | una variabile d'ambiente che, se impostata, sovrascrive `base_url` |
| `key_env` | nomi delle variabili d'ambiente da cui leggere la chiave; il keychain viene provato per primo |
| `label`, `tagline` | come le mostrano le procedure guidate |
| `tools` | `auto` (default), `on` o `off` — se il modello riceve le chiamate-tool |

Una voce con un id integrato (`[providers.ollama]`) modifica le impostazioni di quel
provider — il suo `base_url`, per esempio — ma non il suo tipo. Un file errato viene
segnalato una sola volta, e Veles prosegue con i provider integrati; `veles doctor`
elenca cosa non va.

Punti di partenza per le API più comuni — **non verificati dal team di Veles**, controlla
la documentazione del provider per l'endpoint attuale:

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

## Delegare a un abbonamento Claude / ChatGPT / Google

Se hai la CLI `claude` autenticata, Veles può pilotarla:

```bash
veles run --provider claude-cli "..."
```

Per un abbonamento ChatGPT, installa la Codex CLI ed effettua l'accesso una volta (`codex login`):

```bash
veles run --provider codex --model gpt-6-luna "..."
veles models codex      # the models your account has
```

Per un abbonamento Google, installa ed effettua l'accesso una volta alla Antigravity CLI
(`agy`), poi nomina il suo provider — il modulo `antigravity-cli` si installa da solo dai
tuoi registri connessi a quell'esecuzione:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
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
