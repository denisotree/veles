# Project layout ও state

> 🌐 **ভাষা:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · **বাংলা** · [Tiếng Việt](../../vi/reference/project-layout.md)

`veles init` কী তৈরি করে, Veles কোথায় state রাখে, এবং project memory schema।

## `veles init` কী তৈরি করে

ব্যবহারকারীর কন্টেন্ট অংশটি নির্ভর করে বেছে নেওয়া layout pack-এর উপর (`--layout`,
ডিফল্ট `llm-wiki`); `.veles/` state অংশটি সর্বত্র অভিন্ন।

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

`--layout notes` দিয়ে কন্টেন্ট অংশটি হয় একটিমাত্র `notes/` ডিরেক্টরি; `--layout bare`
দিয়ে কোনো কন্টেন্ট scaffold-ই থাকে না। wiki বড় হওয়ার সাথে সাথে `wiki/INDEX.md`
(on-demand catalog) তৈরি হয়; `config.toml`, `tools/`, ও `plans/` `.veles/`-এর অধীনে তখনই
আসে যখন আপনি কিছু কনফিগার করেন, কোনো agent একটি tool লেখে, বা আপনি একটি goal চালান।

## State ডিরেক্টরি

| Path | Scope | Committed? |
|---|---|---|
| `<project>/AGENTS.md` + layout content (`wiki/`, `sources/`, `notes/`, …) | Project content | **হ্যাঁ** — এটিই আপনার knowledge base |
| `<project>/.veles/` | Project machine-state (memory, config, local skills/tools) | না |
| `~/.veles/` | User-global: `config.toml`, trust grants, cross-project skills/tools, layout packs, model cache, locales | না |

`VELES_USER_HOME` user-global tree-র জন্য `~` redirect করে (tests, sandboxes)।

## Project memory (`.veles/memory.db` + `.veles/memory/`)

Veles-এর project memory একটি **structured artefact**, যা আপনার কন্টেন্ট থেকে আলাদা
এবং layout-নিরপেক্ষ। SQLite ডাটাবেসটি (WAL mode) হলো source of truth;
`.veles/memory/` মানুষের-পাঠযোগ্য অংশটি ধারণ করে (rendered
insight view, session digest, proposal, system-ops journal)।
মূল table-গুলো:

| Table | Holds |
|---|---|
| `sessions`, `turns` | কথোপকথনের ইতিহাস (প্রতি turn-এ একটি row) |
| `turns_fts` | turn-এর উপর full-text index (`veles sessions search` চালায়) |
| `insights`, `insights_fts`, `insight_refs` | শেখা insight (canonical row; markdown view পুনঃতৈরিযোগ্য) + dedup link |
| `rules`, `rules_fts` | stable prompt-এ inject হওয়া format/do/don't/preference rule |
| `skills`, `skill_uses`, `skill_tool_refs` | skill registry + telemetry + tool link |
| `tools`, `tool_uses` | tool registry + telemetry (use/success/error count) |
| `project_tree` | relevance ranking-এর জন্য cached project file map + semantic tag |

এগুলো কীভাবে লেখা ও recall করা হয় তা জানতে দেখুন
[Project memory ও learning loop](../explanation/project-memory-and-learning-loop.md)।

## Layout pack

`veles init --layout {llm-wiki|notes|bare|<custom>}` কন্টেন্ট layout বেছে নেয়;
pack-টি scaffold, AGENTS.md template, writable অঞ্চল, এবং wiki engine (wiki tool,
INDEX prompt injection, wiki recall) সক্রিয় কিনা তা নিয়ন্ত্রণ করে। দেখুন
[layout pack ও LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)।
