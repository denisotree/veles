# Variables de entorno

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/environment-variables.md)

Veles las lee en tiempo de ejecución. Las claves de API y los tokens es mejor
guardarlos en el llavero del sistema operativo (`veles secret set …`); las
variables de entorno son el respaldo y la sobrescritura.

## Claves de API de proveedores

Cascada de búsqueda de claves de API: llavero del SO (ámbito de proyecto) →
llavero del SO (ámbito por defecto) → variable de entorno.

| Variable | Proveedor | Notas |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Proveedor por defecto |
| `ANTHROPIC_API_KEY` | anthropic | API directa de Anthropic |
| `OPENAI_API_KEY` | openai | API directa de OpenAI |
| `GEMINI_API_KEY` | gemini | Clave primaria para Google Gemini |
| `GOOGLE_API_KEY` | gemini | Respaldo para Google Gemini |

`claude-cli` y `gemini-cli` se autentican a través de sus propios binarios: sin
variable de entorno.

## Proveedores locales

| Variable | Por defecto | Propósito |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint de Ollama |
| `OLLAMA_HOST` | sigue a `OLLAMA_BASE_URL` | Host de Ollama para embeddings |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint del servidor llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (requerido) | Endpoint para el proveedor `openai-compat` |
| `VELES_LOCAL_TOOLS` | off | Habilita las llamadas a herramientas en proveedores locales (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | valor por defecto del proveedor | Sobrescribe el modelo de embeddings de Ollama |

## Canales y daemon

| Variable | Por defecto | Propósito |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token del bot de Telegram para `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL base del daemon usada por las pasarelas de canal |
| `VELES_DAEMON_TOKEN` | — | Token de portador para la autenticación del daemon |

## Rutas y locale

| Variable | Por defecto | Propósito |
|---|---|---|
| `VELES_USER_HOME` | `~` | Sobrescribe el home que contiene `~/.veles/` (estado, caché, índice del llavero) |
| `VELES_HOME` | — | Alias heredado de `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Sobrescribe la ruta del registro multiproyecto |
| `VELES_LOCALE` | `[user] language` o `en` | Sobrescribe el locale activo de la UI para una ejecución |
| `VELES_LOG_LEVEL` | `INFO` | Verbosidad de daemon/log (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Sobrescribe el nombre del archivo de configuración (pruebas) |

## Comportamiento y feature flags

| Variable | Por defecto | Propósito |
|---|---|---|
| `VELES_NO_WIZARD` | off | Omite el asistente de primera ejecución (también necesita un TTY) |
| `VELES_MANAGER_MODE` | off | Fuerza el manager multiagente para `veles run` (`1` on / `0` interruptor de apagado) |
| `VELES_FENCED_TOOLS` | off | Ejecuta las herramientas por la ruta de ejecución acotada/aislada |
| `VELES_TRUST_AUTO_ALLOW` | off | Omite la escalera de confianza (CI / autopilot / subagentes preautorizados) |
| `VELES_SANDBOX_ROOTS` | proyecto + `~/.veles` | Sobrescritura separada por `:` de las raíces de lectura/escritura del sandbox |
| `VELES_FETCH_ALLOW_PRIVATE` | off | Permite a las herramientas descargar direcciones RFC-1918 / privadas |
| `VELES_MEMORY_RERANK` | on | Reordenamiento vectorial del recall de memoria (`0`/`false` lo desactiva) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend de búsqueda web para `research` y `web_search` |

## Registros

| Variable | Propósito |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Fuente para `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Fuente para `veles browse modules` |

## Interno / pruebas

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — internos; no deberías necesitar
configurarlos.
