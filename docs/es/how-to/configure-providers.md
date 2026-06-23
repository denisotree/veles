# Cómo configurar proveedores

> 🌐 **Idiomas:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · **Español** · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Cambia Veles entre OpenRouter, Anthropic, OpenAI, Gemini, modelos locales o una
suscripción de CLI. Lista completa de proveedores: [referencia de proveedores](../reference/providers.md).

## Elegir un proveedor por comando

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Establecer un valor por defecto para el proyecto

Pon una base en `<project>/.veles/config.toml`:

```toml
[provider]
default = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

O un valor por defecto global de usuario en `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Proporcionar la clave de API

Los proveedores en la nube necesitan una clave. Guárdala una vez en el llavero del SO:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…o exporta la [variable de entorno](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Orden de búsqueda: llavero (ámbito de proyecto) → llavero (por defecto) → variable de entorno.
Las claves **nunca** se escriben en archivos de configuración.

## Usar un modelo totalmente local (sin clave)

Instala [Ollama](https://ollama.com), descarga un modelo y apunta Veles a él:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

La llamada a herramientas está **desactivada por defecto** en los proveedores locales.
Actívala una vez que hayas elegido un modelo capaz de usar herramientas:

```bash
export VELES_LOCAL_TOOLS=1
```

Anula los endpoints si tu servidor no está en el puerto por defecto:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Delegar a una suscripción de CLI de Claude / Gemini

Si tienes la CLI de `claude` o `gemini` autenticada, Veles puede manejarla:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

No hace falta clave de API — la CLI gestiona la autenticación.

## Listar los modelos disponibles

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## Siguiente

- [Enrutar tareas distintas a modelos distintos](per-task-routing.md) — modelo barato
  para la compresión, modelo fuerte para la planificación.
