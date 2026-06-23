# Environment variables

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/reference/environment-variables.md)

Veles इन्हें runtime पर पढ़ता है। API keys और tokens को OS keychain में रखना सबसे
अच्छा है (`veles secret set …`); env vars fallback और override हैं।

## Provider API keys

API-key lookup cascade: OS keychain (project scope) → OS keychain (default scope)
→ environment variable।

| Variable | Provider | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Default provider |
| `ANTHROPIC_API_KEY` | anthropic | Direct Anthropic API |
| `OPENAI_API_KEY` | openai | Direct OpenAI API |
| `GEMINI_API_KEY` | gemini | Google Gemini के लिए primary key |
| `GOOGLE_API_KEY` | gemini | Google Gemini के लिए fallback |

`claude-cli` और `gemini-cli` अपने ही binaries के ज़रिए authenticate होते हैं — कोई
env var नहीं।

## Local providers

| Variable | Default | उद्देश्य |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama endpoint |
| `OLLAMA_HOST` | follows `OLLAMA_BASE_URL` | Embeddings के लिए Ollama host |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp server endpoint |
| `OPENAI_COMPAT_BASE_URL` | — (required) | `openai-compat` provider के लिए endpoint |
| `VELES_LOCAL_TOOLS` | off | Local providers पर tool calling enable करें (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | provider default | Ollama embedding मॉडल override करें |

## Channels & daemon

| Variable | Default | उद्देश्य |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | `veles channel run --channel telegram` के लिए Telegram bot token |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | channel gateways द्वारा इस्तेमाल किया जाने वाला daemon base URL |
| `VELES_DAEMON_TOKEN` | — | Daemon authentication के लिए bearer token |

## Paths & locale

| Variable | Default | उद्देश्य |
|---|---|---|
| `VELES_USER_HOME` | `~` | `~/.veles/` (state, cache, keychain index) रखने वाले home को override करें |
| `VELES_HOME` | — | `VELES_USER_HOME` के लिए legacy alias |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Multi-project registry path override करें |
| `VELES_LOCALE` | `[user] language` or `en` | एक रन के लिए सक्रिय UI locale override करें |
| `VELES_LOG_LEVEL` | `INFO` | Daemon/log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | config filename override करें (testing) |

## Behaviour & feature flags

| Variable | Default | उद्देश्य |
|---|---|---|
| `VELES_NO_WIZARD` | off | पहली-बार चलने वाले wizard को skip करें (एक TTY भी चाहिए) |
| `VELES_MANAGER_MODE` | off | `veles run` के लिए multi-agent manager force करें (`1` on / `0` kill switch) |
| `VELES_FENCED_TOOLS` | off | Tools को fenced/sandboxed execution path में चलाएँ |
| `VELES_TRUST_AUTO_ALLOW` | off | Trust ladder को bypass करें (CI / autopilot / pre-authorised sub-agents) |
| `VELES_SANDBOX_ROOTS` | project + `~/.veles` | read/write sandbox roots का `:`-separated override |
| `VELES_FETCH_ALLOW_PRIVATE` | off | Tools को RFC-1918 / private addresses fetch करने दें |
| `VELES_MEMORY_RERANK` | on | Memory recall का vector reranking (`0`/`false` बंद करता है) |
| `VELES_WEB_SEARCH_BACKEND` | auto | `research` और `web_search` के लिए web search backend |

## Registries

| Variable | उद्देश्य |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills` के लिए source |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules` के लिए source |

## Internal / testing

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — internal; आपको इन्हें सेट करने
की ज़रूरत नहीं होनी चाहिए।
