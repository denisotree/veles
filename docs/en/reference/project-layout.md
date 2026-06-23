# Project layout & state

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

What `veles init` creates, where Veles keeps state, and the project memory schema.

## What `veles init` produces

The user-content half depends on the chosen layout pack (`--layout`,
default `llm-wiki`); the `.veles/` state half is identical everywhere.

```
my-project/                  # veles init  (default llm-wiki layout)
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # raw, immutable source material (agent-readonly)
├── wiki/                    # the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/ sources/
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

With `--layout notes` the content half is a single `notes/` directory; with
`--layout bare` there is no content scaffold at all. `wiki/INDEX.md` (the
on-demand catalog) is generated as the wiki grows; `config.toml`, `tools/`,
and `plans/` appear under `.veles/` once you configure something, an agent
writes a tool, or you run a goal.

## State directories

| Path | Scope | Committed? |
|---|---|---|
| `<project>/AGENTS.md` + layout content (`wiki/`, `sources/`, `notes/`, …) | Project content | **Yes** — this is your knowledge base |
| `<project>/.veles/` | Project machine-state (memory, config, local skills/tools) | No |
| `~/.veles/` | User-global: `config.toml`, trust grants, cross-project skills/tools, layout packs, model cache, locales | No |

`VELES_USER_HOME` redirects `~` for the user-global tree (tests, sandboxes).

## Project memory (`.veles/memory.db` + `.veles/memory/`)

Veles' project memory is a **structured artefact**, separate from your
content and layout-independent. The SQLite database (WAL mode) is the
source of truth; `.veles/memory/` holds the human-readable side (rendered
insight views, session digests, proposals, the system-ops journal).
Key tables:

| Table | Holds |
|---|---|
| `sessions`, `turns` | Conversation history (one row per turn) |
| `turns_fts` | Full-text index over turns (powers `veles sessions search`) |
| `insights`, `insights_fts`, `insight_refs` | Learned insights (canonical rows; markdown views are regenerable) + dedup links |
| `rules`, `rules_fts` | Format/do/don't/preference rules injected into the stable prompt |
| `skills`, `skill_uses`, `skill_tool_refs` | Skill registry + telemetry + tool links |
| `tools`, `tool_uses` | Tool registry + telemetry (use/success/error counts) |
| `project_tree` | Cached project file map + semantic tags for relevance ranking |

See [Project memory & the learning loop](../explanation/project-memory-and-learning-loop.md)
for how these are written and recalled.

## Layout packs

`veles init --layout {llm-wiki|notes|bare|<custom>}` picks the content
layout; the pack owns the scaffold, the AGENTS.md template, writable zones,
and whether the wiki engine (wiki tools, INDEX prompt injection, wiki
recall) is active. See
[layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
