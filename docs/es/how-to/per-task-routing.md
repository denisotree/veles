# Cómo enrutar tareas a diferentes modelos

> 🌐 **Idiomas:** [English](../../en/how-to/per-task-routing.md) · [简体中文](../../zh-CN/how-to/per-task-routing.md) · [繁體中文](../../zh-TW/how-to/per-task-routing.md) · [日本語](../../ja/how-to/per-task-routing.md) · [한국어](../../ko/how-to/per-task-routing.md) · **Español** · [Français](../../fr/how-to/per-task-routing.md) · [Italiano](../../it/how-to/per-task-routing.md) · [Português (BR)](../../pt-BR/how-to/per-task-routing.md) · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · [العربية](../../ar/how-to/per-task-routing.md) · [हिन्दी](../../hi/how-to/per-task-routing.md) · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

Veles no está atado a un único modelo. Cada **tarea** interna puede usar un
`provider:model` distinto — un modelo barato para la compresión de contexto, uno fuerte
para el agente principal, un modelo de visión para imágenes. Este es el sistema de
*enrutamiento de ensamble*.

## Tipos de tarea

| Tarea | Se usa para |
|---|---|
| `default` | El bucle principal del agente |
| `curator` | Consolidación sesión → wiki |
| `compressor` | Compresión de contexto por ventana deslizante |
| `insights` | Extracción de insights posterior a la ejecución |
| `skills` | Ejecución de skills |
| `advisor` | La autocomprobación `advisor_review` |
| `vision` | `image_describe` (cuando hay un adaptador de visión conectado) |
| `embedding` | Similitud de `veles skill dedup` |

## Ver el enrutamiento actual

```bash
veles route show
```

Esto imprime el `provider:model` resuelto para cada tarea y una etiqueta `source` que
indica qué capa lo decidió.

## Fijar una tarea a un modelo

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Estos escriben `[routing.tasks]` en `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Restablecer

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Pistas en lenguaje natural en AGENTS.md

Puedes expresar el enrutamiento en prosa en `AGENTS.md` (p. ej. "usa un modelo barato para
la compresión"). Veles analiza estas pistas en un `routing.nl.toml` autogenerado:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Las entradas explícitas de `[routing.tasks]` siempre prevalecen sobre las pistas NL.

## Orden de resolución

Para cada tarea, gana la primera capa que produzca una especificación:

1. proyecto `[routing.tasks][task]`
2. proyecto `[routing.tasks].default`
3. pista NL del proyecto (`routing.nl.toml`)
4. base `[provider]` del proyecto
5. usuario `[routing.tasks][task]` / `.default`
6. usuario `[user] default_provider` + `default_model`

Si ninguna de estas resuelve, **no hay respaldo codificado** — la tarea queda sin
asignar y quien la invoca degrada (omite la funcionalidad) o falla con claridad, en lugar
de recurrir silenciosamente a un modelo en la nube.

(`embedding` omite los comodines — un modelo de chat no es un modelo de embeddings — de modo
que solo un `[routing.tasks].embedding` explícito lo responde.)
