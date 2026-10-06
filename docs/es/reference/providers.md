# Proveedores

> 🌐 **Idiomas:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · **Español** · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles es agnóstico respecto al proveedor. Pasa `--provider <id>` a cualquier comando
del agente, o establece un valor por defecto en la configuración. Los IDs de modelo usan
la propia nomenclatura del proveedor.

## El catálogo de proveedores

Todos los proveedores que Veles conoce son entradas de un único catálogo, construido a
partir de tres fuentes:

1. **Integrados** — la tabla de abajo, incluida con Veles.
2. **Los tuyos** — `~/.veles/providers.toml`: una API alojada compatible con OpenAI o un
   servidor que ejecutas tú, añadiendo una entrada (consulta
   [añadir tu propio proveedor](../how-to/configure-providers.md#añadir-tu-propio-proveedor)).
   Una entrada con un id integrado anula los ajustes de ese proveedor (su `base_url`, por ejemplo).
3. **Módulos** — un módulo del registro aporta un proveedor (`antigravity-cli`). Nombrarlo
   en `[engine] provider`, en una ruta o en `--provider` lo instala desde tus registros
   conectados en la siguiente ejecución, igual que un canal declarado.

`--provider`, `veles models`, los asistentes de configuración, el enrutamiento y
`veles doctor` leen el catálogo, así que un proveedor de cualquier fuente funciona en todos
los sitios donde funciona uno integrado. Un id desconocido es un error de una línea que
lista lo que existe; `veles doctor` también revisa `~/.veles/providers.toml` y todos los
proveedores que nombran tus rutas.

| Proveedor | Tipo | Clave de API | Notas |
|---|---|---|---|
| `openrouter` | Pasarela en la nube | `OPENROUTER_API_KEY` | **Por defecto.** Reenvía cientos de modelos; IDs de modelo como `anthropic/claude-sonnet-4.6` |
| `anthropic` | Nube directa | `ANTHROPIC_API_KEY` | API Messages de Claude, prompt caching |
| `openai` | Nube directa | `OPENAI_API_KEY` | Chat completions de GPT |
| `gemini` | Nube directa | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Delegado de CLI | — (sesión de CLI) | Delega en una CLI local de `claude` en modo JSON-stream |
| `codex` | Delegado de CLI | — (sesión de CLI) | Delega en una CLI local de `codex` (suscripción de ChatGPT) |
| `ollama` | Local | ninguna | `OLLAMA_BASE_URL` (por defecto `http://localhost:11434/v1`) |
| `llamacpp` | Local | ninguna | `LLAMACPP_BASE_URL` (por defecto `http://localhost:8080/v1`) |
| `openai-compat` | Local/personalizado | `OPENAI_COMPAT_API_KEY` opcional | `OPENAI_COMPAT_BASE_URL` (requerido, sin valor por defecto) |

`gemini-cli` se eliminó en la 1.2.6 — Google ya no ofrece la CLI de Gemini a cuentas
personales. Usa `gemini` con una clave de API, o el módulo `antigravity-cli`.

Proveedor por defecto: `openrouter`. **No hay un modelo por defecto codificado** —
establece uno mediante el asistente de configuración, `[engine] model` o `--model`
(de lo contrario el agente informa "no model configured"). Las rutas por tarea heredan
`[engine]` como base salvo que se anulen en `[routing.tasks]` — consulta
[enrutamiento por tarea](../how-to/per-task-routing.md).

## Proveedores locales

`ollama`, `llamacpp` y `openai-compat` no necesitan clave de API. Lista los modelos
instalados con `veles models <provider>` (siempre en vivo para los proveedores locales).

**La llamada a herramientas se detecta** a partir de lo que anuncia el backend: ollama
informa de las capacidades de cada modelo, un servidor llama.cpp las de su plantilla de
chat. `VELES_LOCAL_TOOLS=1` fuerza la llamada a herramientas, `=0` la desactiva; sin
definir, se detecta.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Anula los endpoints con las variables de entorno `*_BASE_URL` (consulta
[variables de entorno](environment-variables.md)).

## Delegación a CLI (`claude-cli`, `codex`, `antigravity-cli`)

Si tienes una suscripción a Claude, ChatGPT o Google, Veles puede ejecutar su CLI sin interfaz y
actuar como coordinador — sin una clave de API aparte. `claude-cli` y `codex` están integrados;
`antigravity-cli` (la CLI `agy`) es un módulo del registro que se instala solo cuando lo
nombras.

El delegado es solo el modelo: las herramientas de Veles le llegan por un puente MCP, y
cada llamada pasa por la escalera de confianza de Veles. La configuración del puente vive
en un directorio del proceso en ejecución, `.veles/tmp/delegate-<pid>/`, que se elimina
cuando termina. `agy` se ejecuta en un espacio de trabajo temporal fuera de tu proyecto
(bajo `~/.veles/tmp/`), así que la configuración `.agents/` del propio proyecto nunca le
llega, tras una barrera que deniega sus propias herramientas de shell y de archivos.

`codex` también se ejecuta fuera de tu proyecto (bajo `~/.veles/tmp/`), con tu configuración de codex ignorada y sus propias herramientas — shell, edición de archivos, imágenes, subagentes, navegador, búsqueda web — desactivadas; Veles comprueba esos nombres de flags una vez por proceso y se niega a ejecutar un codex que haya renombrado alguno de los que necesita. Su servidor MCP se pasa en los argumentos, no en un archivo. En `veles run`, codex sigue el protocolo de herramientas de Veles con menos fiabilidad que claude: puede responder que no puede leer un archivo sin llamar a la herramienta — vuelve a preguntar, o nombra la herramienta ("use read_file on …").

## Estado multimodal (visión / voz a texto)

Veles define un `VisionAdapter` y un protocolo de adaptador STT (`modules/vision.py`,
`modules/stt.py`) más un registro global de proceso, **pero no se incluye ningún adaptador
concreto y nada registra uno al arrancar el daemon**. Así que una foto o un mensaje de voz
enviado a un canal devuelve actualmente un aviso de "not configured" en lugar de ser
analizado. La tarea de enrutamiento `vision` existe para cuando se conecte un adaptador.
Consulta [conectar Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Elegir un modelo

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Para usar modelos diferentes en trabajos diferentes (uno barato para la compresión, uno
fuerte para la planificación), consulta [enrutamiento por tarea](../how-to/per-task-routing.md).
