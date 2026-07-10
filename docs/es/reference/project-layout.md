# Estructura y estado del proyecto

> 🌐 **Idiomas:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · **Español** · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

Qué crea `veles init`, dónde guarda Veles su estado y el esquema de la memoria del proyecto.

## Qué produce `veles init`

La mitad de contenido de usuario depende del pack de layout elegido (`--layout`,
por defecto `llm-wiki`); la mitad de estado en `.veles/` es idéntica en todas partes.

```
my-project/                  # veles init  (default llm-wiki layout)
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # raw, immutable source material (agent-readonly)
├── wiki/                    # the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/
└── .veles/                  # project state (do not commit; machine-managed)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessions, turns, insights, rules, telemetry
    ├── memory/              # the agent's own memory artefacts:
    │   ├── LOG.md           #   append-only system-ops journal
    │   ├── insights/        #   rendered views of `insights` rows
    │   ├── sessions/        #   compaction summaries
    │   └── proposals/       #   subproject / skill-promotion proposals
    ├── jobs/                # scheduled-job outputs
    └── skills/              # project-local skills
```

Con `--layout notes` la mitad de contenido es un único directorio `notes/`; con
`--layout bare` no hay andamiaje de contenido en absoluto. `wiki/INDEX.md` (el
catálogo bajo demanda) se genera a medida que la wiki crece; `config.toml`, `tools/`
y `plans/` aparecen bajo `.veles/` en cuanto configuras algo, un agente
escribe una herramienta o ejecutas un objetivo.

## Directorios de estado

| Ruta | Ámbito | ¿Versionar? |
|---|---|---|
| `<project>/AGENTS.md` + contenido del layout (`wiki/`, `sources/`, `notes/`, …) | Contenido del proyecto | **Sí** — es tu base de conocimiento |
| `<project>/.veles/` | Estado de máquina del proyecto (memoria, configuración, skills/herramientas locales) | No |
| `~/.veles/` | Global de usuario: `config.toml`, concesiones de confianza, skills/herramientas entre proyectos, packs de layout, caché de modelos, locales | No |

`VELES_USER_HOME` redirige `~` para el árbol global de usuario (tests, sandboxes).

## Memoria del proyecto (`.veles/memory.db` + `.veles/memory/`)

La memoria del proyecto de Veles es un **artefacto estructurado**, separado de tu
contenido e independiente del layout. La base de datos SQLite (modo WAL) es la
fuente de verdad; `.veles/memory/` contiene la cara legible por humanos (vistas
renderizadas de insights, resúmenes de sesiones, propuestas y el diario de
operaciones del sistema). Tablas clave:

| Tabla | Contiene |
|---|---|
| `sessions`, `turns` | Historial de conversación (una fila por turno) |
| `turns_fts` | Índice de texto completo sobre los turnos (alimenta `veles sessions search`) |
| `insights`, `insights_fts`, `insight_refs` | Insights aprendidos (filas canónicas; las vistas markdown son regenerables) + enlaces de deduplicación |
| `rules`, `rules_fts` | Reglas de formato/hacer/no hacer/preferencia inyectadas en el prompt estable |
| `skills`, `skill_uses`, `skill_tool_refs` | Registro de skills + telemetría + enlaces a herramientas |
| `tools`, `tool_uses` | Registro de herramientas + telemetría (contadores de uso/éxito/error) |
| `project_tree` | Mapa de archivos del proyecto cacheado + etiquetas semánticas para ordenar por relevancia |

Consulta [La memoria del proyecto y el bucle de aprendizaje](../explanation/project-memory-and-learning-loop.md)
para ver cómo se escriben y se recuperan.

## Packs de layout

`veles init --layout {llm-wiki|notes|bare|<custom>}` elige el layout de
contenido; el pack es dueño del andamiaje, la plantilla de AGENTS.md, las zonas
escribibles y de si el motor de wiki (herramientas de wiki, inyección del prompt
INDEX, recuperación de wiki) está activo. Consulta
[Packs de layout y la LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
