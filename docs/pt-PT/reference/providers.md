# Fornecedores

> 🌐 **Idiomas:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · **Português (PT)** · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

O Veles é agnóstico quanto ao fornecedor. Passe `--provider <name>` a qualquer comando do
agente, ou defina uma predefinição na configuração. Os IDs de modelo usam a própria
nomenclatura do fornecedor.

| Fornecedor | Tipo | Chave de API | Notas |
|---|---|---|---|
| `openrouter` | Gateway na nuvem | `OPENROUTER_API_KEY` | **Predefinição.** Retransmite centenas de modelos; IDs de modelo como `anthropic/claude-sonnet-4.6` |
| `anthropic` | Nuvem directa | `ANTHROPIC_API_KEY` | API Messages do Claude, prompt caching |
| `openai` | Nuvem directa | `OPENAI_API_KEY` | Chat completions do GPT |
| `gemini` | Nuvem directa | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocesso | — (sessão da CLI) | Delega numa CLI `claude` local em modo JSON-stream |
| `gemini-cli` | Subprocesso | — (sessão da CLI) | Delega numa CLI `gemini` local |
| `ollama` | Local | nenhuma | `OLLAMA_BASE_URL` (predefinição `http://localhost:11434/v1`) |
| `llamacpp` | Local | nenhuma | `LLAMACPP_BASE_URL` (predefinição `http://localhost:8080/v1`) |
| `openai-compat` | Local/personalizado | nenhuma | `OPENAI_COMPAT_BASE_URL` (obrigatória, sem predefinição) |

Fornecedor predefinido: `openrouter`. **Não existe um modelo predefinido rígido** — defina
um através do assistente de configuração, de `[engine] model`, ou de `--model` (caso
contrário o agente reporta "no model configured"). As rotas por tarefa herdam `[engine]`
como base, a menos que sejam sobrepostas em `[routing.tasks]` — ver
[encaminhamento por tarefa](../how-to/per-task-routing.md).

## Fornecedores locais

`ollama`, `llamacpp` e `openai-compat` não precisam de chave de API. Liste os modelos
instalados com `veles models <provider>` (sempre ao vivo para os fornecedores locais).

**A chamada a ferramentas está desligada por predefinição** nos fornecedores locais —
muitos modelos locais emitem chamadas a ferramentas malformadas. Active-a assim que tiver
escolhido um modelo com capacidade para ferramentas:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Sobreponha os endpoints com as variáveis de ambiente `*_BASE_URL` (ver
[variáveis de ambiente](environment-variables.md)).

## Delegação por CLI (`claude-cli`, `gemini-cli`)

Se tiver uma subscrição da CLI do Claude ou do Gemini, o Veles pode executar o binário em
modo JSON-streaming e actuar como coordenador — mantendo o ciclo local-first sem uma chave
de API separada. As ferramentas do Veles chegam ao subprocesso apenas quando está
configurada uma ponte MCP.

## Estado multimodal (visão / fala-para-texto)

O Veles define um `VisionAdapter` e um protocolo de adaptador STT (`modules/vision.py`,
`modules/stt.py`) mais um registo global ao processo, **mas não vem incluído nenhum
adaptador concreto e nada regista um no arranque do daemon**. Por isso, uma foto ou
mensagem de voz enviada a um canal devolve actualmente um aviso de "não configurado" em vez
de ser analisada. A tarefa de encaminhamento `vision` existe para quando um adaptador for
ligado. Ver [ligar o Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Escolher um modelo

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Para usar modelos diferentes para tarefas diferentes (barato para compressão, forte para
planeamento), ver [encaminhamento por tarefa](../how-to/per-task-routing.md).
