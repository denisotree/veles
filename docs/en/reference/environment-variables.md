# Environment variables

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/environment-variables.md)

Veles reads these at runtime. API keys and tokens are best stored in the OS
keychain (`veles secret set …`); env vars are the fallback and the override.

## Provider API keys

API-key lookup cascade: OS keychain (project scope) → OS keychain (default scope)
→ environment variable.

| Variable | Provider | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Default provider |
| `ANTHROPIC_API_KEY` | anthropic | Direct Anthropic API |
| `OPENAI_API_KEY` | openai | Direct OpenAI API |
| `GEMINI_API_KEY` | gemini | Primary key for Google Gemini |
| `GOOGLE_API_KEY` | gemini | Fallback for Google Gemini |

`claude-cli` and `gemini-cli` authenticate through their own binaries — no env var.

## Local providers

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama endpoint |
| `OLLAMA_HOST` | follows `OLLAMA_BASE_URL` | Ollama host for embeddings |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp server endpoint |
| `OPENAI_COMPAT_BASE_URL` | — (required) | Endpoint for the `openai-compat` provider |
| `VELES_LOCAL_TOOLS` | off | Enable tool calling on local providers (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | provider default | Override the Ollama embedding model |

## Channels & daemon

| Variable | Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token for `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | Daemon base URL used by channel gateways |
| `VELES_DAEMON_TOKEN` | — | Bearer token for daemon authentication |

## Paths & locale

| Variable | Default | Purpose |
|---|---|---|
| `VELES_USER_HOME` | `~` | Override the home that holds `~/.veles/` (state, cache, keychain index) |
| `VELES_HOME` | — | Legacy alias for `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Override the multi-project registry path |
| `VELES_LOCALE` | `[user] language` or `en` | Override the active UI locale for one run |
| `VELES_LOG_LEVEL` | `INFO` | Daemon/log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Override the config filename (testing) |

## Behaviour & feature flags

| Variable | Default | Purpose |
|---|---|---|
| `VELES_NO_WIZARD` | off | Skip the first-run wizard (also needs a TTY) |
| `VELES_MANAGER_MODE` | off | Force multi-agent manager for `veles run` (`1` on / `0` kill switch) |
| `VELES_VERIFY_MODE` | off | Force the verify→escalate pass for `veles run` (`1` on / `0` kill switch) |
| `VELES_FENCED_TOOLS` | off | Run tools in the fenced/sandboxed execution path |
| `VELES_TRUST_AUTO_ALLOW` | off | Bypass the trust ladder (CI / autopilot / pre-authorised sub-agents) |
| `VELES_SANDBOX_ROOTS` | project + `~/.veles` | `:`-separated override of the read/write sandbox roots |
| `VELES_FETCH_ALLOW_PRIVATE` | off | Allow tools to fetch RFC-1918 / private addresses |
| `VELES_MEMORY_RERANK` | on | Vector reranking of memory recall (`0`/`false` disables) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Web search backend for `research` and `web_search` |

## Registries

| Variable | Purpose |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Source for `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Source for `veles browse modules` |

## Internal / testing

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — internal; you should not need
to set these.
