# Memoria del proyecto y el bucle de aprendizaje

> 🌐 **Languages:** **English** · [Русский](../../ru/explanation/project-memory-and-learning-loop.md)

La característica que define a Veles es que **recuerda** y **aprende** por proyecto.
Esta página explica qué es esa memoria y cómo el bucle de aprendizaje la mantiene
útil.

## La memoria es un artefacto estructurado

La memoria del proyecto vive en `<project>/.veles/` — `memory.db` (SQLite, la
fuente de verdad) más un árbol `.veles/memory/` legible por humanos (vistas de
insights renderizadas, resúmenes de sesión, propuestas, un diario de operaciones
del sistema). Está **separada de tu contenido** y funciona de forma idéntica bajo
cualquier layout (wiki, notes o bare). No es un volcado de la transcripción del
chat: es un conjunto de capas estructuradas:

- **Registro de sesiones** — cada conversación, una fila por turno, indexada a
  texto completo.
- **Reglas** — imperativos breves que el agente debe seguir (`format`, `do`,
  `don't`, `preference`), inyectados en el prompt de sistema estable.
- **Insights** — lecciones destiladas a partir de las sesiones. La fila SQL es la
  canónica (el recall, el envejecimiento y la deduplicación operan sobre ella); se
  renderiza una vista en markdown a `.veles/memory/insights/` para humanos y
  exportaciones.
- **Mapa del árbol del proyecto** — un mapa de archivos cacheado y etiquetado
  semánticamente para que el agente lea los 3–5 archivos relevantes, no todo el
  árbol.
- **Registros de skills y herramientas** — con telemetría (recuentos de
  uso/éxito/error) que usan el ranking y la deduplicación.

Consulta la lista de tablas en [estructura del proyecto](../reference/project-layout.md#project-memory-velesmemorydb).

## Recall: contexto pequeño, incorporado bajo demanda

`AGENTS.md` es deliberadamente pequeño. Cuando preguntas algo, Veles incorpora solo
lo relevante: turnos pasados coincidentes (texto completo + reordenamiento vectorial
opcional), reglas e insights aplicables, y los archivos que el mapa del árbol del
proyecto puntúa más alto. Esto mantiene cada llamada al modelo enfocada y económica
en lugar de volcarlo todo.

## El bucle de aprendizaje

La experiencia se convierte en conocimiento duradero a través de tres mecanismos:

### Insights — capturar lecciones
Tras una ejecución, un extractor busca cosas que merezca la pena recordar:
retroalimentación explícita de "recuerda X" / "nunca Y" y patrones de
error-de-herramienta→recuperación (un fallo seguido de una corrección). Los destila
en insights y reglas para que el mismo error no se repita.

### Curator — consolidar sesiones
El curator destila las sesiones más antiguas en memoria duradera: siempre insights
y reglas en SQL; y además una página en `wiki/sessions/` cuando el layout del
proyecto activa el engine de wiki. Se ejecuta con temporizadores de
inactividad/post-turno, o bajo demanda con `veles curate`.

### Dreaming — mantenimiento en segundo plano
`veles dream` (y el daemon cuando está inactivo) extrae insights, deduplica skills e
insights, sugiere promociones y (bajo un layout de wiki) hace lint de la wiki,
manteniendo la memoria fresca sin bloquearte. Añade `--include-consolidation` para
una pasada más profunda con LLM.

## Compresión de contexto

Las conversaciones largas se mantienen por debajo del límite de contexto del modelo
mediante un compresor de ventana deslizante: cuando el historial en memoria supera
un umbral de tokens, la parte central se resume (con un modelo económico enrutado)
y se reemplaza por un puntero al resumen guardado en `.veles/memory/sessions/`. El
historial completo siempre permanece en `memory.db`: solo se comprime la ventana en
memoria, por lo que en disco no hay pérdida.

## Por qué importa

Como la memoria está estructurada y el bucle se ejecuta de forma continua, un
proyecto de Veles se vuelve **más útil cuanto más lo usas**: aprende tus
convenciones, evita errores repetidos y fundamenta las respuestas en lo que
realmente ha visto.
