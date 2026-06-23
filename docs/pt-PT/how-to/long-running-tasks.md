# Como executar tarefas de longa duração: objetivos, jobs, sonho, investigação

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/long-running-tasks.md)

Para além de prompts isolados, o Veles pode perseguir **objetivos** de vários
passos com orçamentos, executar **jobs agendados**, **sonhar** para consolidar a
memória, **investigar** a web em paralelo, e decompor o trabalho entre um **gestor**
(manager) e subagentes.

## Objetivos — metas com orçamentos e checkpoints

Um objetivo é uma meta de longo horizonte com limites explícitos e um registo de
progresso:

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

Na TUI, o modo de execução **goal** (alterne com `Shift+Tab`) conduz a mesma FSM
de forma interativa: entrevista-o, confirma um plano, executa, e verifica.

## Jobs — execuções de agente agendadas

Agende um prompt para correr segundo uma expressão cron, um intervalo, ou uma única
vez a uma dada hora:

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

`--schedule` aceita uma expressão cron, `<N><s|m|h|d>` (por exemplo `30m`), ou um
carimbo temporal ISO. Os jobs correm quando o daemon está ativo, ou execute-os
todos de uma vez de forma síncrona:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

Entregue o resultado de um job a um canal com `--deliver-to telegram:<chat_id>`.

## Sonho — consolidação de memória em segundo plano

O `dream` extrai insights, elimina skills duplicadas, sugere promoções, e faz a
verificação (lint) da wiki — mantendo a memória atualizada sem que tenha de esperar:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

Um daemon em execução sonha automaticamente quando está inativo.

## Investigação — pesquisa paralela na web

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

O Veles decompõe a pergunta, explora ângulos em paralelo, e sintetiza um relatório
com citações.

## Modo gestor — decompor qualquer prompt

Ative a decomposição multiagente para uma única execução (um gestor gera
subagentes explorer / writer / advisor e nunca escreve ele próprio a resposta
final):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

Ver [orquestração multiagente](../explanation/multi-agent-orchestration.md).
