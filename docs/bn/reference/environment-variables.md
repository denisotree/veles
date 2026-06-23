# Environment variables

> 🌐 **Languages:** [English](../../en/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · **বাংলা**

Veles runtime-এ এগুলো পড়ে। API key ও token গুলো OS keychain-এ রাখাই সবচেয়ে ভালো
(`veles secret set …`); env var গুলো fallback এবং override হিসেবে কাজ করে।

## Provider API keys

API-key খোঁজার ক্রম (cascade): OS keychain (project scope) → OS keychain (default scope)
→ environment variable।

| Variable | Provider | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | ডিফল্ট provider |
| `ANTHROPIC_API_KEY` | anthropic | সরাসরি Anthropic API |
| `OPENAI_API_KEY` | openai | সরাসরি OpenAI API |
| `GEMINI_API_KEY` | gemini | Google Gemini-এর প্রাথমিক key |
| `GOOGLE_API_KEY` | gemini | Google Gemini-এর fallback |

`claude-cli` ও `gemini-cli` নিজেদের binary-র মাধ্যমে authenticate করে — কোনো env var লাগে না।

## লোকাল provider

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama endpoint |
| `OLLAMA_HOST` | `OLLAMA_BASE_URL` অনুসরণ করে | embedding-এর জন্য Ollama host |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp server endpoint |
| `OPENAI_COMPAT_BASE_URL` | — (আবশ্যক) | `openai-compat` provider-এর endpoint |
| `VELES_LOCAL_TOOLS` | off | লোকাল provider-এ tool calling সক্রিয় করে (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | provider default | Ollama embedding model override করে |

## Channels ও daemon

| Variable | Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | `veles channel run --channel telegram`-এর জন্য Telegram bot token |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | channel gateway-গুলো যে daemon base URL ব্যবহার করে |
| `VELES_DAEMON_TOKEN` | — | daemon authentication-এর জন্য Bearer token |

## Paths ও locale

| Variable | Default | Purpose |
|---|---|---|
| `VELES_USER_HOME` | `~` | `~/.veles/` (state, cache, keychain index) ধারণকারী home override করে |
| `VELES_HOME` | — | `VELES_USER_HOME`-এর legacy alias |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | multi-project registry path override করে |
| `VELES_LOCALE` | `[user] language` অথবা `en` | একটি run-এর জন্য সক্রিয় UI locale override করে |
| `VELES_LOG_LEVEL` | `INFO` | Daemon/log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | config filename override করে (testing) |

## আচরণ ও feature flag

| Variable | Default | Purpose |
|---|---|---|
| `VELES_NO_WIZARD` | off | first-run wizard বাদ দেয় (এর জন্য একটি TTY-ও লাগে) |
| `VELES_MANAGER_MODE` | off | `veles run`-এর জন্য multi-agent manager জোর করে (`1` চালু / `0` kill switch) |
| `VELES_FENCED_TOOLS` | off | tool-গুলোকে fenced/sandboxed execution path-এ চালায় |
| `VELES_TRUST_AUTO_ALLOW` | off | trust ladder bypass করে (CI / autopilot / আগে-অনুমোদিত sub-agent) |
| `VELES_SANDBOX_ROOTS` | project + `~/.veles` | read/write sandbox root-গুলোর `:`-দিয়ে আলাদা করা override |
| `VELES_FETCH_ALLOW_PRIVATE` | off | tool-গুলোকে RFC-1918 / private ঠিকানা fetch করতে দেয় |
| `VELES_MEMORY_RERANK` | on | memory recall-এর vector reranking (`0`/`false` নিষ্ক্রিয় করে) |
| `VELES_WEB_SEARCH_BACKEND` | auto | `research` ও `web_search`-এর জন্য web search backend |

## Registries

| Variable | Purpose |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills`-এর source |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules`-এর source |

## অভ্যন্তরীণ / testing

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — অভ্যন্তরীণ; এগুলো সেট করার
প্রয়োজন আপনার হওয়ার কথা নয়।
