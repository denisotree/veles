# Cómo gestionar skills, herramientas y módulos

> 🌐 **Idiomas:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · **Español** · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles acumula capacidad con el tiempo. Las **skills** son flujos de trabajo
reutilizables, las **herramientas** son acciones ejecutables y los **módulos** son
plug-ins opcionales. Cada uno vive en dos ámbitos: local del proyecto
(`<project>/.veles/`) y global del usuario (`~/.veles/`). Para los conceptos, ver
[skills y herramientas](../explanation/skills-and-tools.md).

## Skills

Una skill es un `SKILL.md` (frontmatter + cuerpo del prompt) que el agente puede
invocar como una herramienta.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Promover / degradar entre ámbitos

Una skill que demuestra ser útil en un proyecto puede pasar al ámbito de usuario
para que todos los proyectos la vean (o al revés):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Encontrar duplicados y candidatos a promoción

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Herramientas

Las herramientas se catalogan en el `memory.db` del proyecto con telemetría de uso.
Veles puede escribir sus propias herramientas mientras trabaja; tú las gestionas
con:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Las herramientas sensibles (`run_shell`, `write_file`, `fetch_url`, …) están
controladas por la [escalera de confianza](security-and-permissions.md).

## Módulos

Un módulo es código Python (`module.toml` + un punto de entrada) que se ejecuta dentro
de Veles — añade capacidades opcionales (proveedores de memoria, embeddings, visión,
STT) sin inflar el núcleo. Instalar uno requiere confirmación por defecto, y se carga
en cada ejecución solo mientras sus archivos sigan coincidiendo con lo que aprobaste
(consulta [mantén las instalaciones bajo control](../../en/how-to/extension-registries.md#keep-installs-honest)).

```bash
veles module list                              # ambos ámbitos, con una columna `scope`
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # instala en ~/.veles/modules/, para todos los proyectos
veles module show <name> [--user]             # manifiesto + sha256 de los archivos
veles module remove <name> [--user]
veles module approve <name> [--user]          # escribe `yes` en una terminal
veles module approve <name> --sha256 <hash>   # sin terminal: el hash que revisaste
```

Los módulos viven en dos ámbitos, igual que las skills y las herramientas: locales al
proyecto (`<project>/.veles/modules/`) y globales del usuario (`~/.veles/modules/`,
cargados en todos los proyectos). Un módulo de usuario pasa por la misma puerta de
aprobación que uno de proyecto, y la puerta se ejecuta antes de comparar nombres. Si un
módulo de proyecto y uno de usuario comparten nombre, se carga el de proyecto aprobado
y Veles avisa de que el de usuario queda oculto; un módulo de proyecto sin aprobar se
omite (la advertencia nombra su directorio) y se carga el de usuario. Dos módulos
aprobados del mismo ámbito con el mismo nombre — se carga el primero (ordenado por
directorio), los demás avisan y se omiten. `veles module {show,approve,remove}` toman
el nombre del manifiesto (el que muestra `list`) y rechazan un nombre que declare más
de un directorio del ámbito, listándolos; `veles module add` se niega a instalar un
módulo cuyo nombre ya declare otro directorio del ámbito.

### Escribir un módulo que añade un proveedor de memoria

El punto de entrada `register(api)` de un módulo puede llamar a
`api.add_memory_provider(name, factory)` para conectar una fuente de memoria externa a
la recuperación. `name` debe coincidir con una sección `[memory.external.<name>]` de
`~/.veles/config.toml`; a `factory` se le pasa esa sección (un `dict`) y debe devolver
un objeto que implemente el protocolo `MemoryProvider` de Veles
(`veles.core.memory.provider`), o `None` para omitir el proveedor:

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

Un proveedor que además implemente `ingest(title, body, *, insight_id) -> bool` (el
protocolo `IngestingMemoryProvider`) recibe también las escrituras de Veles, no solo
las lecturas. Si dos módulos registran el mismo nombre de proveedor, la carga del
segundo falla — se omite con una advertencia y no queda nada registrado a medias. Una
sección configurada en `config.toml` cuyo módulo no está instalado muestra una sola
advertencia con el comando de instalación; la recuperación sigue funcionando sin él.

El registro incluye Honcho, Mem0 y Supermemory como módulos de proveedor listos para
usar — instálalos con `veles registry install --user {honcho,mem0,supermemory}`,
luego ejecuta el comando `uv tool install veles-ai --with '<package>'` que muestra la
instalación (cada uno declara un SDK — `mem0ai>=2.0`, `honcho-ai>=2.5`,
`supermemory>=3.62` — que Veles nunca instala por ti) y rellena la sección
`[memory.external.<name>]` correspondiente:

- **mem0**: `api_key`, `user_id`, opcionalmente `agent_id` (recupera también los
  recuerdos de ese agente) y `host`. La telemetría del SDK está desactivada por
  defecto; cada recuperación hace una petición extra `GET /v1/ping/`.
- **supermemory**: `api_key`, opcionalmente `user_id` (enviado como el `container_tag`
  de la búsqueda) y `base_url`.
- **honcho**: `api_key`, `workspace_id`, opcionalmente `peer_id` (busca solo en los
  mensajes de ese peer) y `base_url`. Cada recuperación hace un get-or-create del
  workspace — crea `workspace_id` si aún no existe.

## Descubrir más

Busca en los registros conectados:

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```
