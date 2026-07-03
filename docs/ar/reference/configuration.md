# مرجع الإعداد

> 🌐 **اللغات:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · **العربية** · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

يُهيَّأ Veles عبر ملفّي TOML ومجموعة من أدلّة الحالة. لا تُكتَب الأسرار
(مفاتيح API، رموز البوتات) **أبدًا** في هذه الملفات — فهي تُخزَّن في سلسلة مفاتيح
نظام التشغيل أو في متغيّرات البيئة (راجع [متغيّرات البيئة](environment-variables.md)).

## أين تُخزَّن الحالة

| المسار | النطاق | المحتويات |
|---|---|---|
| `~/.veles/` | عام للمستخدم | `config.toml`، منح الثقة، المهارات/الأدوات عبر المشاريع، ذاكرة النماذج المؤقتة، اللغات، السجلّ |
| `<project>/.veles/` | محلي للمشروع | `project.toml`، `config.toml`، `memory.db`، مهارات/أدوات المشروع، الخطط، العناصر وقت التشغيل |
| `<project>/AGENTS.md` | المشروع | ملف السياق المحقون في الوكيل (مرتبط رمزيًا بـ `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`، `sources/` | المشروع | محتوى المستخدم (تخطيط LLM-Wiki الافتراضي) |

يُعيد `VELES_USER_HOME` توجيه `~` (بحيث تُخزَّن حالة المستخدم في `<override>/.veles/`).
راجع [تخطيط المشروع](project-layout.md) للاطّلاع على الشجرة الكاملة.

---

## إعداد المستخدم — `~/.veles/config.toml`

يكتبه معالج التشغيل لأول مرة؛ ويمكن تحريره يدويًا بأمان.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| المفتاح | النوع | الغرض |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | لغة سلاسل الواجهة (قابلة للتجاوز عبر `VELES_LOCALE`) |
| `[user] default_provider` | سلسلة | المزوّد المستخدَم عند عدم تحديد أي مزوّد |
| `[user] default_model` | سلسلة | النموذج المستخدَم عند عدم تحديد أي نموذج |
| `[user] tui_theme` | سلسلة | سمة ألوان TUI الافتراضية |
| `[permissions] <tool>` | سياسة | سياسة الإذن لكل أداة (راجع [الثقة وصندوق الحماية](../explanation/trust-and-sandbox.md)) |

---

## إعداد المشروع — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### الأقسام

| القسم | الغرض |
|---|---|
| `[engine]` | المزوّد الأساس (`provider` = اسم المزوّد) + النموذج (`model` = معرّف النموذج) للوكيل الرئيسي وسلسلة التوجيه |
| `[routing.tasks]` | تجاوزات `provider:model` لكل مهمة — راجع [التوجيه حسب المهمة](../how-to/per-task-routing.md) |
| `[permissions]` | سياسة الإذن لكل أداة (نطاق المشروع) |
| `[daemon]` | ربط العفريت غير المُسمّى/"الافتراضي" + التشغيل التلقائي |
| `[daemon.<name>]` | جلسة عفريت مُسمّاة (لها نموذجها/مزوّدها/مضيفها/منفذها/وضعها الخاص) |
| `[channels.<type>]` | قناة يقدّمها العفريت غير المُسمّى (مثل `telegram`) |
| `[daemon.<name>.channels.<type>]` | قناة مرتبطة بجلسة عفريت مُسمّاة |
| `[mcp.servers.<name>]` | خادم MCP خارجي (مصدر أدوات) |

أنواع المهام لـ `[routing.tasks]`: `default` و`curator` و`compressor` و`insights`
و`skills` و`advisor` و`vision` و`embedding`.

> تُحلَّل تلميحات التوجيه باللغة الطبيعية في `AGENTS.md` إلى ملف
> `routing.nl.toml` مُولَّد تلقائيًا؛ وتفوز إدخالات `[routing.tasks]` الصريحة دائمًا. شغّل
> `veles route refresh` لإعادة التحليل. راجع [التوجيه حسب المهمة](../how-to/per-task-routing.md).

### `project.toml`

يحمل `<project>/.veles/project.toml` بيانات المشروع الوصفية الثابتة (`name`
و`created_at` و`schema_version` و`layout`). لا تحرّره يدويًا في العادة.

---

## AGENTS.md

ملف سياق المشروع في جذر المشروع. يُحقَن في موجِّه نظام الوكيل عند بدء التشغيل
ويُربَط رمزيًا بـ `CLAUDE.md` و`GEMINI.md` بحيث يلتقط أي
`claude` أو `gemini` CLI يُطلَق في الدليل السياق نفسه.

أبقِه صغيرًا — تُحمَّل ملفات `.md` المساعِدة (مثل `wiki/INDEX.md`) عند الطلب.
تحقّق من صحة الأقسام المطلوبة عبر `veles schema validate`. راجع
[حزم التخطيط و LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
