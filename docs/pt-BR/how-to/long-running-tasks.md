# Como executar tarefas de longa duração: goals, jobs, dreaming, research

> 🌐 **Idiomas:** [English](../../en/how-to/long-running-tasks.md) · [简体中文](../../zh-CN/how-to/long-running-tasks.md) · [繁體中文](../../zh-TW/how-to/long-running-tasks.md) · [日本語](../../ja/how-to/long-running-tasks.md) · [한국어](../../ko/how-to/long-running-tasks.md) · [Español](../../es/how-to/long-running-tasks.md) · [Français](../../fr/how-to/long-running-tasks.md) · [Italiano](../../it/how-to/long-running-tasks.md) · **Português (BR)** · [Português (PT)](../../pt-PT/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · [العربية](../../ar/how-to/long-running-tasks.md) · [हिन्दी](../../hi/how-to/long-running-tasks.md) · [বাংলা](../../bn/how-to/long-running-tasks.md) · [Tiếng Việt](../../vi/how-to/long-running-tasks.md)

Além de prompts isolados, o Veles pode perseguir **goals** (metas) de múltiplas etapas com orçamentos, executar
**jobs agendados**, fazer **dream** (sonhar) para consolidar a memória, **pesquisar** a web em
paralelo e decompor o trabalho entre um **manager** e sub-agentes.

## Goals — objetivos com orçamentos e checkpoints

Uma goal é um objetivo de longo horizonte com limites explícitos e um log de progresso:

```bash
veles goal start "Draft a competitor analysis report" \
  --done-when "report.md exists and cites >=3 sources" \
  --max-steps 30 --max-cost-usd 5 --max-wall-time-s 3600

veles goal list
veles goal show <id>
veles goal checkpoint <id> "Outlined sections; cited 2 sources" --cost-usd 0.40
veles goal pause <id> ; veles goal resume <id>
veles goal done <id> --evidence report.md
veles goal cancel <id> --reason "scope changed"
```

No TUI, o modo de execução **goal** (alterne com `Shift+Tab`) controla a mesma FSM
de forma interativa: ele entrevista você, confirma um plano, executa e verifica.

## Jobs — execuções agendadas do agente

Agende um prompt para rodar com uma expressão cron, um intervalo ou uma única vez em um horário:

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # run on the next tick
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

`--schedule` aceita uma expressão cron, `<N><s|m|h|d>` (ex.: `30m`), ou um timestamp
ISO. Os jobs rodam quando o daemon está no ar, ou execute todos eles uma vez de forma síncrona:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

Entregue a saída de um job a um canal com `--deliver-to telegram:<chat_id>`.

## Dreaming — consolidação de memória em segundo plano

O `dream` extrai insights, deduplica skills, sugere promoções e faz lint da
wiki — mantendo a memória atualizada sem que você precise esperar:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

Um daemon em execução sonha automaticamente quando está ocioso.

## Research — investigação paralela na web

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

O Veles decompõe a pergunta, explora os ângulos em paralelo e sintetiza um
relatório com citações.

## Modo manager — decompor qualquer prompt

Ative a decomposição multi-agente para uma única execução (um manager cria sub-agentes
explorer / writer / advisor e nunca escreve a resposta final ele mesmo):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

Veja [orquestração multi-agente](../explanation/multi-agent-orchestration.md).
