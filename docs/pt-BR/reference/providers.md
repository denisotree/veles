# Provedores

> 🌐 **Idiomas:** **English** · [Русский](../../ru/reference/providers.md)

O Veles é agnóstico em relação a provedores. Passe `--provider <name>` para qualquer comando do agente ou defina
um padrão na configuração. Os IDs de modelo usam a nomenclatura do próprio provedor.

| Provedor | Tipo | Chave de API | Observações |
|---|---|---|---|
| `openrouter` | Gateway de nuvem | `OPENROUTER_API_KEY` | **Padrão.** Encaminha centenas de modelos; IDs de modelo como `anthropic/claude-sonnet-4.6` |
| `anthropic` | Nuvem direta | `ANTHROPIC_API_KEY` | API Claude Messages, prompt caching |
| `openai` | Nuvem direta | `OPENAI_API_KEY` | Chat completions da GPT |
| `gemini` | Nuvem direta | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocesso | — (sessão da CLI) | Delega a uma CLI `claude` local em modo JSON-stream |
| `gemini-cli` | Subprocesso | — (sessão da CLI) | Delega a uma CLI `gemini` local |
| `ollama` | Local | nenhuma | `OLLAMA_BASE_URL` (padrão `http://localhost:11434/v1`) |
| `llamacpp` | Local | nenhuma | `LLAMACPP_BASE_URL` (padrão `http://localhost:8080/v1`) |
| `openai-compat` | Local/personalizado | nenhuma | `OPENAI_COMPAT_BASE_URL` (obrigatório, sem padrão) |

Padrões: provedor `openrouter`, modelo `anthropic/claude-sonnet-4.6`, compressor
`anthropic/claude-haiku-4.5`.

## Provedores locais

`ollama`, `llamacpp` e `openai-compat` não precisam de chave de API. Liste os modelos instalados
com `veles models <provider>` (sempre ao vivo para provedores locais).

**As chamadas de ferramenta vêm desligadas por padrão** em provedores locais — muitos modelos locais emitem
chamadas de ferramenta malformadas. Habilite-as depois de escolher um modelo capaz de usar ferramentas:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Sobrescreva os endpoints com as variáveis de ambiente `*_BASE_URL` (veja
[variáveis de ambiente](environment-variables.md)).

## Delegação de CLI (`claude-cli`, `gemini-cli`)

Se você tem uma assinatura da CLI do Claude ou do Gemini, o Veles pode executar o binário em
modo JSON-streaming e atuar como coordenador — mantendo o loop local-first sem
uma chave de API separada. As ferramentas do Veles só alcançam o subprocesso quando uma ponte MCP está
configurada.

## Status multimodal (visão / fala-para-texto)

O Veles define um `VisionAdapter` e um protocolo de adaptador de STT (`modules/vision.py`,
`modules/stt.py`) mais um registry global ao processo, **mas nenhum adaptador concreto é distribuído
e nada registra um na inicialização do daemon**. Portanto, uma foto ou mensagem de voz enviada a
um canal atualmente retorna um aviso de "não configurado" em vez de ser analisada.
A tarefa de roteamento `vision` existe para quando um adaptador for conectado. Veja
[conectar o Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Escolhendo um modelo

```bash
veles models openrouter            # cache de 24h
veles models openrouter --refresh  # ignora o cache
veles models ollama                # sempre ao vivo
```

Para usar modelos diferentes para tarefas diferentes (barato para compressão, forte para
planejamento), veja [roteamento por tarefa](../how-to/per-task-routing.md).
