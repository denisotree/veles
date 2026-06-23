# Referencia de configuración

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/configuration.md)

Veles se configura mediante dos archivos TOML y un conjunto de directorios de
estado. Los secretos (claves de API, tokens de bots) **nunca** se escriben en
estos archivos: viven en el llavero del sistema operativo o en variables de
entorno (consulta [variables de entorno](environment-variables.md)).

## Dónde reside el estado

| Ruta | Ámbito | Contenido |
|---|---|---|
| `~/.veles/` | Global del usuario | `config.toml`, concesiones de confianza, skills/herramientas entre proyectos, caché de modelos, locales, registro |
| `<project>/.veles/` | Local del proyecto | `project.toml`, `config.toml`, `memory.db`, skills/herramientas del proyecto, planes, artefactos de tiempo de ejecución |
| `<project>/AGENTS.md` | Proyecto | El archivo de contexto inyectado en el agente (enlazado simbólicamente a `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Proyecto | Contenido del usuario (el layout LLM-Wiki por defecto) |

`VELES_USER_HOME` redirige `~` (de modo que el estado del usuario aterriza en
`<override>/.veles/`). Consulta [layout del proyecto](project-layout.md) para ver
el árbol completo.

---

## Configuración de usuario — `~/.veles/config.toml`

Escrita por el asistente de primera ejecución; segura de editar a mano.

```toml
[user]
language = "en"                  # "en" | "ru" — locale de las cadenas de la UI
default_provider = "openrouter"  # proveedor por defecto para nuevos proyectos
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # registrado por el asistente
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # política opcional por herramienta
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # enrutamiento opcional de ámbito de usuario (ver abajo)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # servidores MCP opcionales de ámbito de usuario
transport = "stdio"
command = "python"               # solo el ejecutable — los argumentos van en `args`
args = ["-m", "my_mcp_server"]
```

| Clave | Tipo | Propósito |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale de las cadenas de la UI (sobrescribible mediante `VELES_LOCALE`) |
| `[user] default_provider` | string | Proveedor usado cuando no se da ninguno |
| `[user] default_model` | string | Modelo usado cuando no se da ninguno |
| `[user] tui_theme` | string | Tema de color por defecto de la TUI |
| `[permissions] <tool>` | policy | Política de permisos por herramienta (ver [confianza y sandbox](../explanation/trust-and-sandbox.md)) |

---

## Configuración de proyecto — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base para el agente principal + enrutamiento

[routing.tasks]                  # sobrescrituras por tarea (máxima prioridad por debajo de los flags explícitos)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # el daemon sin nombre / "default"
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # una sesión de daemon con nombre ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # canales globales (servidos por el daemon sin nombre)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # canales vinculados a una sesión de daemon con nombre
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # servidores MCP externos (ámbito de proyecto)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # solo el ejecutable — los argumentos van en `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} se interpola desde el entorno
```

### Secciones

| Sección | Propósito |
|---|---|
| `[provider]` | Proveedor/modelo base para el agente principal y la cascada de enrutamiento |
| `[routing.tasks]` | Sobrescrituras de `provider:model` por tarea — ver [enrutamiento por tarea](../how-to/per-task-routing.md) |
| `[permissions]` | Política de permisos por herramienta (ámbito de proyecto) |
| `[daemon]` | Dirección de escucha + autostart del daemon sin nombre / "default" |
| `[daemon.<name>]` | Una sesión de daemon con nombre (modelo/proveedor/host/puerto/mode propios) |
| `[channels.<type>]` | Un canal servido por el daemon sin nombre (p. ej. `telegram`) |
| `[daemon.<name>.channels.<type>]` | Un canal vinculado a una sesión de daemon con nombre |
| `[mcp.servers.<name>]` | Un servidor MCP externo (fuente de herramientas) |

Tipos de tarea para `[routing.tasks]`: `default`, `curator`, `compressor`,
`insights`, `skills`, `advisor`, `vision`, `embedding`.

> Las pistas de enrutamiento en lenguaje natural en `AGENTS.md` se interpretan en
> un `routing.nl.toml` generado automáticamente; las entradas explícitas de
> `[routing.tasks]` siempre prevalecen. Ejecuta `veles route refresh` para volver a
> interpretarlas. Consulta [enrutamiento por tarea](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` contiene metadatos inmutables del proyecto
(`name`, `created_at`, `schema_version`, `layout`). Normalmente no lo editas a
mano.

---

## AGENTS.md

El archivo de contexto del proyecto, en la raíz del proyecto. Se inyecta en el
prompt del sistema del agente al arrancar y se enlaza simbólicamente a `CLAUDE.md`
y `GEMINI.md` para que una CLI `claude` o `gemini` lanzada en el directorio recoja
el mismo contexto.

Mantenlo pequeño: los archivos `.md` auxiliares (p. ej. `wiki/INDEX.md`) se cargan
bajo demanda. Valida las secciones requeridas con `veles schema validate`.
Consulta [packs de layout y la LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
