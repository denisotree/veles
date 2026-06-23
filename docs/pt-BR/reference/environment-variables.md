# Variáveis de ambiente

> 🌐 **Idiomas:** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · [繁體中文](../../zh-TW/reference/environment-variables.md) · [日本語](../../ja/reference/environment-variables.md) · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · **Português (BR)** · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · [العربية](../../ar/reference/environment-variables.md) · [हिन्दी](../../hi/reference/environment-variables.md) · [বাংলা](../../bn/reference/environment-variables.md) · [Tiếng Việt](../../vi/reference/environment-variables.md)

O Veles lê estas variáveis em tempo de execução. O ideal é guardar chaves de API
e tokens no chaveiro do SO (`veles secret set …`); as variáveis de ambiente são o
fallback e o mecanismo de sobrescrita.

## Chaves de API dos provedores

Cascata de busca de chave de API: chaveiro do SO (escopo do projeto) → chaveiro do
SO (escopo default) → variável de ambiente.

| Variável | Provedor | Observações |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Provedor padrão |
| `ANTHROPIC_API_KEY` | anthropic | API direta da Anthropic |
| `OPENAI_API_KEY` | openai | API direta da OpenAI |
| `GEMINI_API_KEY` | gemini | Chave primária do Google Gemini |
| `GOOGLE_API_KEY` | gemini | Fallback do Google Gemini |

`claude-cli` e `gemini-cli` se autenticam pelos próprios binários — sem variável de ambiente.

## Provedores locais

| Variável | Padrão | Finalidade |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint do Ollama |
| `OLLAMA_HOST` | segue `OLLAMA_BASE_URL` | Host do Ollama para embeddings |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint do servidor llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (obrigatório) | Endpoint para o provedor `openai-compat` |
| `VELES_LOCAL_TOOLS` | desligado | Habilita chamada de tools em provedores locais (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | padrão do provedor | Sobrescreve o modelo de embedding do Ollama |

## Canais e daemon

| Variável | Padrão | Finalidade |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token do bot do Telegram para `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL base do daemon usada pelos gateways de canal |
| `VELES_DAEMON_TOKEN` | — | Token bearer para autenticação do daemon |

## Caminhos e locale

| Variável | Padrão | Finalidade |
|---|---|---|
| `VELES_USER_HOME` | `~` | Sobrescreve o home que contém `~/.veles/` (estado, cache, índice do chaveiro) |
| `VELES_HOME` | — | Alias legado de `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Sobrescreve o caminho do registry multiprojeto |
| `VELES_LOCALE` | `[user] language` ou `en` | Sobrescreve o locale ativo da UI em uma única execução |
| `VELES_LOG_LEVEL` | `INFO` | Verbosidade de log/daemon (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Sobrescreve o nome do arquivo de config (testes) |

## Flags de comportamento e funcionalidades

| Variável | Padrão | Finalidade |
|---|---|---|
| `VELES_NO_WIZARD` | desligado | Pula o assistente de primeira execução (também precisa de um TTY) |
| `VELES_MANAGER_MODE` | desligado | Força o gerente multiagente em `veles run` (`1` liga / `0` desliga via kill switch) |
| `VELES_VERIFY_MODE` | desligado | Força a passada verify→escalate em `veles run` (`1` liga / `0` desliga via kill switch) |
| `VELES_FENCED_TOOLS` | desligado | Executa tools pelo caminho de execução cercado/em sandbox |
| `VELES_TRUST_AUTO_ALLOW` | desligado | Ignora a escada de confiança (CI / autopilot / subagentes pré-autorizados) |
| `VELES_SANDBOX_ROOTS` | projeto + `~/.veles` | Sobrescrita separada por `:` das raízes de leitura/escrita da sandbox |
| `VELES_FETCH_ALLOW_PRIVATE` | desligado | Permite que tools acessem endereços RFC-1918 / privados |
| `VELES_MEMORY_RERANK` | ligado | Reranking vetorial do recall de memória (`0`/`false` desativa) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend de busca na web para `research` e `web_search` |

## Registries

| Variável | Finalidade |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Fonte para `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Fonte para `veles browse modules` |

## Internas / testes

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — internas; você não deveria
precisar defini-las.
