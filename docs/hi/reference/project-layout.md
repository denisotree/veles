# प्रोजेक्ट लेआउट और स्टेट

> 🌐 **भाषाएँ:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · **हिन्दी** · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

`veles init` क्या बनाता है, Veles अपना स्टेट कहाँ रखता है, और प्रोजेक्ट मेमोरी का schema।

## `veles init` क्या बनाता है

user-content वाला हिस्सा चुने गए layout pack पर निर्भर करता है (`--layout`,
default `llm-wiki`); `.veles/` स्टेट वाला हिस्सा हर जगह एक जैसा होता है।

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

`--layout notes` के साथ content वाला हिस्सा सिर्फ एक `notes/` डायरेक्टरी होता है;
`--layout bare` के साथ कोई content scaffold बिल्कुल नहीं होता। `wiki/INDEX.md`
(on-demand catalog) wiki के बढ़ने के साथ जनरेट होता है; `config.toml`, `tools/`,
और `plans/` `.veles/` के अंदर तभी दिखते हैं जब आप कुछ कॉन्फ़िगर करते हैं, कोई agent
कोई tool लिखता है, या आप कोई goal चलाते हैं।

## स्टेट डायरेक्टरीज़

| Path | Scope | Committed? |
|---|---|---|
| `<project>/AGENTS.md` + layout content (`wiki/`, `sources/`, `notes/`, …) | Project content | **हाँ** — यह आपकी knowledge base है |
| `<project>/.veles/` | Project machine-state (memory, config, local skills/tools) | नहीं |
| `~/.veles/` | User-global: `config.toml`, trust grants, cross-project skills/tools, layout packs, model cache, locales | नहीं |

`VELES_USER_HOME` user-global tree के लिए `~` को रीडायरेक्ट करता है (tests, sandboxes)।

## प्रोजेक्ट मेमोरी (`.veles/memory.db` + `.veles/memory/`)

Veles की प्रोजेक्ट मेमोरी एक **structured artefact** है, जो आपके content से
अलग और layout-independent है। SQLite database (WAL mode) ही source of truth है;
`.veles/memory/` human-readable पक्ष रखता है (rendered insight views, session
digests, proposals, system-ops journal)। मुख्य tables:

| Table | Holds |
|---|---|
| `sessions`, `turns` | Conversation history (one row per turn) |
| `turns_fts` | Full-text index over turns (powers `veles sessions search`) |
| `insights`, `insights_fts`, `insight_refs` | Learned insights (canonical rows; markdown views are regenerable) + dedup links |
| `rules`, `rules_fts` | Format/do/don't/preference rules injected into the stable prompt |
| `skills`, `skill_uses`, `skill_tool_refs` | Skill registry + telemetry + tool links |
| `tools`, `tool_uses` | Tool registry + telemetry (use/success/error counts) |
| `project_tree` | Cached project file map + semantic tags for relevance ranking |

ये कैसे लिखे और recall किए जाते हैं, इसके लिए देखें
[Project memory & the learning loop](../explanation/project-memory-and-learning-loop.md)।

## Layout packs

`veles init --layout {llm-wiki|notes|bare|<custom>}` content layout चुनता है; pack
के पास scaffold, AGENTS.md template, writable zones, और यह तय करने का अधिकार होता है
कि wiki engine (wiki tools, INDEX prompt injection, wiki recall) active है या नहीं।
देखें [layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)।
