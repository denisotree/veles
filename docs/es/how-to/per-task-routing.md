# Cómo enrutar tareas a diferentes modelos

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

Veles no está atado a un único modelo. Cada **tarea** interna puede usar un
`provider:model` distinto: un modelo económico para la compresión de contexto, uno
potente para el agente principal, un modelo de visión para imágenes. Este es el
sistema de *enrutamiento de ensamble*.

## Tipos de tarea

| Tarea | Usada para |
|---|---|
| `default` | El bucle del agente principal |
| `curator` | Consolidación de sesión → wiki |
| `compressor` | Compresión de contexto por ventana deslizante |
| `insights` | Extracción de insights tras la ejecución |
| `skills` | Ejecución de skills |
| `advisor` | La autoverificación `advisor_review` |
| `vision` | `image_describe` (cuando hay un adaptador de visión conectado) |
| `embedding` | Similitud de `veles skill dedup` |

## Ver el enrutamiento actual

```bash
veles route show
```

Esto imprime el `provider:model` resuelto para cada tarea y una etiqueta `source`
que indica qué capa lo decidió.

## Fijar una tarea a un modelo

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Esto escribe `[routing.tasks]` en `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Restablecer

```bash
veles route reset compressor   # una tarea vuelve al valor por defecto
veles route reset              # todas las tareas vuelven al valor por defecto
```

## Pistas en lenguaje natural en AGENTS.md

Puedes expresar el enrutamiento en prosa dentro de `AGENTS.md` (p. ej. "usa un
modelo económico para la compresión"). Veles las interpreta y genera
automáticamente un `routing.nl.toml`:

```bash
veles route refresh            # vuelve a interpretar las pistas de AGENTS.md
veles route refresh --force    # incluso si AGENTS.md no ha cambiado
```

Las entradas explícitas de `[routing.tasks]` siempre prevalecen sobre las pistas
en lenguaje natural.

## Orden de resolución

Para cada tarea gana la primera capa que produzca una especificación:

1. `[routing.tasks][task]` del proyecto
2. `[routing.tasks].default` del proyecto
3. pista en lenguaje natural del proyecto (`routing.nl.toml`)
4. base `[provider]` del proyecto
5. `[routing.tasks][task]` / `.default` del usuario
6. `[user] default_provider` + `default_model` del usuario
7. valor por defecto incorporado para esa tarea

(`embedding` omite los comodines genéricos: un modelo de chat no es un modelo de
embeddings.)
