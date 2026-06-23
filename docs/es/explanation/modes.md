# Modos de ejecución

> 🌐 **Languages:** **English** · [Русский](../../ru/explanation/modes.md)

En la TUI, cada prompt se gestiona mediante un **modo de ejecución**: una estrategia
que decide cuánta autonomía y qué herramientas recibe el turno. Cambia de modo con
`Shift+Tab`; el orden es `auto → planning → writing → goal`.

## Los cuatro modos

### `writing` — chat directo
El modo más sencillo: tu prompt llega al agente con el conjunto completo de
herramientas disponible y este responde. Úsalo para el trabajo habitual en el que
quieres que el agente actúe.

### `planning` — investigación de solo lectura + un plan
Las mutaciones están bloqueadas (sin `write_file`, sin `run_shell`). El agente usa
herramientas de lectura/búsqueda para reunir contexto y luego produce un artefacto
de plan estructurado. Úsalo para pensar antes de tocar nada — o pasa `--plan` a
`veles run` para obtener el mismo efecto en la CLI.

### `auto` — enrutamiento inteligente (predeterminado)
Una clasificación rápida decide si tu prompt es una petición directa o requiere
planificación, y luego lo despacha a `writing` o `planning` según corresponda. Es
el respaldo más inteligente cuando no has expresado tu intención, razón por la cual
es la primera parada predeterminada del ciclo.

### `goal` — objetivo de largo horizonte
Conduce una máquina de estados finitos para un objetivo de varios pasos: te
entrevista para aclarar, confirma un plan, ejecuta pasos (con comprobaciones del
advisor) y verifica la condición de finalización, todo bajo presupuestos
explícitos. El equivalente en la CLI es la familia de comandos
[`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints).

## Por qué existen los modos

Distintas peticiones requieren distintas dosis de cautela. Una pregunta rápida no
debería exigir ceremonia; un cambio arriesgado se beneficia de una pasada previa de
planificación en solo lectura; un objetivo grande necesita presupuestos y puntos de
control. Los modos hacen esa elección explícita y conmutable por turno, en lugar de
imponer un único comportamiento a toda la sesión.

Cuando cambias a mitad de sesión, se le comunican al agente las nuevas reglas para
que su comportamiento cambie de inmediato.
