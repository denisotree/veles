# Proveedores

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/providers.md)

Veles es agnóstico del proveedor. Pasa `--provider <name>` a cualquier comando del
agente, o establece un valor por defecto en la configuración. Los IDs de modelo usan
la propia nomenclatura del proveedor.

| Proveedor | Tipo | Clave API | Notas |
|---|---|---|---|
| `openrouter` | Pasarela en la nube | `OPENROUTER_API_KEY` | **Por defecto.** Retransmite cientos de modelos; IDs de modelo como `anthropic/claude-sonnet-4.6` |
| `anthropic` | Nube directa | `ANTHROPIC_API_KEY` | Claude Messages API, caché de prompts |
| `openai` | Nube directa | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Nube directa | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subproceso | — (sesión de CLI) | Delega en una CLI `claude` local en modo JSON-stream |
| `gemini-cli` | Subproceso | — (sesión de CLI) | Delega en una CLI `gemini` local |
| `ollama` | Local | ninguna | `OLLAMA_BASE_URL` (por defecto `http://localhost:11434/v1`) |
| `llamacpp` | Local | ninguna | `LLAMACPP_BASE_URL` (por defecto `http://localhost:8080/v1`) |
| `openai-compat` | Local/personalizado | ninguna | `OPENAI_COMPAT_BASE_URL` (obligatoria, sin valor por defecto) |

Valores por defecto: proveedor `openrouter`, modelo `anthropic/claude-sonnet-4.6`,
compresor `anthropic/claude-haiku-4.5`.

## Proveedores locales

`ollama`, `llamacpp` y `openai-compat` no necesitan clave API. Lista los modelos
instalados con `veles models <provider>` (siempre en vivo para proveedores locales).

**Las llamadas a herramientas están desactivadas por defecto** en los proveedores
locales — muchos modelos locales emiten llamadas a herramientas malformadas.
Actívalas cuando hayas elegido un modelo capaz de usar herramientas:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Sobrescribe los endpoints con las variables de entorno `*_BASE_URL` (consulta
[environment variables](environment-variables.md)).

## Delegación en CLI (`claude-cli`, `gemini-cli`)

Si tienes una suscripción a la CLI de Claude o de Gemini, Veles puede ejecutar el
binario en modo JSON-streaming y actuar como coordinador — manteniendo el bucle
local-first sin una clave API aparte. Las herramientas de Veles llegan al
subproceso solo cuando hay un puente MCP configurado.

## Estado multimodal (visión / voz a texto)

Veles define un `VisionAdapter` y un protocolo de adaptador STT (`modules/vision.py`,
`modules/stt.py`) más un registro global de proceso, **pero no se incluye ningún
adaptador concreto y nada registra uno al arrancar el daemon**. Así que una foto o
un mensaje de voz enviado a un canal devuelve actualmente un aviso de "no
configurado" en lugar de ser analizado. La tarea de enrutamiento `vision` existe
para cuando se conecte un adaptador. Consulta
[connect Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Elegir un modelo

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Para usar modelos distintos en trabajos distintos (barato para la compresión,
potente para la planificación), consulta [per-task routing](../how-to/per-task-routing.md).
