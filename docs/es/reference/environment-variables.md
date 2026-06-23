# Variables de entorno

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/environment-variables.md)

Veles las lee en tiempo de ejecución. Lo mejor es guardar las claves de API y los
tokens en el llavero del SO (`veles secret set …`); las variables de entorno son el
respaldo y la anulación.

## Claves de API de proveedores

Cascada de búsqueda de la clave de API: llavero del SO (ámbito de proyecto) → llavero del SO (ámbito por defecto)
→ variable de entorno.

| Variable | Proveedor | Notas |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Proveedor por defecto |
| `ANTHROPIC_API_KEY` | anthropic | API directa de Anthropic |
| `OPENAI_API_KEY` | openai | API directa de OpenAI |
| `GEMINI_API_KEY` | gemini | Clave principal para Google Gemini |
| `GOOGLE_API_KEY` | gemini | Respaldo para Google Gemini |

`claude-cli` y `gemini-cli` se autentican mediante sus propios binarios — sin variable de entorno.

## Proveedores locales

| Variable | Predeterminado | Propósito |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint de Ollama |
| `OLLAMA_HOST` | sigue a `OLLAMA_BASE_URL` | Host de Ollama para embeddings |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint del servidor llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (requerido) | Endpoint del proveedor `openai-compat` |
| `VELES_LOCAL_TOOLS` | desactivado | Habilita la llamada a herramientas en proveedores locales (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | valor por defecto del proveedor | Anula el modelo de embeddings de Ollama |

## Canales y daemon

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token del bot de Telegram para `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL base del daemon usada por las pasarelas de canal |
| `VELES_DAEMON_TOKEN` | — | Token bearer para la autenticación del daemon |

## Rutas y locale

| Variable | Predeterminado | Propósito |
|---|---|---|
| `VELES_USER_HOME` | `~` | Anula el home que contiene `~/.veles/` (estado, caché, índice del llavero) |
| `VELES_HOME` | — | Alias heredado de `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Anula la ruta del registro multiproyecto |
| `VELES_LOCALE` | `[user] language` o `en` | Anula el locale activo de la UI para una ejecución |
| `VELES_LOG_LEVEL` | `INFO` | Verbosidad del daemon/log (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Anula el nombre del archivo de configuración (pruebas) |

## Banderas de comportamiento y de funcionalidades

| Variable | Predeterminado | Propósito |
|---|---|---|
| `VELES_NO_WIZARD` | desactivado | Omite el asistente de primera ejecución (también requiere un TTY) |
| `VELES_MANAGER_MODE` | desactivado | Fuerza el manager multi-agente para `veles run` (`1` activa / `0` interruptor de apagado) |
| `VELES_VERIFY_MODE` | desactivado | Fuerza la pasada de verificar→escalar para `veles run` (`1` activa / `0` interruptor de apagado) |
| `VELES_FENCED_TOOLS` | desactivado | Ejecuta las herramientas por la ruta de ejecución vallada/en sandbox |
| `VELES_TRUST_AUTO_ALLOW` | desactivado | Omite la escala de confianza (CI / autopilot / subagentes preautorizados) |
| `VELES_SANDBOX_ROOTS` | proyecto + `~/.veles` | Anulación separada por `:` de las raíces del sandbox de lectura/escritura |
| `VELES_FETCH_ALLOW_PRIVATE` | desactivado | Permite a las herramientas acceder a direcciones RFC-1918 / privadas |
| `VELES_MEMORY_RERANK` | activado | Reordenamiento vectorial del recall de memoria (`0`/`false` lo desactiva) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend de búsqueda web para `research` y `web_search` |

## Registros

| Variable | Propósito |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Fuente para `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Fuente para `veles browse modules` |

## Interno / pruebas

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — internos; no deberías necesitar
configurarlos.
