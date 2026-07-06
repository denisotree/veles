# Environment variables

> 🌐 **भाषाएँ:** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · [繁體中文](../../zh-TW/reference/environment-variables.md) · [日本語](../../ja/reference/environment-variables.md) · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · [العربية](../../ar/reference/environment-variables.md) · **हिन्दी** · [বাংলা](../../bn/reference/environment-variables.md) · [Tiếng Việt](../../vi/reference/environment-variables.md)

Veles इन्हें runtime पर पढ़ता है। API keys और tokens को OS keychain में रखना सबसे
अच्छा है (`veles secret set …`); env vars fallback और override के रूप में हैं।

## Provider API keys

API-key lookup cascade: OS keychain (project scope) → OS keychain (default scope)
→ environment variable।

| Variable | Provider | टिप्पणियाँ |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Default provider |
| `ANTHROPIC_API_KEY` | anthropic | Direct Anthropic API |
| `OPENAI_API_KEY` | openai | Direct OpenAI API |
| `GEMINI_API_KEY` | gemini | Google Gemini के लिए primary key |
| `GOOGLE_API_KEY` | gemini | Google Gemini के लिए fallback |

`claude-cli` और `gemini-cli` अपने ही binaries के ज़रिए authenticate होते हैं — कोई env var नहीं।

## Local providers

| Variable | Default | उद्देश्य |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama endpoint |
| `OLLAMA_HOST` | `OLLAMA_BASE_URL` का अनुसरण करता है | embeddings के लिए Ollama host |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp server endpoint |
| `OPENAI_COMPAT_BASE_URL` | — (आवश्यक) | `openai-compat` provider के लिए endpoint |
| `VELES_LOCAL_TOOLS` | off | local providers पर tool calling सक्षम करें (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | provider default | Ollama embedding model override करें |

## Channels और daemon

| Variable | Default | उद्देश्य |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | `veles channel run --channel telegram` के लिए Telegram bot token |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | channel gateways द्वारा उपयोग किया जाने वाला daemon base URL |
| `VELES_DAEMON_TOKEN` | — | daemon authentication के लिए Bearer token |

## Paths और locale

| Variable | Default | उद्देश्य |
|---|---|---|
| `VELES_USER_HOME` | `~` | `~/.veles/` (state, cache, keychain index) रखने वाली home को override करें |
| `VELES_HOME` | — | `VELES_USER_HOME` के लिए legacy alias |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | multi-project registry path override करें |
| `VELES_LOCALE` | `[user] language` या `en` | एक run के लिए सक्रिय UI locale override करें |
| `VELES_LOG_LEVEL` | `INFO` | Daemon/log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | config filename override करें (testing) |

## Behaviour और feature flags

| Variable | Default | उद्देश्य |
|---|---|---|
| `VELES_NO_WIZARD` | off | पहली बार चलने वाला wizard छोड़ें (TTY भी चाहिए) |
| `VELES_MANAGER_MODE` | off | `veles run` के लिए multi-agent manager बाध्य करें (`1` on / `0` kill switch) |
| `VELES_VERIFY_MODE` | off | `veles run` के लिए verify→escalate pass बाध्य करें (`1` on / `0` kill switch) |
| `VELES_FENCED_TOOLS` | off | tools को fenced/sandboxed execution path में चलाएँ |
| `VELES_TRUST_AUTO_ALLOW` | off | trust ladder को bypass करें (CI / autopilot / pre-authorised sub-agents) |
| `VELES_SANDBOX_ROOTS` | project + `~/.veles` | read/write sandbox roots का `:`-separated override |
| `VELES_FETCH_ALLOW_PRIVATE` | off | tools को RFC-1918 / private addresses fetch करने दें |
| `VELES_MEMORY_RERANK` | on | memory recall का vector reranking (`0`/`false` अक्षम करता है) |
| `VELES_WEB_SEARCH_BACKEND` | auto | `research` और `web_search` के लिए web search backend |

## Registries

| Variable | उद्देश्य |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills` के लिए source |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules` के लिए source |

## Internal / testing

| Variable | उद्देश्य |
|---|---|
| `VELES_BUNDLE_VERSION` | Internal; इसे set करने की आपको आवश्यकता नहीं होनी चाहिए |
| `VELES_REPL_SIMPLE` | full-screen `prompt_toolkit` app के बजाय सादा line-आधारित REPL loop बाध्य करने के लिए `1` पर set करें (सीमित terminals के लिए fallback) |
