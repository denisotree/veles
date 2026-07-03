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
| `[engine]` | Proveedor base (`provider` = nombre del proveedor) + modelo (`model` = id del modelo) para el agente principal y la cascada de enrutamiento |
| `[routing.tasks]` | Anulaciones `provider:model` por tarea — consulta [enrutamiento por tarea](../how-to/per-task-routing.md) |
| `[permissions]` | Política de permisos por herramienta (ámbito de proyecto) |
| `[daemon]` | Bind + autoarranque del daemon sin nombre/"por defecto" |
| `[daemon.<name>]` | Una sesión de daemon con nombre (modelo/proveedor/host/puerto/modo propios) |
| `[channels.<type>]` | Un canal servido por el daemon sin nombre (p. ej. `telegram`) |
| `[daemon.<name>.channels.<type>]` | Un canal vinculado a una sesión de daemon con nombre |
| `[mcp.servers.<name>]` | Un servidor MCP externo (fuente de herramientas) |

Tipos de tarea para `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> Las pistas de enrutamiento en lenguaje natural de `AGENTS.md` se analizan en un
> `routing.nl.toml` autogenerado; las entradas explícitas de `[routing.tasks]` siempre
> prevalecen. Ejecuta `veles route refresh` para reanalizarlas. Consulta [enrutamiento por tarea](../how-to/per-task-routing.md).

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
