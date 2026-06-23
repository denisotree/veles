# Variáveis de ambiente

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/environment-variables.md)

O Veles lê estas variáveis em tempo de execução. As chaves de API e os tokens são
mais bem guardados no porta-chaves (keychain) do sistema operativo
(`veles secret set …`); as variáveis de ambiente são o recurso alternativo e a
substituição.

## Chaves de API dos fornecedores

Cascata de pesquisa da chave de API: porta-chaves do SO (âmbito de projeto) →
porta-chaves do SO (âmbito predefinido) → variável de ambiente.

| Variável | Fornecedor | Notas |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Fornecedor predefinido |
| `ANTHROPIC_API_KEY` | anthropic | API Anthropic direta |
| `OPENAI_API_KEY` | openai | API OpenAI direta |
| `GEMINI_API_KEY` | gemini | Chave principal para o Google Gemini |
| `GOOGLE_API_KEY` | gemini | Recurso alternativo para o Google Gemini |

O `claude-cli` e o `gemini-cli` autenticam-se através dos seus próprios binários —
sem variável de ambiente.

## Fornecedores locais

| Variável | Predefinição | Finalidade |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint do Ollama |
| `OLLAMA_HOST` | segue `OLLAMA_BASE_URL` | Host do Ollama para embeddings |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint do servidor llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (obrigatório) | Endpoint para o fornecedor `openai-compat` |
| `VELES_LOCAL_TOOLS` | desligado | Ativa a chamada de ferramentas em fornecedores locais (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | predefinição do fornecedor | Substitui o modelo de embedding do Ollama |

## Canais e daemon

| Variável | Predefinição | Finalidade |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token do bot de Telegram para `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL base do daemon usado pelos gateways de canais |
| `VELES_DAEMON_TOKEN` | — | Token de portador para a autenticação no daemon |

## Caminhos e locale

| Variável | Predefinição | Finalidade |
|---|---|---|
| `VELES_USER_HOME` | `~` | Substitui a home que contém `~/.veles/` (estado, cache, índice do porta-chaves) |
| `VELES_HOME` | — | Alias legado para `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Substitui o caminho do registo multiprojeto |
| `VELES_LOCALE` | `[user] language` ou `en` | Substitui o locale ativo da UI para uma execução |
| `VELES_LOG_LEVEL` | `INFO` | Verbosidade do daemon/registo (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Substitui o nome do ficheiro de configuração (testes) |

## Comportamento e flags de funcionalidades

| Variável | Predefinição | Finalidade |
|---|---|---|
| `VELES_NO_WIZARD` | desligado | Ignora o assistente da primeira execução (também precisa de um TTY) |
| `VELES_MANAGER_MODE` | desligado | Força o gestor multi-agente para `veles run` (`1` ligado / `0` interruptor de emergência) |
| `VELES_FENCED_TOOLS` | desligado | Executa as ferramentas no caminho de execução isolado/em sandbox |
| `VELES_TRUST_AUTO_ALLOW` | desligado | Ignora a escada de confiança (CI / autopilot / subagentes pré-autorizados) |
| `VELES_SANDBOX_ROOTS` | projeto + `~/.veles` | Substituição (separada por `:`) das raízes da sandbox de leitura/escrita |
| `VELES_FETCH_ALLOW_PRIVATE` | desligado | Permite que as ferramentas obtenham endereços RFC-1918 / privados |
| `VELES_MEMORY_RERANK` | ligado | Reordenação vetorial da recolha de memória (`0`/`false` desativa) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend de pesquisa web para `research` e `web_search` |

## Registos

| Variável | Finalidade |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Fonte para `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Fonte para `veles browse modules` |

## Internas / testes

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — internas; não deve precisar de
as definir.
