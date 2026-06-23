# Variabili d'ambiente

> 🌐 **Lingue:** [English](../../en/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · **Italiano**

Veles le legge a runtime. Le chiavi API e i token è meglio conservarli nel portachiavi
del SO (`veles secret set …`); le variabili d'ambiente sono il fallback e l'override.

## Chiavi API dei provider

Cascata di ricerca delle chiavi API: portachiavi del SO (scope progetto) → portachiavi del SO (scope default)
→ variabile d'ambiente.

| Variabile | Provider | Note |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Provider di default |
| `ANTHROPIC_API_KEY` | anthropic | API Anthropic diretta |
| `OPENAI_API_KEY` | openai | API OpenAI diretta |
| `GEMINI_API_KEY` | gemini | Chiave primaria per Google Gemini |
| `GOOGLE_API_KEY` | gemini | Fallback per Google Gemini |

`claude-cli` e `gemini-cli` si autenticano tramite i propri binari — nessuna variabile d'ambiente.

## Provider locali

| Variabile | Default | Scopo |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint di Ollama |
| `OLLAMA_HOST` | segue `OLLAMA_BASE_URL` | Host Ollama per gli embedding |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint del server llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (richiesto) | Endpoint per il provider `openai-compat` |
| `VELES_LOCAL_TOOLS` | off | Abilita la chiamata di tool sui provider locali (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | default del provider | Sovrascrive il modello di embedding di Ollama |

## Canali e daemon

| Variabile | Default | Scopo |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token del bot Telegram per `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL base del daemon usato dai gateway dei canali |
| `VELES_DAEMON_TOKEN` | — | Bearer token per l'autenticazione del daemon |

## Percorsi e locale

| Variabile | Default | Scopo |
|---|---|---|
| `VELES_USER_HOME` | `~` | Sovrascrive la home che contiene `~/.veles/` (stato, cache, indice del portachiavi) |
| `VELES_HOME` | — | Alias legacy per `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Sovrascrive il percorso del registro multi-progetto |
| `VELES_LOCALE` | `[user] language` o `en` | Sovrascrive la locale UI attiva per una sola esecuzione |
| `VELES_LOG_LEVEL` | `INFO` | Verbosità daemon/log (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Sovrascrive il nome del file di config (testing) |

## Comportamento e feature flag

| Variabile | Default | Scopo |
|---|---|---|
| `VELES_NO_WIZARD` | off | Salta la procedura guidata al primo avvio (richiede anche un TTY) |
| `VELES_MANAGER_MODE` | off | Forza il manager multi-agente per `veles run` (`1` on / `0` kill switch) |
| `VELES_FENCED_TOOLS` | off | Esegue i tool nel percorso di esecuzione recintato/sandboxed |
| `VELES_TRUST_AUTO_ALLOW` | off | Aggira la trust ladder (CI / autopilot / sub-agenti pre-autorizzati) |
| `VELES_SANDBOX_ROOTS` | progetto + `~/.veles` | Override separato da `:` delle root di lettura/scrittura della sandbox |
| `VELES_FETCH_ALLOW_PRIVATE` | off | Consente ai tool di recuperare indirizzi RFC-1918 / privati |
| `VELES_MEMORY_RERANK` | on | Reranking vettoriale del recall di memoria (`0`/`false` disabilita) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend di ricerca web per `research` e `web_search` |

## Registri

| Variabile | Scopo |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Fonte per `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Fonte per `veles browse modules` |

## Interno / testing

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — interne; non dovresti aver bisogno
di impostarle.
