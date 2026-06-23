# Variáveis de ambiente

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/environment-variables.md)

O Veles lê estas em runtime. As chaves de API e tokens são melhor guardadas no chaveiro
do SO (`veles secret set …`); as variáveis de ambiente são o recurso de reserva e a
sobreposição.

## Chaves de API dos fornecedores

Cascata de consulta da chave de API: chaveiro do SO (âmbito do projecto) → chaveiro do SO
(âmbito default) → variável de ambiente.

| Variável | Fornecedor | Notas |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Fornecedor predefinido |
| `ANTHROPIC_API_KEY` | anthropic | API directa da Anthropic |
| `OPENAI_API_KEY` | openai | API directa da OpenAI |
| `GEMINI_API_KEY` | gemini | Chave primária para o Google Gemini |
| `GOOGLE_API_KEY` | gemini | Reserva para o Google Gemini |

`claude-cli` e `gemini-cli` autenticam-se através dos seus próprios binários — sem
variável de ambiente.

## Fornecedores locais

| Variável | Predefinição | Finalidade |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint do Ollama |
| `OLLAMA_HOST` | segue `OLLAMA_BASE_URL` | Host do Ollama para embeddings |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint do servidor llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (obrigatória) | Endpoint para o fornecedor `openai-compat` |
| `VELES_LOCAL_TOOLS` | desligado | Activa a chamada a ferramentas nos fornecedores locais (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | predefinição do fornecedor | Sobrepõe o modelo de embeddings do Ollama |

## Canais e daemon

| Variável | Predefinição | Finalidade |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token do bot do Telegram para `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL base do daemon usado pelos gateways de canal |
| `VELES_DAEMON_TOKEN` | — | Bearer token para autenticação no daemon |

## Caminhos e locale

| Variável | Predefinição | Finalidade |
|---|---|---|
| `VELES_USER_HOME` | `~` | Sobrepõe a home que contém `~/.veles/` (estado, cache, índice do chaveiro) |
| `VELES_HOME` | — | Alias legado para `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Sobrepõe o caminho do registo multi-projecto |
| `VELES_LOCALE` | `[user] language` ou `en` | Sobrepõe o locale activo da UI numa execução |
| `VELES_LOG_LEVEL` | `INFO` | Verbosidade de daemon/log (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Sobrepõe o nome do ficheiro de configuração (testes) |

## Comportamento e feature flags

| Variável | Predefinição | Finalidade |
|---|---|---|
| `VELES_NO_WIZARD` | desligado | Ignora o assistente do primeiro arranque (também precisa de um TTY) |
| `VELES_MANAGER_MODE` | desligado | Força o gestor multi-agente para `veles run` (`1` ligado / `0` kill switch) |
| `VELES_VERIFY_MODE` | desligado | Força a passagem verificar→escalar para `veles run` (`1` ligado / `0` kill switch) |
| `VELES_FENCED_TOOLS` | desligado | Executa as ferramentas no caminho de execução fenced/em sandbox |
| `VELES_TRUST_AUTO_ALLOW` | desligado | Contorna a escada de confiança (CI / autopilot / subagentes pré-autorizados) |
| `VELES_SANDBOX_ROOTS` | projecto + `~/.veles` | Sobreposição separada por `:` das raízes de sandbox de leitura/escrita |
| `VELES_FETCH_ALLOW_PRIVATE` | desligado | Permite às ferramentas obter endereços RFC-1918 / privados |
| `VELES_MEMORY_RERANK` | ligado | Rerank vectorial da recuperação de memória (`0`/`false` desactiva) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend de pesquisa web para `research` e `web_search` |

## Registos

| Variável | Finalidade |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Fonte para `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Fonte para `veles browse modules` |

## Interno / testes

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — internas; não deve precisar de as
definir.
