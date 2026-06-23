# Fornecedores

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/providers.md)

O Veles é agnóstico quanto ao fornecedor. Passa `--provider <name>` a qualquer comando
de agente, ou define uma predefinição na configuração. Os IDs de modelo usam a
nomenclatura própria de cada fornecedor.

| Fornecedor | Tipo | Chave de API | Notas |
|---|---|---|---|
| `openrouter` | Gateway de nuvem | `OPENROUTER_API_KEY` | **Predefinição.** Encaminha centenas de modelos; IDs de modelo como `anthropic/claude-sonnet-4.6` |
| `anthropic` | Nuvem direta | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Nuvem direta | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Nuvem direta | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocesso | — (sessão de CLI) | Delega num CLI `claude` local em modo JSON-stream |
| `gemini-cli` | Subprocesso | — (sessão de CLI) | Delega num CLI `gemini` local |
| `ollama` | Local | nenhuma | `OLLAMA_BASE_URL` (predefinição `http://localhost:11434/v1`) |
| `llamacpp` | Local | nenhuma | `LLAMACPP_BASE_URL` (predefinição `http://localhost:8080/v1`) |
| `openai-compat` | Local/personalizado | nenhuma | `OPENAI_COMPAT_BASE_URL` (obrigatório, sem predefinição) |

Predefinições: fornecedor `openrouter`, modelo `anthropic/claude-sonnet-4.6`, compressor
`anthropic/claude-haiku-4.5`.

## Fornecedores locais

`ollama`, `llamacpp` e `openai-compat` não precisam de chave de API. Lista os modelos
instalados com `veles models <provider>` (sempre ao vivo para fornecedores locais).

**A invocação de ferramentas está desativada por omissão** nos fornecedores locais —
muitos modelos locais emitem chamadas de ferramentas malformadas. Ativa-a assim que
tiveres escolhido um modelo capaz de usar ferramentas:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Substitui os endpoints com as variáveis de ambiente `*_BASE_URL` (consulta
[variáveis de ambiente](environment-variables.md)).

## Delegação de CLI (`claude-cli`, `gemini-cli`)

Se tiveres uma subscrição do CLI Claude ou Gemini, o Veles pode correr o binário em
modo JSON-streaming e atuar como coordenador — mantendo o ciclo local-first sem
uma chave de API separada. As ferramentas do Veles chegam ao subprocesso apenas quando
está configurada uma ponte MCP.

## Estado multimodal (visão / fala-para-texto)

O Veles define um `VisionAdapter` e um protocolo de adaptador STT (`modules/vision.py`,
`modules/stt.py`), além de um registo global ao processo, **mas nenhum adaptador concreto
é distribuído e nada regista um no arranque do daemon**. Por isso, uma fotografia ou
mensagem de voz enviada para um canal devolve atualmente um aviso de "não configurado"
em vez de ser analisada. A tarefa de routing `vision` existe para quando um adaptador
estiver ligado. Consulta
[ligar o Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Escolher um modelo

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Para usar modelos diferentes para tarefas diferentes (barato para compressão, forte para
planeamento), consulta [routing por tarefa](../how-to/per-task-routing.md).
