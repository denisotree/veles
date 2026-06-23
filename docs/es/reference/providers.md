# Proveedores

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/providers.md)

Veles es agnóstico respecto al proveedor. Pasa `--provider <name>` a cualquier comando
del agente, o establece un valor por defecto en la configuración. Los IDs de modelo usan
la propia nomenclatura del proveedor.

| Proveedor | Tipo | Clave de API | Notas |
|---|---|---|---|
| `openrouter` | Pasarela en la nube | `OPENROUTER_API_KEY` | **Por defecto.** Reenvía cientos de modelos; IDs de modelo como `anthropic/claude-sonnet-4.6` |
| `anthropic` | Nube directa | `ANTHROPIC_API_KEY` | API Messages de Claude, prompt caching |
| `openai` | Nube directa | `OPENAI_API_KEY` | Chat completions de GPT |
| `gemini` | Nube directa | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subproceso | — (sesión de CLI) | Delega en una CLI local de `claude` en modo JSON-stream |
| `gemini-cli` | Subproceso | — (sesión de CLI) | Delega en una CLI local de `gemini` |
| `ollama` | Local | ninguna | `OLLAMA_BASE_URL` (por defecto `http://localhost:11434/v1`) |
| `llamacpp` | Local | ninguna | `LLAMACPP_BASE_URL` (por defecto `http://localhost:8080/v1`) |
| `openai-compat` | Local/personalizado | ninguna | `OPENAI_COMPAT_BASE_URL` (requerido, sin valor por defecto) |

Proveedor por defecto: `openrouter`. **No hay un modelo por defecto codificado** —
establece uno mediante el asistente de configuración, `[provider] model` o `--model`
(de lo contrario el agente informa "no model configured"). Las rutas por tarea heredan
`[provider]` como base salvo que se anulen en `[routing.tasks]` — consulta
[enrutamiento por tarea](../how-to/per-task-routing.md).

## Proveedores locales

`ollama`, `llamacpp` y `openai-compat` no necesitan clave de API. Lista los modelos
instalados con `veles models <provider>` (siempre en vivo para los proveedores locales).

**La llamada a herramientas está desactivada por defecto** en los proveedores locales —
muchos modelos locales emiten llamadas a herramientas malformadas. Actívala una vez que
hayas elegido un modelo capaz de usar herramientas:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Anula los endpoints con las variables de entorno `*_BASE_URL` (consulta
[variables de entorno](environment-variables.md)).

## Delegación a CLI (`claude-cli`, `gemini-cli`)

Si tienes una suscripción a la CLI de Claude o Gemini, Veles puede ejecutar el binario
en modo JSON-streaming y actuar como coordinador — manteniendo el bucle local-first sin
una clave de API aparte. Las herramientas de Veles llegan al subproceso solo cuando hay
un puente MCP configurado.

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
