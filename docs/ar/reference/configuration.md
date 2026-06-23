# مرجع الإعداد

> 🌐 **اللغات:** [English](../../en/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · **العربية**

تُهيَّأ Veles بملفّي TOML ومجموعة من أدلّة الحالة. الأسرار
(مفاتيح API، رموز البوتات) لا تُكتَب **أبدًا** في هذه الملفات — بل تعيش في سلسلة
مفاتيح نظام التشغيل أو في متغيّرات البيئة (راجع [متغيّرات البيئة](environment-variables.md)).

## أين تعيش الحالة

| المسار | النطاق | المحتويات |
|---|---|---|
| `~/.veles/` | عامّ للمستخدم | `config.toml`، تصاريح الثقة، المهارات/الأدوات عبر المشاريع، ذاكرة النماذج المؤقتة، اللغات، السجلّ |
| `<project>/.veles/` | محلّي للمشروع | `project.toml`، `config.toml`، `memory.db`، مهارات/أدوات المشروع، الخطط، عابرات وقت التشغيل |
| `<project>/AGENTS.md` | المشروع | ملف السياق المحقون في الوكيل (مرتبط رمزيًّا بـ `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | المشروع | محتوى المستخدم (تخطيط LLM-Wiki الافتراضي) |

يعيد `VELES_USER_HOME` توجيه `~` (فتنزل حالة المستخدم في `<override>/.veles/`).
راجع [تخطيط المشروع](project-layout.md) للاطّلاع على الشجرة الكاملة.

---

## إعداد المستخدم — `~/.veles/config.toml`

يكتبه معالج أول تشغيل؛ ومن الآمن تحريره يدويًّا.

```toml
[user]
language = "en"                  # "en" | "ru" — لغة سلاسل الواجهة
default_provider = "openrouter"  # المزوّد الافتراضي للمشاريع الجديدة
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # يسجّله المعالج
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # سياسة اختيارية لكل أداة
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # توجيه اختياري بنطاق المستخدم (انظر أدناه)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # خوادم MCP اختيارية بنطاق المستخدم
transport = "stdio"
command = "python"               # الملف التنفيذي فقط — الوسائط تذهب في `args`
args = ["-m", "my_mcp_server"]
```

| المفتاح | النوع | الغرض |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | لغة سلاسل الواجهة (قابلة للتجاوز عبر `VELES_LOCALE`) |
| `[user] default_provider` | سلسلة | المزوّد المستخدَم عند عدم تحديد أيّ |
| `[user] default_model` | سلسلة | النموذج المستخدَم عند عدم تحديد أيّ |
| `[user] tui_theme` | سلسلة | سمة ألوان TUI الافتراضية |
| `[permissions] <tool>` | سياسة | سياسة الأذونات لكل أداة (راجع [الثقة والصندوق الرملي](../explanation/trust-and-sandbox.md)) |

---

## إعداد المشروع — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # الأساس للوكيل الرئيسي + التوجيه

[routing.tasks]                  # تجاوزات لكل مهمة (أعلى أولوية تحت الرايات الصريحة)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # الخدمة الخفيّة غير المسمّاة/"الافتراضية"
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # جلسة خدمة خفيّة مسمّاة ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # قنوات عامّة (تخدمها الخدمة الخفيّة غير المسمّاة)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # قنوات مرتبطة بجلسة خدمة خفيّة مسمّاة
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # خوادم MCP خارجية (نطاق المشروع)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # الملف التنفيذي فقط — الوسائط تذهب في `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} يُستبدَل من البيئة
```

### الأقسام

| القسم | الغرض |
|---|---|
| `[provider]` | المزوّد/النموذج الأساسيّ للوكيل الرئيسي وتسلسل التوجيه |
| `[routing.tasks]` | تجاوزات `provider:model` لكل مهمة — راجع [التوجيه لكل مهمة](../how-to/per-task-routing.md) |
| `[permissions]` | سياسة الأذونات لكل أداة (نطاق المشروع) |
| `[daemon]` | ربط وبدء تلقائي للخدمة الخفيّة غير المسمّاة/"الافتراضية" |
| `[daemon.<name>]` | جلسة خدمة خفيّة مسمّاة (نموذج/مزوّد/مضيف/منفذ/وضع خاص بها) |
| `[channels.<type>]` | قناة تخدمها الخدمة الخفيّة غير المسمّاة (مثل `telegram`) |
| `[daemon.<name>.channels.<type>]` | قناة مرتبطة بجلسة خدمة خفيّة مسمّاة |
| `[mcp.servers.<name>]` | خادم MCP خارجي (مصدر أدوات) |

أنواع المهام لـ `[routing.tasks]`: `default`، `curator`، `compressor`، `insights`،
`skills`، `advisor`، `vision`، `embedding`.

> تُحلَّل تلميحات التوجيه بلغة طبيعية في `AGENTS.md` إلى ملف `routing.nl.toml`
> مُولَّد تلقائيًّا؛ وتتفوّق مدخلات `[routing.tasks]` الصريحة دائمًا. شغّل
> `veles route refresh` لإعادة التحليل. راجع [التوجيه لكل مهمة](../how-to/per-task-routing.md).

### `project.toml`

يحمل `<project>/.veles/project.toml` بيانات وصفية ثابتة للمشروع (`name`،
`created_at`، `schema_version`، `layout`). وفي العادة لا تحرّره يدويًّا.

---

## AGENTS.md

ملف سياق المشروع في جذر المشروع. يُحقَن في موجِّه نظام الوكيل عند بدء التشغيل،
ويُربط رمزيًّا بـ `CLAUDE.md` و`GEMINI.md` كي يلتقط `claude` أو `gemini` CLI
المُطلَق في الدليل نفس السياق.

أبقِه صغيرًا — تُحمَّل ملفات `.md` المساعدة (مثل `wiki/INDEX.md`) عند الطلب.
تحقّق من الأقسام المطلوبة بـ `veles schema validate`. راجع
[حزم التخطيط وLLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
