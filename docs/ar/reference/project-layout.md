# بنية المشروع وحالته

> 🌐 **اللغات:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · **العربية** · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

ما الذي ينشئه `veles init`، وأين يحتفظ Veles بحالته، ومخطط ذاكرة المشروع.

## ما الذي ينتجه `veles init`

يعتمد نصف محتوى المستخدم على حزمة البنية المختارة (`--layout`، والافتراضي
`llm-wiki`)؛ أما نصف الحالة في `.veles/` فهو متطابق في كل مكان.

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

مع `--layout notes` يكون نصف المحتوى مجرد دليل `notes/` واحد؛ ومع
`--layout bare` لا يوجد أي هيكل للمحتوى على الإطلاق. ويُولَّد `wiki/INDEX.md`
(الفهرس عند الطلب) مع نمو الويكي؛ بينما يظهر `config.toml` و`tools/`
و`plans/` ضمن `.veles/` بمجرد أن تضبط شيئًا، أو يكتب وكيلٌ أداة،
أو تشغّل هدفًا.

## أدلة الحالة

| المسار | النطاق | مُودَع في git؟ |
|---|---|---|
| `<project>/AGENTS.md` + محتوى البنية (`wiki/`، `sources/`، `notes/`، …) | محتوى المشروع | **نعم** — هذه قاعدة معرفتك |
| `<project>/.veles/` | حالة المشروع الآلية (الذاكرة، الإعدادات، المهارات/الأدوات المحلية) | لا |
| `~/.veles/` | عمومي على مستوى المستخدم: `config.toml`، منح الثقة، المهارات/الأدوات العابرة للمشاريع، حزم البنية، ذاكرة النماذج المؤقتة، الإعدادات المحلية للغات | لا |

يعيد `VELES_USER_HOME` توجيه `~` لشجرة المستخدم العمومية (الاختبارات، البيئات المعزولة).

## ذاكرة المشروع (`.veles/memory.db` + `.veles/memory/`)

ذاكرة مشروع Veles هي **أثرٌ مُهيكَل**، منفصلٌ عن محتواك ومستقل عن البنية.
قاعدة بيانات SQLite (في وضع WAL) هي مصدر الحقيقة؛ بينما يحمل `.veles/memory/`
الجانب القابل للقراءة البشرية (عروض الرؤى المُصيَّرة، خلاصات الجلسات،
الاقتراحات، سجل عمليات النظام). الجداول الرئيسية:

| الجدول | يحوي |
|---|---|
| `sessions`، `turns` | سجل المحادثة (صف لكل دور) |
| `turns_fts` | فهرس النص الكامل عبر الأدوار (يشغّل `veles sessions search`) |
| `insights`، `insights_fts`، `insight_refs` | الرؤى المتعلَّمة (الصفوف الأساسية؛ عروض markdown قابلة لإعادة التوليد) + روابط إزالة التكرار |
| `rules`، `rules_fts` | قواعد التنسيق/الفعل/الامتناع/التفضيل المحقونة في الموجّه المستقر |
| `skills`، `skill_uses`، `skill_tool_refs` | سجل المهارات + القياسات + روابط الأدوات |
| `tools`، `tool_uses` | سجل الأدوات + القياسات (أعداد الاستخدام/النجاح/الخطأ) |
| `project_tree` | خريطة ملفات المشروع المخزَّنة مؤقتًا + وسوم دلالية لترتيب الصلة |

راجع [ذاكرة المشروع وحلقة التعلّم](../explanation/project-memory-and-learning-loop.md)
لمعرفة كيف تُكتَب هذه وتُستدعى.

## حزم البنية

يختار `veles init --layout {llm-wiki|notes|bare|<custom>}` بنية المحتوى؛
وتمتلك الحزمة الهيكل، وقالب AGENTS.md، والمناطق القابلة للكتابة،
وما إذا كان محرك الويكي (أدوات الويكي، حقن موجّه INDEX، استدعاء الويكي)
نشطًا. راجع
[حزم البنية وLLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
