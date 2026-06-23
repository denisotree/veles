# Variáveis de ambiente

> 🌐 **Idiomas:** **English** · [Русский](../../ru/reference/environment-variables.md)

O Veles lê estas variáveis em tempo de execução. Chaves de API e tokens são mais bem armazenados no
keychain do SO (`veles secret set …`); as variáveis de ambiente são o fallback e o override.

## Chaves de API dos provedores

Cascata de busca de chave de API: keychain do SO (escopo de projeto) → keychain do SO (escopo default)
→ variável de ambiente.

| Variável | Provedor | Observações |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Provedor padrão |
| `ANTHROPIC_API_KEY` | anthropic | API direta da Anthropic |
| `OPENAI_API_KEY` | openai | API direta da OpenAI |
| `GEMINI_API_KEY` | gemini | Chave principal para o Google Gemini |
| `GOOGLE_API_KEY` | gemini | Fallback para o Google Gemini |

`claude-cli` e `gemini-cli` se autenticam por meio dos próprios binários — sem variável de ambiente.

## Provedores locais

| Variável | Padrão | Finalidade |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint do Ollama |
| `OLLAMA_HOST` | segue `OLLAMA_BASE_URL` | Host do Ollama para embeddings |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint do servidor llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (obrigatório) | Endpoint para o provedor `openai-compat` |
| `VELES_LOCAL_TOOLS` | desligado | Habilita chamadas de ferramenta em provedores locais (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | padrão do provedor | Sobrescreve o modelo de embedding do Ollama |

## Canais e daemon

| Variável | Padrão | Finalidade |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token do bot do Telegram para `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL base do daemon usada pelos gateways de canal |
| `VELES_DAEMON_TOKEN` | — | Bearer token para autenticação do daemon |

## Caminhos e locale

| Variável | Padrão | Finalidade |
|---|---|---|
| `VELES_USER_HOME` | `~` | Sobrescreve o home que contém `~/.veles/` (estado, cache, índice do keychain) |
| `VELES_HOME` | — | Alias legado para `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Sobrescreve o caminho do registry multiprojeto |
| `VELES_LOCALE` | `[user] language` ou `en` | Sobrescreve o locale ativo da interface por execução |
| `VELES_LOG_LEVEL` | `INFO` | Verbosidade de daemon/log (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Sobrescreve o nome do arquivo de configuração (testes) |

## Flags de comportamento e funcionalidades

| Variável | Padrão | Finalidade |
|---|---|---|
| `VELES_NO_WIZARD` | desligado | Pula o assistente da primeira execução (também precisa de um TTY) |
| `VELES_MANAGER_MODE` | desligado | Força o gerenciador multiagente para `veles run` (`1` liga / `0` kill switch) |
| `VELES_FENCED_TOOLS` | desligado | Executa ferramentas no caminho de execução cercado/sandboxed |
| `VELES_TRUST_AUTO_ALLOW` | desligado | Ignora a escada de confiança (CI / autopilot / subagentes pré-autorizados) |
| `VELES_SANDBOX_ROOTS` | projeto + `~/.veles` | Override, separado por `:`, das raízes de leitura/escrita do sandbox |
| `VELES_FETCH_ALLOW_PRIVATE` | desligado | Permite que ferramentas acessem endereços RFC-1918 / privados |
| `VELES_MEMORY_RERANK` | ligado | Reranking vetorial da recuperação de memória (`0`/`false` desabilita) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend de busca na web para `research` e `web_search` |

## Registries

| Variável | Finalidade |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Fonte para `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Fonte para `veles browse modules` |

## Internas / testes

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — internas; você não deveria precisar
defini-las.
