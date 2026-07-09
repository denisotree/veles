# Referencia de la CLI

> 🌐 **Idiomas:** [English](../../en/reference/cli.md) · [简体中文](../../zh-CN/reference/cli.md) · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · **Español** · [Français](../../fr/reference/cli.md) · [Italiano](../../it/reference/cli.md) · [Português (BR)](../../pt-BR/reference/cli.md) · [Português (PT)](../../pt-PT/reference/cli.md) · [Русский](../../ru/reference/cli.md) · [العربية](../../ar/reference/cli.md) · [हिन्दी](../../hi/reference/cli.md) · [বাংলা](../../bn/reference/cli.md) · [Tiếng Việt](../../vi/reference/cli.md)

Cada comando, subcomando y opción de Veles. Ejecuta `veles <command> --help` para
obtener la firma autorizada y siempre actualizada — esta página refleja los
analizadores de argumentos de `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — omite el asistente de configuración inicial aunque falte
  `~/.veles/config.toml` (también condicionado a un TTY y a `VELES_NO_WIZARD=1`).
- Sin argumentos, `veles` lanza la [TUI](tui.md) interactiva.

La mayoría de los comandos del agente aceptan las [opciones compartidas del bucle del agente](#shared-agent-loop-flags)
y los [nombres de proveedor](#provider-names) listados al final.

---

## Ciclo de vida del proyecto

### `veles init [name]`
Crea un nuevo proyecto Veles en el directorio actual (un directorio de estado `.veles/`
+ `AGENTS.md` + el andamiaje de contenido del paquete de layout elegido).

| Opción | Predeterminado | Propósito |
|---|---|---|
| `name` (posicional) | basename del cwd | Nombre del proyecto |
| `--layout <name>` | `llm-wiki` | Paquete de layout para el andamiaje de contenido (`llm-wiki`, `notes`, `bare` o un paquete personalizado de `~/.veles/layouts/`) |
| `--force` | desactivado | Recrea `.veles/` aunque ya exista |

### `veles schema {validate,edit,fix}`
Valida o edita `AGENTS.md` (el archivo de contexto del proyecto).

- `validate` — comprueba las secciones H2 requeridas.
- `edit` — abre `AGENTS.md` en `$EDITOR` (por defecto `vi`) y valida al salir.
- `fix` — añade interactivamente las secciones que falten mediante un asistente LLM.

### `veles self-doc [refresh|show]`
Genera y muestra la autodocumentación del proyecto (`wiki/self-doc/overview.md`).
`veles self-doc` a secas muestra la página actual; `refresh` la regenera.

### `veles doctor`
Ejecuta comprobaciones de salud sobre el estado global del usuario y el proyecto
activo. Funciona con o sin un proyecto activo.

| Opción | Predeterminado | Propósito |
|---|---|---|
| `--json` | desactivado | Emite un informe JSON |
| `--strict` | desactivado | Sale con código distinto de cero ante cualquier advertencia (para bloquear CI) |
| `--fix` | desactivado | Intenta reparaciones seguras antes de comprobar — actualmente reconstruye un índice de recall de memoria (FTS) corrupto |

`doctor` también valida las secciones de `config.toml` relevantes para la seguridad
(`[channels.*]`, `[daemon.*]`, `[mcp.servers.*]`) y notifica las claves desconocidas
como un error — una errata como `whitlist` en vez de `whitelist` desactiva
silenciosamente un control de acceso, así que aquí falla de forma ruidosa.

### `veles export {full,template} <path>`
Empaqueta el proyecto en un paquete `.tar.gz`. Consulta [Copia de seguridad y compartir](../how-to/backup-and-share.md).

- `full <path>` — proyecto completo (`.veles/` + `AGENTS.md`), sin los efímeros de tiempo de ejecución.
- `template <path>` — subconjunto saneado (schema + skills + módulos + páginas wiki
  que no son de sesión); elimina `memory.db`, `sources/`, `sessions/`, las concesiones de `trust`
  y redacta la información personal del texto.

### `veles import <path>`
Restaura un paquete creado por `veles export`.

| Opción | Predeterminado | Propósito |
|---|---|---|
| `path` (posicional) | — | Ruta del paquete (`.tar.gz`) |
| `--into <dir>` | cwd | Directorio de destino |
| `--force` | desactivado | Sobrescribe un `.veles/` existente en el destino |

---

## Ejecutar el agente

### `veles run "<prompt>"`
Ejecuta un único prompt de principio a fin con persistencia de memoria y los
disparadores del curador/aprendizaje. Acepta todas las [opciones compartidas del bucle del agente](#shared-agent-loop-flags) más:

| Opción | Predeterminado | Propósito |
|---|---|---|
| `--resume <session_id>` | nueva sesión | Continúa una sesión existente |
| `--manager` | desactivado | Descompone mediante el manager multi-agente (también `VELES_MANAGER_MODE=1`) |
| `--verify` | desactivado | Tras la ejecución, el advisor enrutado juzga la respuesta; ante un fallo seguro, reejecuta en el modelo más fuerte (también `VELES_VERIFY_MODE=1`) |
| `--plan` | desactivado | Modo de planificación: se permite leer/buscar/redactar, las mutaciones se bloquean |
| `--no-agents-md` | desactivado | No inyecta `AGENTS.md` en el system prompt |
| `--no-index` | desactivado | No inyecta `wiki/INDEX.md` |
| `--no-compress` | desactivado | Desactiva la compresión de contexto por ventana deslizante |
| `--no-curator` | desactivado | Desactiva los disparadores del curador para esta ejecución |
| `--no-insights` | desactivado | Desactiva la extracción de insights posterior a la ejecución |
| `--no-proposer` | desactivado | Desactiva el autodisparador del proponente de subproyectos |
| `--no-route-refresh` | desactivado | Desactiva el refresco de enrutamiento NL desde `AGENTS.md` |
| `--no-suggest-promote` | desactivado | Desactiva el sugeridor de autopromoción |
| `--compressor-model <id>` | enrutado | Anula el modelo de compresión |
| `--compress-threshold-tokens <n>` | `50000` | Tamaño del historial que dispara la compresión |

### `veles tui`
Abre el REPL interactivo. Consulta la [referencia de la TUI](tui.md). Acepta las
opciones compartidas del bucle del agente, `--resume`, las opciones `--no-*` de
inyección/compresión anteriores y:

| Opción | Predeterminado | Propósito |
|---|---|---|
| `--theme <name>` | config o `everforest` | Tema de color (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
Lee una fuente (un archivo local o una URL `http(s)://`) y la sintetiza en una
página wiki. Acepta las opciones compartidas del bucle del agente.

### `veles curate`
Ejecuta una pasada del curador: compacta las sesiones sin procesar en páginas de `wiki/sessions/`.

| Opción | Predeterminado | Propósito |
|---|---|---|
| `--limit <n>` | un valor por defecto pequeño | Máximo de sesiones a procesar en esta ejecución |

Más las opciones compartidas del bucle del agente.

### `veles research "<question>"`
Investigación profunda: descompone en subpreguntas → explora la web en paralelo →
sintetiza un informe con citas.

| Opción | Predeterminado | Propósito |
|---|---|---|
| `--max-subquestions <n>` | `4` | Ángulos de investigación paralelos |

Más las opciones compartidas del bucle del agente.

### `veles dream`
Ejecuta un ciclo de consolidación de memoria en segundo plano (insights → dedup de skills →
sugerencias de promoción → lint de wiki, opcionalmente consolidación con LLM).

| Opción | Predeterminado | Propósito |
|---|---|---|
| `--include-consolidation` | desactivado | Ejecuta la costosa consolidación con LLM (requiere una clave de API) |
| `--dry-run` | desactivado | Ejecuta todos los pasos pero omite las escrituras en `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | desactivado | Omite pasos individuales |
| `--consolidation-model <id>` | enrutado (recurre a `anthropic/claude-haiku-4.5`) | Anula el modelo de consolidación |
| `--provider <name>` | enrutado | Proveedor para el subagente de consolidación (omítelo para usar el proveedor enrutado del proyecto) |
| `--project-root <path>` | descubrimiento | Anulación del proyecto |

---

## Conocimiento: skills, herramientas, módulos

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcomando | Propósito |
|---|---|
| `list` | Lista las skills del proyecto activo (con telemetría) |
| `show <name>` | Imprime el `SKILL.md` de una skill |
| `add <source> [--name N] [--scope project\|user] [-y]` | Instala desde una URL de git o una ruta local |
| `remove <name> [--scope project\|user] [-y]` | Elimina una skill instalada |
| `promote <name> [--keep-telemetry]` | Copia una skill de proyecto al ámbito de usuario (`~/.veles/skills/`) |
| `demote <name> [-y]` | Copia una skill de usuario al proyecto activo |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Encuentra skills casi duplicadas |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | Lista las skills que cumplen el umbral de autopromoción |

### `veles tool {list,show,promote,approve}`

| Subcomando | Propósito |
|---|---|
| `list` | Lista las herramientas catalogadas en el `memory.db` de este proyecto |
| `show <name>` | Imprime el manifiesto + la telemetría de una herramienta |
| `promote <name> [-y]` | Mueve una herramienta de proyecto a `~/.veles/tools/` (entre proyectos) |
| `approve [<name>] [--all] [-y]` | Revisa + aprueba un archivo de herramienta de autoría propia para que el cargador lo ejecute |

Las herramientas de autoría propia (`.veles/tools/*.py`) ejecutan su código a nivel
de módulo cuando el cargador las importa, por lo que un archivo nuevo o editado **no
se carga hasta que lo apruebas** — `veles tool approve` muestra el código y registra
su hash. `veles tool approve` a secas lista lo que está pendiente. Por eso una
herramienta escrita por el agente necesita un paso de revisión antes de poder invocarse.

### `veles module {list,show,add,remove}`

| Subcomando | Propósito |
|---|---|
| `list` | Lista los módulos instalados |
| `show <name>` | Imprime el manifiesto de un módulo |
| `add <source> [--name N] [-y]` | Instala un módulo desde una URL de git o una ruta local |
| `remove <name> [-y]` | Elimina un módulo instalado |

### `veles browse {modules,skills} [query]`
Explora los registros curados.

| Opción | Predeterminado | Propósito |
|---|---|---|
| `query` (posicional) | `""` | Filtro por subcadena |
| `--source <url>` | canónico | Anula la fuente del registro |
| `--json` | desactivado | Emite JSON |

---

## Sesiones y memoria

### `veles sessions {list,show,delete,search}`

| Subcomando | Propósito |
|---|---|
| `list [--limit n]` | Lista las sesiones recientes (por defecto 20) |
| `show <session_id>` | Imprime el historial completo de turnos de una sesión |
| `delete <session_id>` | Elimina una sesión y sus turnos |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Búsqueda de texto completo (FTS5) sobre el contenido de los turnos |

---

## Multiproyecto

### `veles project {list,add,remove,switch}`

| Subcomando | Propósito |
|---|---|
| `list` | Lista los proyectos registrados, los más recientes primero |
| `add <path> [--slug S]` | Registra un directorio de proyecto existente |
| `remove <slug>` | Desregistra un proyecto (los archivos no se tocan) |
| `switch <slug>` | Imprime la ruta absoluta del proyecto (usa `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcomando | Propósito |
|---|---|
| `init <subdir> [--name N] [--description D]` | Crea + registra un subproyecto |
| `list` | Lista los subproyectos del proyecto activo |
| `switch <slug>` | Imprime la ruta absoluta de un subproyecto |
| `remove <slug>` | Desregistra un subproyecto |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Detecta clústeres temáticos y propone subproyectos |

---

## Enrutamiento y modelos

### `veles route {show,set,reset,refresh}`
Enrutamiento de ensamble por tarea — qué `provider:model` gestiona cada tipo de tarea
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`). Consulta [enrutamiento por tarea](../how-to/per-task-routing.md).

| Subcomando | Propósito |
|---|---|
| `show` | Imprime la tabla de enrutamiento resuelta para el proyecto activo |
| `set <task> <provider:model>` | Fija una tarea a una especificación |
| `reset [task]` | Restablece una tarea (o todas) a los valores por defecto |
| `refresh [--force]` | Reanaliza las pistas de enrutamiento en lenguaje natural de `AGENTS.md` |

### `veles models <provider>`
Lista los modelos de un proveedor. Los proveedores en la nube (openrouter/openai/gemini)
se cachean 24 h; los proveedores locales siempre están en vivo.

| Opción | Predeterminado | Propósito |
|---|---|---|
| `provider` (posicional) | — | Uno de los [nombres de proveedor](#provider-names) |
| `--refresh` | desactivado | Omite la caché en disco (solo nube) |
| `--json` | desactivado | Emite `{provider, source, models}` como JSON |

---

## Tareas de larga duración

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Objetivos de largo horizonte con presupuestos y puntos de control.

| Subcomando | Propósito |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | Lista los objetivos |
| `show <id> [--json]` | Muestra un objetivo |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | Crea un objetivo |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | Añade progreso |
| `pause <id>` / `resume <id>` | Pausa / reanuda |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Finaliza / cancela |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Trabajos del agente programados.

| Subcomando | Propósito |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | Crea un trabajo (schedule = cron, `<N><s\|m\|h\|d>` o marca de tiempo ISO) |
| `list [--json]` / `show <id>` | Inspecciona trabajos |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Ciclo de vida |
| `history <id> [--limit n]` | Ejecuciones recientes |
| `tick` | Ejecuta de forma síncrona todos los trabajos vencidos una vez (sin necesidad de daemon; admite las opciones del bucle del agente) |

---

## Seguridad y control de acceso

### `veles trust {list,set,revoke,clear}`
Concesiones persistidas para herramientas sensibles (`run_shell`, `write_file`, `fetch_url`, …).
Consulta [seguridad](../how-to/security-and-permissions.md).

| Subcomando | Propósito |
|---|---|
| `list` | Muestra las concesiones (ámbito de usuario + proyecto) |
| `set <tool> [--scope project\|user]` | Concede una herramienta |
| `revoke <tool> [--scope project\|user\|both]` | Elimina una concesión |
| `clear [--scope project\|user\|all]` | Borra las concesiones de un ámbito |

### `veles autopilot {enable,disable,status}`
Una ventana acotada en el tiempo en la que las solicitudes de la escala de confianza se autorizan automáticamente.

| Subcomando | Propósito |
|---|---|
| `enable --until <DUR>` | Abre una ventana (`+30m`, `+2h`, `+1d` o ISO `2026-05-12T18:00:00Z`) |
| `disable` | Cierra la ventana ahora |
| `status` | Informa si el autopilot está activo |

### `veles secret {set,get,list,delete}`
Secretos respaldados por el llavero del SO (claves de API, tokens de bot).

| Subcomando | Propósito |
|---|---|
| `set <name> [value]` | Almacena (omite el valor para entrada interactiva / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Consulta (recurre a la variable de entorno por defecto) |
| `list` | Muestra qué secretos canónicos están configurados |
| `delete <name>` | Elimina un secreto |

---

## Daemon y canales

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Ejecuta/controla el daemon HTTP+WS. `veles daemon` a secas abre la **TUI del selector
de daemons** (proyecto → daemons → canales). Consulta [ejecutar como daemon](../how-to/run-as-daemon.md).

| Subcomando | Propósito |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Inicia un daemon (se desacopla por defecto) |
| `stop [--name N]` / `status [--name N]` | Detiene / inspecciona |
| `list` | Lista los daemons de todos los proyectos |
| `restart [target] [--name N]` | Detiene + relanza en el mismo host/puerto |
| `delete <target> [-y]` | Detiene + elimina del registro |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Declara una sesión de daemon con nombre |
| `session list [--all]` / `session delete <name>` | Gestiona las sesiones con nombre |
| `token add <name>` / `token list` / `token remove <name>` | CRUD de tokens bearer |

`start` también acepta las opciones compartidas del bucle del agente; para el daemon, `--model` /
`--provider` toman por defecto la configuración del proyecto y quedan fijados durante toda la vida del daemon.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
Pasarelas de chat externas (Telegram, …) que hablan con un daemon. Consulta
[conectar Telegram](../how-to/connect-telegram.md).

| Subcomando | Propósito |
|---|---|
| `list` | Lista las plataformas de canal registradas + recuentos de sesiones |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | Inicia una pasarela en primer plano |
| `list-sessions [--channel C]` | Muestra los mapeos `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | Olvida un mapeo (el siguiente mensaje empieza de cero) |
| `add [--channel C] [--session S]` | Adjunta un canal a un daemon (asistente; credenciales → llavero) |
| `remove <channel> [--session S]` | Elimina una vinculación de canal |

---

## MCP (servidores de herramientas externos)

### `veles mcp {list,test}`
Inspecciona los servidores MCP externos configurados bajo `[mcp.servers.*]`. Consulta
[servidores MCP externos](../how-to/external-mcp-servers.md).

| Subcomando | Propósito |
|---|---|
| `list [--connect-timeout f]` | Muestra los servidores configurados, el estado de conexión y los recuentos de herramientas |
| `test <server>` | Conecta a un servidor y lista sus herramientas |

---

## Opciones compartidas del bucle del agente

Aceptadas por `run`, `add`, `tui`, `curate`, `research`, `job tick` y `daemon
start`:

| Opción | Predeterminado | Propósito |
|---|---|---|
| `--model <id>` | resuelto desde el modelo de `[engine]` del proyecto → `default_model` del usuario (sin valor por defecto codificado) | ID del modelo |
| `--provider <name>` | `openrouter` | Proveedor (ver más abajo) |
| `--max-tokens-total <n>` | `100000` | Presupuesto de tokens acumulado; `0` lo desactiva |
| `--max-iterations <n>` | `1000` | Máximo de iteraciones de llamada a herramientas por turno |
| `--stream` | desactivado | Transmite la respuesta token a token |
| `--verbose` / `-v` | desactivado | Progreso por turno a stderr |
| `--project-root <path>` | descubrimiento desde el cwd | Opera sobre un proyecto en otra ubicación |

## Nombres de proveedor

`openrouter` (predeterminado) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Los proveedores locales (`ollama`, `llamacpp`, `openai-compat`) no necesitan clave de API. Consulta la
[referencia de proveedores](providers.md) y [configurar proveedores](../how-to/configure-providers.md).
