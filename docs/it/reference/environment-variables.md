# Variabili d'ambiente

> 🌐 **Lingue:** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · [繁體中文](../../zh-TW/reference/environment-variables.md) · [日本語](../../ja/reference/environment-variables.md) · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · **Italiano** · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · [العربية](../../ar/reference/environment-variables.md) · [हिन्दी](../../hi/reference/environment-variables.md) · [বাংলা](../../bn/reference/environment-variables.md) · [Tiếng Việt](../../vi/reference/environment-variables.md)

Veles legge queste variabili a runtime. È preferibile conservare chiavi API e
token nel keychain del sistema operativo (`veles secret set …`); le variabili
d'ambiente sono il ripiego e l'override.

## Chiavi API dei provider

Cascata di ricerca della chiave API: keychain del SO (scope di progetto) →
keychain del SO (scope di default) → variabile d'ambiente.

| Variabile | Provider | Note |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Provider di default |
| `ANTHROPIC_API_KEY` | anthropic | API Anthropic diretta |
| `OPENAI_API_KEY` | openai | API OpenAI diretta |
| `GEMINI_API_KEY` | gemini | Chiave primaria per Google Gemini |
| `GOOGLE_API_KEY` | gemini | Ripiego per Google Gemini |

`claude-cli` e `gemini-cli` si autenticano tramite i propri binari — nessuna
variabile d'ambiente.

## Provider locali

| Variabile | Default | Scopo |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint Ollama |
| `OLLAMA_HOST` | segue `OLLAMA_BASE_URL` | Host Ollama per gli embedding |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint del server llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (obbligatorio) | Endpoint per il provider `openai-compat` |
| `VELES_LOCAL_TOOLS` | off | Abilita la chiamata-tool sui provider locali (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | default del provider | Sovrascrive il modello di embedding di Ollama |

## Canali e daemon

| Variabile | Default | Scopo |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token del bot Telegram per `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL di base del daemon usato dai gateway dei canali |
| `VELES_DAEMON_TOKEN` | — | Bearer token per l'autenticazione del daemon |

## Percorsi e locale

| Variabile | Default | Scopo |
|---|---|---|
| `VELES_USER_HOME` | `~` | Sovrascrive la home che contiene `~/.veles/` (stato, cache, indice del keychain) |
| `VELES_HOME` | — | Alias legacy di `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Sovrascrive il percorso del registro multi-progetto |
| `VELES_LOCALE` | `[user] language` o `en` | Sovrascrive la locale dell'interfaccia attiva per una singola esecuzione |
| `VELES_LOG_LEVEL` | `INFO` | Verbosità di daemon/log (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Sovrascrive il nome del file di config (test) |

## Comportamento e feature flag

| Variabile | Default | Scopo |
|---|---|---|
| `VELES_NO_WIZARD` | off | Salta la procedura guidata al primo avvio (richiede anche un TTY) |
| `VELES_MANAGER_MODE` | off | Forza il manager multi-agente per `veles run` (`1` on / `0` kill switch) |
| `VELES_VERIFY_MODE` | off | Forza il passaggio verify→escalate per `veles run` (`1` on / `0` kill switch) |
| `VELES_FENCED_TOOLS` | off | Esegue i tool nel percorso di esecuzione recintato/in sandbox |
| `VELES_TRUST_AUTO_ALLOW` | off | Bypassa la scala di fiducia (CI / autopilot / sub-agenti pre-autorizzati) |
| `VELES_SANDBOX_ROOTS` | progetto + `~/.veles` | Override separato da `:` delle radici della sandbox di lettura/scrittura |
| `VELES_FETCH_ALLOW_PRIVATE` | off | Consente ai tool di raggiungere indirizzi RFC-1918 / privati |
| `VELES_MEMORY_RERANK` | on | Re-ranking vettoriale del recall della memoria (`0`/`false` lo disabilita) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend di ricerca web per `research` e `web_search` |

## Registri

| Variabile | Scopo |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Sorgente per `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Sorgente per `veles browse modules` |

## Interne / test

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — interne; non dovresti aver
bisogno di impostarle.
