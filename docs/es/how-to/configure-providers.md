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
[engine]
provider = "openrouter"                 # provider name
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

La llamada a herramientas se **detecta** a partir de lo que anuncia el servidor. Fuérzala
con `VELES_LOCAL_TOOLS=1` (o desactívala con `=0`).

Anula los endpoints si tu servidor no está en el puerto por defecto:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Añadir tu propio proveedor

Cualquier API alojada compatible con OpenAI, o un servidor que ejecutes tú, se convierte
en un proveedor con una entrada en `~/.veles/providers.toml` — sin código. El id es el
nombre de la tabla:

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

Luego úsalo como cualquier proveedor integrado:

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| Clave | Significado |
|---|---|
| `kind` | `openai-api` (una API alojada) o `local` (un servidor que ejecutas tú) |
| `base_url` | el endpoint compatible con OpenAI, terminado en `/v1` (o el equivalente del proveedor) |
| `base_url_env` | una variable de entorno que anula `base_url` cuando está definida |
| `key_env` | nombres de variables de entorno de las que se lee la clave; el llavero se prueba primero |
| `label`, `tagline` | cómo los asistentes lo muestran |
| `tools` | `auto` (por defecto), `on` u `off` — si el modelo recibe llamadas a herramientas |

Una entrada con un id integrado (`[providers.ollama]`) cambia los ajustes de ese
proveedor — su `base_url`, por ejemplo — pero no su tipo. Un archivo roto se informa una
sola vez y Veles sigue con los proveedores integrados; `veles doctor` lista lo que está
mal en él.

Puntos de partida para APIs habituales — **no verificados por el equipo de Veles**,
consulta la documentación del proveedor para ver el endpoint actual:

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## Delegar a una suscripción de Claude / ChatGPT / Google

Si tienes la CLI de `claude` autenticada, Veles puede manejarla:

```bash
veles run --provider claude-cli "..."
```

Para una suscripción de ChatGPT, instala la CLI de Codex e inicia sesión una vez (`codex login`):

```bash
veles run --provider codex --model gpt-6-luna "..."
veles models codex      # the models your account has
```

Para una suscripción de Google, instala la CLI de Antigravity (`agy`) e inicia sesión una
vez, luego nombra su proveedor — el módulo `antigravity-cli` se instala solo desde tus
registros conectados en esa ejecución:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
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
