# Referencia de configuración

> 🌐 **Idiomas:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · **Español** · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

Veles se configura mediante dos archivos TOML y un conjunto de directorios de estado.
Los secretos (claves de API, tokens de bot) **nunca** se escriben en estos archivos —
residen en el llavero del SO o en variables de entorno (consulta [variables de entorno](environment-variables.md)).

## Dónde vive el estado

| Ruta | Ámbito | Contenido |
|---|---|---|
| `~/.veles/` | Global del usuario | `config.toml`, concesiones de confianza, skills/herramientas entre proyectos, caché de modelos, locales, registro |
| `<project>/.veles/` | Local del proyecto | `project.toml`, `config.toml`, `memory.db`, skills/herramientas del proyecto, planes, artefactos de tiempo de ejecución |
| `<project>/AGENTS.md` | Proyecto | El archivo de contexto inyectado en el agente (con enlace simbólico a `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Proyecto | Contenido del usuario (el layout LLM-Wiki por defecto) |

`VELES_USER_HOME` redirige `~` (de modo que el estado del usuario acaba en `<override>/.veles/`).
Consulta [layout del proyecto](project-layout.md) para ver el árbol completo.

---

## Configuración del usuario — `~/.veles/config.toml`

Escrito por el asistente de primera ejecución; es seguro editarlo a mano.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Clave | Tipo | Propósito |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale para las cadenas de la UI (anulable mediante `VELES_LOCALE`) |
| `[user] default_provider` | string | Proveedor usado cuando no se indica ninguno |
| `[user] default_model` | string | Modelo usado cuando no se indica ninguno |
| `[user] tui_theme` | string | Tema de color por defecto de la TUI |
| `[permissions] <tool>` | policy | Política de permisos por herramienta (consulta [confianza y sandbox](../explanation/trust-and-sandbox.md)) |

---

## Configuración del proyecto — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)
request_timeout_s = 180                              # opcional; cuánto esperar una respuesta
max_retries = 1                                      # opcional; reintentos por petición

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### Secciones

| Sección | Propósito |
|---|---|
| `[engine]` | Proveedor base (`provider` = nombre del proveedor) + modelo (`model` = id del modelo) para el agente principal y la cascada de enrutamiento, más los presupuestos de cliente `request_timeout_s` / `max_retries` |
| `[routing.tasks]` | Anulaciones `provider:model` por tarea — consulta [enrutamiento por tarea](../how-to/per-task-routing.md) |
| `[permissions]` | Política de permisos por herramienta (ámbito de proyecto) |
| `[daemon]` | Bind + autoarranque del daemon sin nombre/"por defecto" |
| `[daemon.<name>]` | Una sesión de daemon con nombre (modelo/proveedor/host/puerto/modo propios) |
| `[goal]` | El presupuesto de un objetivo nuevo — `max_steps` (30), `max_cost_usd` (5.0), `max_wall_time_s` (3600); los flags de `veles goal start` lo sustituyen |
| `[channels.<type>]` | Un canal servido por el daemon sin nombre (p. ej. `telegram`) |
| `[daemon.<name>.channels.<type>]` | Un canal vinculado a una sesión de daemon con nombre |
| `[mcp.servers.<name>]` | Un servidor MCP externo (fuente de herramientas) |

Tipos de tarea para `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> Las pistas de enrutamiento en lenguaje natural de `AGENTS.md` se analizan en un
> `routing.nl.toml` autogenerado; las entradas explícitas de `[routing.tasks]` siempre
> prevalecen. Ejecuta `veles route refresh` para reanalizarlas. Consulta [enrutamiento por tarea](../how-to/per-task-routing.md).

### Cuánto esperar una respuesta y cuántos reintentos

```toml
[engine]
request_timeout_s = 180
max_retries = 1
```

Ambos son parámetros del **cliente**, por eso van planos en `[engine]` y no en
`[engine.request.<provider>]`: esa sección es el *cuerpo* de la petición, y un
tiempo de espera nunca viaja ahí.

Sin ellos, el tiempo de espera se deduce del id del modelo: una familia de
razonamiento recibe 900 s, una variante `flash`/`mini` de ella 450 s, el resto
120 s. Esa deducción es una conjetura estructuralmente débil: **el nombre describe
una familia, mientras que el tiempo de respuesta lo fija el backend que la sirve.**
Un mismo id puede dar 33 tok/s en un backend y 0,8 tok/s en otro. Cuando el número
deducido no sirva para tu ejecución, fíjalo; y fija también el backend (más abajo)
si quieres que ese número signifique lo mismo dos veces.

`max_retries` importa por la misma razón. Sin él, el SDK reintenta dos veces, así
que un tiempo de espera de 450 s son en realidad hasta 1350 s en un solo turno:
suficiente para reventar un presupuesto que parecía generoso. `0` es un valor
legítimo y no equivale a omitir la clave.

Precedencia de ambos: argumento explícito en código → `[engine]` → valor por
modelo. Un valor que no sea un número positivo (o, para `max_retries`, un entero
no negativo) aborta con un `ConfigError` que nombra el archivo.

**Alcance:** hoy sólo el adaptador de OpenRouter lee estas claves. Los clientes de
Anthropic, OpenAI y Gemini se construyen sin ninguno de los dos parámetros y las
ignoran.

### Fijar un backend y otras claves del cuerpo de la petición

`[engine.request.<provider>]` se envía **tal cual** en el cuerpo de la petición de
ese proveedor. Veles no modela el esquema del proveedor, así que cualquier opción
que este acepte funciona sin esperar a que Veles la conozca:

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

La sección se identifica por el **nombre del proveedor** (`openrouter`,
`anthropic`, `openai`, `gemini`, `ollama`, `llamacpp`, `openai-compat`) para que
una misma configuración de proyecto sobreviva a un cambio de backend: un bloque
`provider` de OpenRouter enviado a llama.cpp sería un 400, así que cada backend
lee solo su propia subsección. Sin sección declarada, las peticiones son idénticas
byte a byte a las de antes.

**Cuándo hace falta: mediciones reproducibles.** Un relé como OpenRouter reparte
un mismo modelo entre muchos backends con cuantizaciones distintas, de modo que
dos ejecuciones con la misma entrada pueden diferir por razones ajenas a la
entrada. El enrutado persistente por `session_id` mantiene una conversación en un
backend, pero no dice en **cuál**.

Fija con `order`, no con `quantizations`. A 18-09-2026, `z-ai/glm-5.3-flash`
tiene 29 endpoints: 16 en `fp8`, 3 en `fp4`, uno en `nvfp4`, **9 que no declaran
cuantización alguna** y ninguno en `bf16`. Por tanto `quantizations = ["fp8"]`
deja 16 candidatos con ventanas de contexto de 262144 a 1310720 tokens, mientras
que un `order` de un solo elemento junto con `allow_fallbacks = false` determina
el backend de forma inequívoca. Para listar los endpoints de un modelo:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

Mantén la fijación solo en el proyecto de medición: producción quiere enrutado
persistente, que preserva disponibilidad y fallback.

**Comprobar que se mantuvo.** Cada llamada al modelo registra en
`.veles/traces.jsonl` tanto la intención como el resultado: `request_extra` es lo
que se envió, `upstream_provider` el backend que respondió. Una línea basta:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

Más de una línea significa que la ejecución mezcló backends. Los mismos registros
llevan `reasoning_tokens` (cuánto presupuesto se fue en razonar) y `est_cost_usd`
(el coste real facturado por el proveedor, cuando lo informa).

**Los errores son ruidosos a propósito.** Un nombre de proveedor mal escrito o un
error en la ruta de la sección (`[engine.reqest.…]`) aborta la ejecución con un
`ConfigError` que nombra el fichero y los proveedores conocidos: una fijación que
nunca llegó al cable invalidaría en silencio la medición para la que se escribió.
Veles no comprueba las claves *dentro* de la subsección del proveedor, porque las
comprueba el propio proveedor: OpenRouter responde
`400 provider: Unrecognized key: "quantization"` a una clave desconocida y
`404 No endpoints found …` a un valor que no casa con nada.

### Cuánto tiempo se conservan las transcripciones

**No se borra nada a menos que lo pidas.** `turn_retention_days` vale `0` por
defecto, lo que conserva para siempre todos los turnos de conversación. Ponle un
número de días para poner un techo a `memory.db`:

```toml
[memory]
turn_retention_days = 90   # 0 (por defecto) conserva todo
```

Con la opción activada, los turnos en bruto más antiguos que ese plazo se
eliminan; los **insights** y las reglas extraídos de ellos se conservan para
siempre en cualquier caso. La transcripción es la materia prima y los insights
son aquello para lo que se leyó.

Deben cumplirse **dos** condiciones antes de descartar una transcripción: que sea
más antigua que la ventana **y** que el curador ya haya procesado esa sesión. Una
sesión que el curador no ha alcanzado nunca se elimina, tenga la edad que tenga;
de lo contrario se destruiría la transcripción antes de haber aprendido nada de
ella.

El coste de activarlo: `veles sessions search` solo encuentra texto dentro de la
ventana. `veles sessions list` sigue mostrando ejecuciones antiguas, porque las
filas de sesión (id, título, marcas de tiempo) se conservan: solo se van los
cuerpos de los mensajes. La limpieza ocurre durante `veles dream`, después de la
extracción de insights.

### Rotación de logs

`traces.jsonl` y `events.jsonl` rotan a los 50 MB hacia `<nombre>.<unix_ts>`, y se
conservan las **10** rotaciones más recientes; las anteriores se borran en la
siguiente rotación. Antes se guardaban para siempre.

Con volúmenes normales no hay nada que configurar: a ~530 bytes por registro de
traza y ~1,1 KB de eventos por turno del agente, la primera rotación queda a años
vista. El ajuste existe porque un crecimiento sin límite y sin política es una
fuga que acabará descubriendo quien herede la máquina.

### Imágenes

Una foto enviada a un canal se describe antes de que empiece el turno, usando el
modelo al que apunta `[routing.tasks].vision`, que sin ruta explícita es tu modelo
de `[engine]`. Un motor multimodal no necesita, por tanto, ninguna configuración.

`[vision] mode` elige la tubería:

- `model` (por defecto) — el modelo de visión describe la imagen.
- `ocr` — solo Tesseract. Local, gratuito, sin llamada al LLM; bueno para
  escaneos de texto.
- `ocr+model` — primero el texto literal, luego la descripción del modelo.
- `off` — no se lee nada; el fichero se guarda igualmente y el agente puede
  llamar a `image_describe` / `image_ocr` por su cuenta si quiere.

Define `[vision] model` cuando el motor sea solo de texto. Sirve cualquier
proveedor con visión, incluido un servidor local: `ollama:llava`, `llamacpp:…`,
`openai-compat:…`.

### `project.toml`

`<project>/.veles/project.toml` contiene metadatos inmutables del proyecto (`name`,
`created_at`, `schema_version`, `layout`). Normalmente no se edita a mano.

---

## AGENTS.md

El archivo de contexto del proyecto, en la raíz del proyecto. Se inyecta en el
system prompt del agente al arrancar y se enlaza simbólicamente a `CLAUDE.md` y `GEMINI.md`
para que una CLI de `claude` o `gemini` lanzada en el directorio recoja el mismo contexto.

Mantenlo pequeño — los archivos `.md` auxiliares (p. ej. `wiki/INDEX.md`) se cargan bajo demanda.
Valida las secciones requeridas con `veles schema validate`. Consulta
[paquetes de layout y la LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
