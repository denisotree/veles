# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <b>Español</b> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**Un framework de agente CLI minimalista que se vuelve más inteligente con cada sesión.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="REPL de Veles — haz una pregunta y obtén una respuesta fundamentada en la propia memoria del proyecto" width="800">
</p>

A diferencia de las herramientas de chat que empiezan de cero cada vez, Veles mantiene una **memoria de proyecto estructurada** — insights, reglas y conocimiento curado que se acumulan a lo largo de las sesiones y hacen que el agente sea más útil cuanto más lo usas. La forma en que se organiza tu *contenido* es configurable: una wiki LLM al estilo Karpathy por defecto, notas planas, o ninguna estructura en absoluto para repositorios de código. Construido limpio: sin archivos monstruo, sin dependencia de proveedor, sin sincronización en la nube.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (just run `veles` with no subcommand)
```

---

## ¿Por qué Veles?

**Memoria acumulativa** — Cada sesión es destilada por el Curador en memoria por proyecto (insights, reglas de comportamiento, resúmenes de sesión en `.veles/`). El agente recuerda hechos relevantes y decisiones pasadas automáticamente — dejas de reexplicar el mismo contexto. La memoria funciona bajo *cualquier* disposición de contenido.

**Disposiciones de contenido configurables** — `veles init` genera por defecto una wiki LLM al estilo Karpathy; `--layout notes` ofrece un directorio plano de notas; `--layout bare` no añade ninguna estructura (ideal para repositorios de código). Los paquetes de disposición personalizados son un único archivo TOML en `~/.veles/layouts/`.

**Enrutamiento agnóstico al proveedor** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp, o tu suscripción a la CLI de `claude`/`gemini`. Distintos tipos de tareas (planificación, compresión, insights) pueden enrutarse a modelos diferentes.

**Skills que se acumulan** — Los bloques de prompt reutilizables se convierten en herramientas del agente. Promueve una skill de un proyecto a global de usuario y queda disponible en todas partes. La deduplicación integrada encuentra skills casi duplicadas antes de que se desvíen.

**Local primero + en sandbox** — Sin telemetría, sin sincronización en la nube. El agente ve únicamente el directorio del proyecto activo. La escalera de confianza pide permiso en cada llamada a herramienta sensible; concede permisos por adelantado para CI.

**Modular, no monolítico** — Núcleo mínimo (memoria, bucle del agente, protocolo de proveedor, registro de herramientas). Todo lo demás — TUI, daemon, gateway de Telegram, investigación profunda, programador de tareas — es un módulo opcional y cargable.

---

## Inicio rápido

**Requisitos:** Python 3.13+, macOS / Linux (Windows en la medida de lo posible). Instala primero [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

Abre en su lugar el REPL interactivo (el comando `veles` a secas hace lo mismo):

```bash
veles
```

En la primera ejecución, un asistente de configuración te guía por tu idioma preferido, el proveedor de LLM, la clave de API, el modelo por defecto, el tema de color y si inicializar un proyecto en el directorio actual.

---

## Proveedores

| Proveedor | Variable de entorno | Notas |
|---|---|---|
| **OpenRouter** *(recomendado)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — una clave, cientos de modelos |
| Anthropic | `ANTHROPIC_API_KEY` | API directa |
| OpenAI | `OPENAI_API_KEY` | API directa |
| Gemini | `GEMINI_API_KEY` o `GOOGLE_API_KEY` | API directa |
| CLI de `claude` | — | Usa tu suscripción a Claude; no se necesita clave de API |
| CLI de `gemini` | — | Usa tu suscripción a Gemini; no se necesita clave de API |
| Ollama | — | Modelos locales, `http://localhost:11434/v1` |
| llamacpp | — | Modelos locales, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | Cualquier endpoint compatible con OpenAI |

Sobrescribe por ejecución:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

Guarda las claves de API en el llavero del sistema operativo en lugar de en variables de entorno:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## Flujo de trabajo principal

### Elige una disposición de contenido

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

La propia memoria del agente (insights, reglas, resúmenes de sesión en `.veles/`) funciona de forma idéntica bajo cualquier disposición. Los paquetes personalizados son un único `layout.toml` en `~/.veles/layouts/<name>/`.

### Construye una base de conocimiento (disposición llm-wiki)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Base de conocimiento de Veles — ingiere una fuente en una página de wiki, luego haz una pregunta y obtén una respuesta que la cita" width="800">
</p>

El Curador se ejecuta automáticamente después de las sesiones. La extracción de insights detecta frases como "siempre prefiere X" o "nunca hagas Y" y las escribe como insights persistentes del proyecto.

### Investigación profunda

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

Descompone la pregunta en subpreguntas paralelas, explora cada una y sintetiza un informe estructurado.

### Objetivos de larga duración

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### Tareas programadas

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## Enrutamiento de modelos (ensembles)

Enruta distintos tipos de tareas a distintos modelos — configúralo una vez y olvídate.

**Mediante la CLI:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**Mediante lenguaje natural en `AGENTS.md`:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## Skills y módulos

Las **Skills** son bloques de prompt reutilizables (`SKILL.md`) que se convierten en herramientas del agente automáticamente.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

Los **Módulos** son plugins de Python que pueden engancharse al ciclo de vida del agente (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) y vetar despachos de herramientas.

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## Sesión interactiva (REPL)

```bash
veles                        # new session (bare `veles` launches the interactive REPL)
veles --resume <id>          # continue a session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="REPL de Veles — inspectores con barra (/status, /context), cambio de modo y la paleta de comandos" width="800">
</p>

Los comandos con barra muestran todo en vivo — `/status`, `/tokens`, `/context`, `/mode`, `/help` — y `Shift+Tab` alterna entre modos (auto / planning / writing / goal).

| Tecla | Acción |
|---|---|
| `Enter` | Enviar mensaje |
| `Shift+Enter` | Salto de línea en el compositor |
| `Ctrl+I` | Alternar el inspector de actividad de herramientas |
| `Ctrl+R` | Superposición de selección de sesión |
| `Ctrl+G` | Abrir `$EDITOR` con el borrador actual |
| `Tab` | Autocompletado de comandos con barra |
| `Ctrl+D` | Salir |

Comandos con barra: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` y más.

---

## Daemon + Telegram

Ejecuta Veles como un daemon persistente con una API HTTP/WebSocket. En un directorio de proyecto nuevo, `veles daemon start` te guía a través de la configuración — inicializa el proyecto, habilita el daemon y **conecta un canal**: primero elige un *tipo* de canal (Telegram es la única plataforma hoy en día, pero el selector es el punto de unión donde se registran los nuevos canales), luego completa los campos de ese canal (token del bot, lista blanca). No necesitas abrir antes la TUI.

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — asistente que levanta el daemon y conecta un canal de Telegram (primero el tipo de canal, luego su token y lista blanca)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

El comando `veles daemon` a secas abre un panel de control en vivo — un árbol de proyecto → daemons → canales. Inicia, detén, reinicia o elimina daemons, y añade/elimina canales (el mismo flujo de tipo-de-canal-primero, tecla `c`) en todos los proyectos, todo desde el teclado:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — TUI de panel de control: un árbol de proyecto → daemons → canales con iniciar/detener/reiniciar/eliminar y gestión de canales en línea" width="800">
</p>

El mismo asistente de canales también está disponible de forma independiente (`veles channel add`) sobre un proyecto ya en ejecución.

Endpoints de la API: `POST /v1/runs` para enviar un prompt, `WS /v1/runs/{id}/events` para transmitir la respuesta, `GET /v1/sessions` para listar sesiones. Todos excepto `GET /v1/health` requieren `Authorization: Bearer <token>` (genera uno con `veles daemon token add <name>`).

Cada usuario de Telegram obtiene una sesión persistente. Usa `veles channel list-sessions` / `reset-session` para gestionar las asociaciones.

---

## Multiproyecto

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## Confianza y seguridad

Cada llamada a herramienta sensible (ejecución de shell, escritura de archivos, descarga de URLs) pide permiso:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

Concede permisos por adelantado para CI o ejecuciones autónomas prolongadas:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

El agente ve únicamente el directorio del proyecto activo — otros proyectos, escapes por symlink y recorridos con `..` quedan bloqueados.

---

## Exportar / Importar

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## Referencia de la CLI

| Comando | Propósito |
|---|---|
| `veles init [name]` | Crear un nuevo proyecto |
| `veles run "<prompt>"` | Ejecución del agente de un solo turno |
| `veles` | REPL interactivo (sin subcomando) |
| `veles add <file\|url>` | Ingerir una fuente → páginas temáticas de wiki |
| `veles organize` | Reorganizar el contenido del proyecto según el layout activo (proponer y aplicar) |
| `veles research "<question>"` | Investigación profunda multiángulo |
| `veles curate` | Consolidar sesiones en la wiki |
| `veles sessions {list,show,delete,search}` | Gestión de sesiones |
| `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}` | Gestión de skills |
| `veles tool {list,show,promote,approve}` | Gestión de herramientas (`approve` autoriza las herramientas autogeneradas) |
| `veles module {list,add,remove}` | Gestión de plugins |
| `veles browse {modules,skills}` | Buscar en los registros curados de módulos / skills |
| `veles route {show,set,reset,refresh}` | Enrutamiento de modelos |
| `veles schema {validate,edit}` | Validar / editar AGENTS.md |
| `veles self-doc` | Generar la autodocumentación del proyecto |
| `veles layout {sync}` | Mantenimiento del layout-pack |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Objetivos de largo horizonte |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Tareas programadas |
| `veles dream` | Ciclo de consolidación de memoria en segundo plano |
| `veles project {list,add,remove,switch}` | Registro multiproyecto |
| `veles subproject {init,list,switch,remove,suggest}` | Proyectos hijos |
| `veles trust {list,set,revoke,clear}` | Concesiones de confianza |
| `veles autopilot {enable,disable,status}` | Omisión temporal de confianza |
| `veles secret {set,get,list,delete}` | Secretos del llavero del SO |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | Daemon HTTP/WS |
| `veles channel {list,run,list-sessions,reset-session,add,remove}` | Gateway de canal externo |
| `veles mcp {list,test}` | Servidores MCP externos |
| `veles models <provider>` | Listar modelos del proveedor |
| `veles doctor` | Comprobaciones de salud |
| `veles export / import` | Copia de seguridad y transferencia de proyectos |

Cada comando tiene `--help`.

---

## Documentación

Documentación completa — organizada según Diátaxis (tutoriales · guías prácticas · referencia · explicación):

- **Español:** [`docs/es/index.md`](docs/es/index.md)

Otros idiomas: usa el selector 🌐 en la parte superior de cualquier página de la documentación.

---

## Contribuir

Las contribuciones son muy bienvenidas — Veles está **construido para extenderse**. El núcleo se mantiene pequeño (bucle del agente + memoria de proyecto + protocolo de proveedor); casi todo lo demás es un punto de extensión enchufable, así que añadir una capacidad rara vez implica tocar el núcleo:

- **Adaptadores de proveedor** (`src/veles/adapters/`) — conecta un nuevo backend de modelo.
- **Skills** — bloques de prompt y herramientas reutilizables con herencia `extends:`, promocionables de un proyecto a global de usuario.
- **Herramientas** — Python tipado que el agente escribe y reutiliza, bajo `<project>/.veles/tools/`.
- **Paquetes de disposición** — un único `layout.toml` en `~/.veles/layouts/<name>/` define una disposición de contenido completa.
- **Hooks de módulo** — observabilidad, registro y políticas mediante hooks `pre_turn` / `post_turn` (`src/veles/core/modules.py`).
- **Canales y servidores MCP** — nuevos gateways y fuentes de herramientas externas.
- **Locales** — traducciones en `src/veles/locales/`.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

El código está deliberadamente descompuesto — responsabilidad única, sin archivos monstruo. Lee [`CONTRIBUTING.md`](CONTRIBUTING.md) para conocer las convenciones y [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) antes de abrir un PR. Buenas primeras contribuciones: adaptadores de proveedor, skills de flujo de trabajo, hooks de módulo y archivos de locale.

---

## Licencia

Apache 2.0 con concesión de patente — consulta [`LICENSE`](LICENSE) y [`NOTICE`](NOTICE).
