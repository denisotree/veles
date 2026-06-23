# Cómo configurar proveedores

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/configure-providers.md)

Cambia Veles entre OpenRouter, Anthropic, OpenAI, Gemini, modelos locales o una
suscripción a una CLI. Lista completa de proveedores: [referencia de proveedores](../reference/providers.md).

## Elegir un proveedor por comando

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Definir un valor por defecto para el proyecto

Pon una base en `<project>/.veles/config.toml`:

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
```

O un valor por defecto global del usuario en `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Proporcionar la clave de API

Los proveedores en la nube necesitan una clave. Guárdala una vez en el llavero del
sistema operativo:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…o exporta la [variable de entorno](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Orden de búsqueda: llavero (ámbito del proyecto) → llavero (por defecto) → variable
de entorno. Las claves **nunca** se escriben en archivos de configuración.

## Usar un modelo totalmente local (sin clave)

Instala [Ollama](https://ollama.com), descarga un modelo y apunta Veles a él:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

La invocación de herramientas está **desactivada por defecto** en los proveedores
locales. Actívala una vez que hayas elegido un modelo capaz de usar herramientas:

```bash
export VELES_LOCAL_TOOLS=1
```

Sobrescribe los endpoints si tu servidor no está en el puerto por defecto:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Delegar en una suscripción a la CLI de Claude / Gemini

Si tienes la CLI de `claude` o `gemini` autenticada, Veles puede manejarla:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

No hace falta clave de API — la CLI se encarga de la autenticación.

## Listar los modelos disponibles

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## Siguiente

- [Enrutar distintas tareas a distintos modelos](per-task-routing.md) — un modelo
  barato para la compresión, uno potente para la planificación.
