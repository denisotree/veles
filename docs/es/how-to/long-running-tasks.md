# Cómo ejecutar tareas de larga duración: objetivos, jobs, dreaming, investigación

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/long-running-tasks.md)

Más allá de los prompts individuales, Veles puede perseguir **objetivos** de varios
pasos con presupuestos, ejecutar **jobs programados**, **soñar** para consolidar la
memoria, **investigar** la web en paralelo y descomponer el trabajo entre un
**manager** y subagentes.

## Objetivos — metas con presupuestos y checkpoints

Un objetivo es una meta de horizonte largo con límites explícitos y un registro de
progreso:

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

En la TUI, el modo de ejecución **goal** (cíclalo con `Shift+Tab`) maneja la misma
FSM de forma interactiva: te entrevista, confirma un plan, ejecuta y verifica.

## Jobs — ejecuciones programadas del agente

Programa un prompt para que se ejecute según una expresión cron, un intervalo o una
sola vez a una hora concreta:

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

`--schedule` acepta una expresión cron, `<N><s|m|h|d>` (p. ej. `30m`) o una marca de
tiempo ISO. Los jobs se ejecutan cuando el daemon está activo, o ejecútalos todos de
una vez de forma síncrona:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

Entrega la salida de un job a un canal con `--deliver-to telegram:<chat_id>`.

## Dreaming — consolidación de memoria en segundo plano

`dream` extrae insights, deduplica skills, sugiere promociones y revisa la wiki —
manteniendo la memoria fresca sin que tengas que esperar:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

Un daemon en ejecución sueña automáticamente cuando está inactivo.

## Investigación — indagación web en paralelo

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles descompone la pregunta, explora distintos ángulos en paralelo y sintetiza un
informe con citas.

## Modo manager — descomponer cualquier prompt

Activa la descomposición multiagente para una sola ejecución (un manager genera
subagentes explorer / writer / advisor y nunca escribe él mismo la respuesta final):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

Ver [orquestación multiagente](../explanation/multi-agent-orchestration.md).
