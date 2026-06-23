# مرجع واجهة سطر الأوامر (CLI)

> 🌐 **اللغات:** [English](../../en/reference/cli.md) · [Русский](../../ru/reference/cli.md) · **العربية**

كل أمر في Veles وكل أمر فرعي وكل راية. شغّل `veles <command> --help` للحصول على
التوقيع المرجعيّ المُحدَّث دائمًا — تعكس هذه الصفحة محلِّلات الوسائط في
`src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — تخطّي معالج الإعداد عند أول تشغيل حتى لو كان `~/.veles/config.toml`
  مفقودًا (مقيّد أيضًا بوجود طرفية TTY وبـ `VELES_NO_WIZARD=1`).
- بلا وسائط، يطلق `veles` واجهة [TUI](tui.md) التفاعلية.

تقبل معظم أوامر الوكيل [رايات حلقة الوكيل المشتركة](#shared-agent-loop-flags)
و[أسماء المزوّدين](#provider-names) المسرودة في الأسفل.

---

## دورة حياة المشروع

### `veles init [name]`
أنشئ مشروع Veles جديدًا في الدليل الحالي (دليل حالة `.veles/`
+ `AGENTS.md` + سقالة المحتوى لحزمة التخطيط المختارة).

| الراية | الافتراضي | الغرض |
|---|---|---|
| `name` (موضعيّة) | اسم أساس cwd | اسم المشروع |
| `--layout <name>` | `llm-wiki` | حزمة التخطيط لسقالة المحتوى (`llm-wiki`، `notes`، `bare`، أو حزمة مخصّصة من `~/.veles/layouts/`) |
| `--force` | معطّل | إعادة إنشاء `.veles/` حتى لو كان موجودًا بالفعل |

### `veles schema {validate,edit,fix}`
تحقّق من `AGENTS.md` أو حرّره (ملف سياق المشروع).

- `validate` — التحقّق من أقسام H2 المطلوبة.
- `edit` — فتح `AGENTS.md` في `$EDITOR` (الافتراضي `vi`)، والتحقّق عند الخروج.
- `fix` — إضافة الأقسام المفقودة تفاعليًّا عبر معالج LLM.

### `veles self-doc [refresh|show]`
وَلِّد وثائق المشروع الذاتية واعرضها (`wiki/self-doc/overview.md`).
يعرض `veles self-doc` المجرّد الصفحة الحالية؛ ويعيد `refresh` توليدها.

### `veles doctor`
شغّل فحوصات الصحة على الحالة العامّة للمستخدم وعلى المشروع النشط. يعمل مع
وجود مشروع نشط أو بدونه.

| الراية | الافتراضي | الغرض |
|---|---|---|
| `--json` | معطّل | إصدار تقرير JSON |
| `--strict` | معطّل | الخروج بقيمة غير صفرية عند أي تحذير (تقييد CI) |

### `veles export {full,template} <path>`
احزم المشروع في حُزمة `.tar.gz`. راجع [النسخ الاحتياطي والمشاركة](../how-to/backup-and-share.md).

- `full <path>` — المشروع كاملًا (`.veles/` + `AGENTS.md`)، باستثناء العابرات في وقت التشغيل.
- `template <path>` — مجموعة فرعية مُنقّاة (المخطّط + المهارات + الوحدات + صفحات
  الويكي غير الجلسات)؛ يجرّد `memory.db`، و`sources/`، و`sessions/`، وتصاريح `trust`،
  ويحجب المعلومات الشخصية في النصوص.

### `veles import <path>`
استعد حُزمة أنشأها `veles export`.

| الراية | الافتراضي | الغرض |
|---|---|---|
| `path` (موضعيّة) | — | مسار الحُزمة (`.tar.gz`) |
| `--into <dir>` | cwd | الدليل الهدف |
| `--force` | معطّل | الكتابة فوق `.veles/` موجود في الهدف |

---

## تشغيل الوكيل

### `veles run "<prompt>"`
شغّل موجِّهًا واحدًا من البداية للنهاية مع حفظ الذاكرة ومُحفِّزات القيّم/التعلّم.
يقبل كل [رايات حلقة الوكيل المشتركة](#shared-agent-loop-flags) إضافةً إلى:

| الراية | الافتراضي | الغرض |
|---|---|---|
| `--resume <session_id>` | جلسة جديدة | متابعة جلسة قائمة |
| `--manager` | معطّل | التفكيك عبر مدير متعدّد الوكلاء (أيضًا `VELES_MANAGER_MODE=1`) |
| `--plan` | معطّل | وضع التخطيط: القراءة/البحث/المسوّدة مسموحة، التعديلات محجوبة |
| `--no-agents-md` | معطّل | عدم حقن `AGENTS.md` في موجِّه النظام |
| `--no-index` | معطّل | عدم حقن `wiki/INDEX.md` |
| `--no-compress` | معطّل | تعطيل ضغط السياق بنافذة منزلقة |
| `--no-curator` | معطّل | تعطيل مُحفِّزات القيّم لهذا التشغيل |
| `--no-insights` | معطّل | تعطيل استخلاص الرؤى بعد التشغيل |
| `--no-proposer` | معطّل | تعطيل المُحفِّز التلقائي لمُقترِح المشروع الفرعي |
| `--no-route-refresh` | معطّل | تعطيل تحديث التوجيه بلغة طبيعية من `AGENTS.md` |
| `--no-suggest-promote` | معطّل | تعطيل مُقترِح الترقية التلقائي |
| `--compressor-model <id>` | موجَّه | تجاوز نموذج الضغط |
| `--compress-threshold-tokens <n>` | `50000` | حجم السجلّ الذي يُحفِّز الضغط |

### `veles tui`
افتح حلقة REPL التفاعلية. راجع [مرجع TUI](tui.md). يقبل رايات حلقة الوكيل
المشتركة، و`--resume`، ورايات الحقن/الضغط `--no-*` أعلاه، إضافةً إلى:

| الراية | الافتراضي | الغرض |
|---|---|---|
| `--theme <name>` | من الإعداد أو `everforest` | سمة الألوان (everforest، dracula، gruvbox، tokyo-night، catppuccin) |

### `veles add <source>`
اقرأ مصدرًا (ملفًّا محليًّا أو عنوان `http(s)://`) وركّبه في صفحة ويكي.
يقبل رايات حلقة الوكيل المشتركة.

### `veles curate`
شغّل مرور قيّم واحدًا: ضغط الجلسات غير المعالَجة في صفحات `wiki/sessions/`.

| الراية | الافتراضي | الغرض |
|---|---|---|
| `--limit <n>` | افتراضي صغير | الحدّ الأقصى للجلسات المعالَجة في هذا التشغيل |

إضافةً إلى رايات حلقة الوكيل المشتركة.

### `veles research "<question>"`
بحث عميق: التفكيك إلى أسئلة فرعية ← استكشاف الويب بالتوازي ←
تركيب تقرير مُستشهَد به.

| الراية | الافتراضي | الغرض |
|---|---|---|
| `--max-subquestions <n>` | `4` | زوايا البحث المتوازية |

إضافةً إلى رايات حلقة الوكيل المشتركة.

### `veles dream`
شغّل دورة دمج ذاكرة واحدة في الخلفية (الرؤى ← إزالة تكرار المهارات ← اقتراحات
الترقية ← تنقية الويكي، واختياريًّا دمج LLM).

| الراية | الافتراضي | الغرض |
|---|---|---|
| `--include-consolidation` | معطّل | تشغيل دمج LLM المكلِف (يحتاج مفتاح API) |
| `--dry-run` | معطّل | تشغيل كل الخطوات لكن مع تخطّي عمليات الكتابة في `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | معطّل | تخطّي خطوات فردية |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | تجاوز نموذج الدمج |
| `--provider <name>` | `openrouter` | المزوّد للوكيل الفرعي للدمج |
| `--project-root <path>` | اكتشاف | تجاوز المشروع |

---

## المعرفة: المهارات، الأدوات، الوحدات

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد المهارات في المشروع النشط (مع القياس عن بعد) |
| `show <name>` | طباعة `SKILL.md` لمهارة |
| `add <source> [--name N] [--scope project\|user] [-y]` | التثبيت من عنوان git أو مسار محلي |
| `remove <name> [--scope project\|user] [-y]` | حذف مهارة مثبَّتة |
| `promote <name> [--keep-telemetry]` | نسخ مهارة المشروع إلى نطاق المستخدم (`~/.veles/skills/`) |
| `demote <name> [-y]` | نسخ مهارة المستخدم إلى المشروع النشط |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | إيجاد المهارات شبه المكرّرة |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | سرد المهارات التي تستوفي عتبة الترقية التلقائية |

### `veles tool {list,show,promote}`

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد الأدوات المفهرسة في `memory.db` لهذا المشروع |
| `show <name>` | طباعة بيان أداة + القياس عن بعد |
| `promote <name> [-y]` | نقل أداة المشروع إلى `~/.veles/tools/` (عبر المشاريع) |

### `veles module {list,show,add,remove}`

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد الوحدات المثبَّتة |
| `show <name>` | طباعة بيان وحدة |
| `add <source> [--name N] [-y]` | تثبيت وحدة من عنوان git أو مسار محلي |
| `remove <name> [-y]` | حذف وحدة مثبَّتة |

### `veles browse {modules,skills} [query]`
تصفّح السجلّات المنسَّقة.

| الراية | الافتراضي | الغرض |
|---|---|---|
| `query` (موضعيّة) | `""` | مرشِّح سلسلة فرعية |
| `--source <url>` | قانونيّ | تجاوز مصدر السجلّ |
| `--json` | معطّل | إصدار JSON |

---

## الجلسات والذاكرة

### `veles sessions {list,show,delete,search}`

| الأمر الفرعي | الغرض |
|---|---|
| `list [--limit n]` | سرد الجلسات الأخيرة (الافتراضي 20) |
| `show <session_id>` | طباعة سجلّ أدوار الجلسة كاملًا |
| `delete <session_id>` | حذف جلسة وأدوارها |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | بحث نصّي كامل (FTS5) في محتوى الأدوار |

---

## تعدّد المشاريع

### `veles project {list,add,remove,switch}`

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد المشاريع المسجّلة، الأحدث أولًا |
| `add <path> [--slug S]` | تسجيل دليل مشروع قائم |
| `remove <slug>` | إلغاء تسجيل مشروع (دون المساس بالملفات) |
| `switch <slug>` | طباعة المسار المطلق للمشروع (استخدم `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| الأمر الفرعي | الغرض |
|---|---|
| `init <subdir> [--name N] [--description D]` | إنشاء مشروع فرعي وتسجيله |
| `list` | سرد المشاريع الفرعية للمشروع النشط |
| `switch <slug>` | طباعة المسار المطلق لمشروع فرعي |
| `remove <slug>` | إلغاء تسجيل مشروع فرعي |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | اكتشاف العناقيد الموضوعية واقتراح مشاريع فرعية |

---

## التوجيه والنماذج

### `veles route {show,set,reset,refresh}`
توجيه مجمَّع لكل مهمة — أيّ `provider:model` يتولّى كل نوع مهمة
(`default`، `curator`، `compressor`، `insights`، `skills`، `advisor`، `vision`،
`embedding`). راجع [التوجيه لكل مهمة](../how-to/per-task-routing.md).

| الأمر الفرعي | الغرض |
|---|---|
| `show` | طباعة جدول التوجيه المحلول للمشروع النشط |
| `set <task> <provider:model>` | تثبيت مهمة على مواصفة |
| `reset [task]` | إعادة مهمة واحدة (أو الكل) إلى الافتراضيات |
| `refresh [--force]` | إعادة تحليل تلميحات التوجيه بلغة طبيعية من `AGENTS.md` |

### `veles models <provider>`
سرد نماذج مزوّد. تُخزَّن مزوّدات السحابة (openrouter/openai/gemini) مؤقتًّا لمدة
24 ساعة؛ أمّا المزوّدات المحلية فمباشرة دائمًا.

| الراية | الافتراضي | الغرض |
|---|---|---|
| `provider` (موضعيّة) | — | أحد [أسماء المزوّدين](#provider-names) |
| `--refresh` | معطّل | تجاوز ذاكرة القرص المؤقتة (السحابة فقط) |
| `--json` | معطّل | إصدار `{provider, source, models}` بصيغة JSON |

---

## المهام طويلة الأمد

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
أهداف بعيدة المدى مع ميزانيات ونقاط تفتيش.

| الأمر الفرعي | الغرض |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | سرد الأهداف |
| `show <id> [--json]` | عرض هدف واحد |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | إنشاء هدف |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | إلحاق تقدّم |
| `pause <id>` / `resume <id>` | إيقاف مؤقت / استئناف |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | إنهاء / إلغاء |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
مهام وكيل مجدوَلة.

| الأمر الفرعي | الغرض |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | إنشاء مهمة (الجدولة = cron، أو `<N><s\|m\|h\|d>`، أو طابع زمني ISO) |
| `list [--json]` / `show <id>` | فحص المهام |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | دورة الحياة |
| `history <id> [--limit n]` | عمليات التشغيل الأخيرة |
| `tick` | تشغيل كل المهام المستحقّة مرة واحدة بشكل متزامن (لا حاجة لخدمة خفيّة؛ يقبل رايات حلقة الوكيل) |

---

## الأمان والتحكّم في الوصول

### `veles trust {list,set,revoke,clear}`
تصاريح محفوظة للأدوات الحسّاسة (`run_shell`، `write_file`، `fetch_url`، …).
راجع [الأمان](../how-to/security-and-permissions.md).

| الأمر الفرعي | الغرض |
|---|---|
| `list` | عرض التصاريح (نطاق المستخدم + المشروع) |
| `set <tool> [--scope project\|user]` | منح أداة |
| `revoke <tool> [--scope project\|user\|both]` | إزالة تصريح |
| `clear [--scope project\|user\|all]` | محو التصاريح في نطاق |

### `veles autopilot {enable,disable,status}`
نافذة محدودة زمنيًّا تُسمح فيها طلبات سلّم الثقة تلقائيًّا.

| الأمر الفرعي | الغرض |
|---|---|
| `enable --until <DUR>` | فتح نافذة (`+30m`، `+2h`، `+1d`، أو ISO `2026-05-12T18:00:00Z`) |
| `disable` | إغلاق النافذة الآن |
| `status` | الإبلاغ عمّا إذا كان الطيّار الآلي نشطًا |

### `veles secret {set,get,list,delete}`
أسرار مدعومة بسلسلة مفاتيح نظام التشغيل (مفاتيح API، رموز البوتات).

| الأمر الفرعي | الغرض |
|---|---|
| `set <name> [value]` | التخزين (احذف القيمة للإدخال التفاعلي / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | البحث (مع لجوء افتراضي إلى البيئة) |
| `list` | عرض أيُّ الأسرار القانونية مُهيَّأ |
| `delete <name>` | إزالة سرّ |

---

## الخدمة الخفيّة والقنوات

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
تشغيل/التحكّم في خدمة HTTP+WS الخفيّة. يفتح `veles daemon` المجرّد واجهة
**مُنتقي الخدمة الخفيّة** (مشروع ← خدمات خفيّة ← قنوات). راجع [التشغيل كخدمة خفيّة](../how-to/run-as-daemon.md).

| الأمر الفرعي | الغرض |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | بدء خدمة خفيّة (تنفصل افتراضيًّا) |
| `stop [--name N]` / `status [--name N]` | إيقاف / فحص |
| `list` | سرد الخدمات الخفيّة عبر كل المشاريع |
| `restart [target] [--name N]` | الإيقاف + إعادة الإطلاق على نفس المضيف/المنفذ |
| `delete <target> [-y]` | الإيقاف + الإزالة من السجلّ |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | إعلان جلسة خدمة خفيّة مسمّاة |
| `session list [--all]` / `session delete <name>` | إدارة الجلسات المسمّاة |
| `token add <name>` / `token list` / `token remove <name>` | عمليات CRUD لرمز الحامل |

يقبل `start` أيضًا رايات حلقة الوكيل المشتركة؛ وبالنسبة للخدمة الخفيّة، تأخذ
`--model` / `--provider` افتراضيًّا من إعداد المشروع وتظلّ ثابتة طوال مدة حياة الخدمة.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
بوابات دردشة خارجية (تيليجرام، …) تتحدّث مع خدمة خفيّة. راجع
[ربط تيليجرام](../how-to/connect-telegram.md).

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد منصّات القنوات المسجّلة + أعداد الجلسات |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | بدء بوابة في المقدمة |
| `list-sessions [--channel C]` | عرض تعيينات `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | نسيان تعيين (تبدأ الرسالة التالية من جديد) |
| `add [--channel C] [--session S]` | إرفاق قناة بخدمة خفيّة (معالج؛ بيانات الاعتماد ← سلسلة المفاتيح) |
| `remove <channel> [--session S]` | إزالة ربط قناة |

---

## MCP (خوادم أدوات خارجية)

### `veles mcp {list,test}`
افحص خوادم MCP الخارجية المُهيَّأة تحت `[mcp.servers.*]`. راجع
[خوادم MCP الخارجية](../how-to/external-mcp-servers.md).

| الأمر الفرعي | الغرض |
|---|---|
| `list [--connect-timeout f]` | عرض الخوادم المُهيَّأة، وحالة الاتصال، وأعداد الأدوات |
| `test <server>` | الاتصال بخادم واحد وسرد أدواته |

---

## رايات حلقة الوكيل المشتركة

مقبولة في `run`، و`add`، و`tui`، و`curate`، و`research`، و`job tick`، و`daemon
start`:

| الراية | الافتراضي | الغرض |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: محفوظ) | معرّف النموذج |
| `--provider <name>` | `openrouter` | المزوّد (انظر أدناه) |
| `--max-tokens-total <n>` | `100000` | ميزانية الرموز التراكمية؛ `0` يعطّلها |
| `--max-iterations <n>` | `30` | الحدّ الأقصى لتكرارات استدعاء الأدوات لكل دور |
| `--stream` | معطّل | تدفّق الاستجابة رمزًا برمز |
| `--verbose` / `-v` | معطّل | التقدّم لكل دور إلى stderr |
| `--project-root <path>` | الاكتشاف من cwd | العمل على مشروع في مكان آخر |

## أسماء المزوّدين

`openrouter` (الافتراضي) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

لا تحتاج المزوّدات المحلية (`ollama`، `llamacpp`، `openai-compat`) إلى مفتاح API. راجع
[مرجع المزوّدين](providers.md) و[تهيئة المزوّدين](../how-to/configure-providers.md).
