# Primeros pasos

> 🌐 **Languages:** **English** · [Русский](../../ru/tutorials/getting-started.md)

En este tutorial instalarás Veles, le darás una clave de API, crearás tu primer proyecto
y ejecutarás tu primer prompt. Unos 10 minutos. Terminarás con un proyecto Veles funcional
con el que podrás conversar.

## Requisitos previos

- **Python 3.13+** (Veles requiere `>=3.13`).
- Una clave de API de LLM. Usaremos **OpenRouter** (el proveedor por defecto); cualquiera
  de los [otros proveedores](../reference/providers.md) también funciona, incluidos los
  totalmente locales sin clave.

## 1. Instalar

Veles se instala como un comando global `veles` mediante [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

Para actualizar más adelante: `uv tool upgrade veles-ai`.

## 2. Darle a Veles una clave de API

Consigue una clave en [openrouter.ai](https://openrouter.ai) y expórtala:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

También puedes guardarla en el llavero del SO para no reexportarla en cada shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(¿Prefieres una configuración totalmente local sin clave? Instala [Ollama](https://ollama.com),
`ollama pull qwen3:4b-instruct` y usa `--provider ollama` más abajo.)

## 3. Crear tu primer proyecto

Un proyecto Veles no es más que un directorio con una carpeta de estado `.veles/`. Crea uno:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Esto crea `AGENTS.md` (el contexto de tu proyecto), `sources/` y `wiki/` (el
[layout LLM-Wiki por defecto](../explanation/layout-packs-and-llm-wiki.md)) y
`.veles/` (el estado de la máquina). Consulta [layout del proyecto](../reference/project-layout.md).

## 4. Ejecutar tu primer prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles carga el contexto de tu proyecto, llama al modelo e imprime la respuesta. El
turno se guarda en la memoria del proyecto.

Añade `--stream` para ver los tokens según llegan, o `--verbose` para ver el progreso por turno:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Abrir el REPL interactivo

Para una conversación de varios turnos, abre la TUI:

```bash
veles tui
```

Escribe un mensaje y pulsa Enter. Teclas útiles: `Ctrl+D` para salir, `Shift+Tab` para
recorrer los [modos de ejecución](../explanation/modes.md), `/help` para listar los comandos
de barra. Lista completa en la [referencia de la TUI](../reference/tui.md).

## 6. Ver qué recuerda Veles

Cada ejecución se guarda. Lista y busca en tus sesiones:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Adónde ir después

- **[Crear una base de conocimiento](building-a-knowledge-base.md)** — ingiere fuentes
  en la wiki y hazle preguntas sobre ellas.
- **[Configurar proveedores](../how-to/configure-providers.md)** — cambia a
  Anthropic, OpenAI, Gemini o un modelo totalmente local.
- **[Visión general de la arquitectura](../explanation/architecture.md)** — entiende qué
  hace Veles bajo el capó.
