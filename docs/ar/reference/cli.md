# مرجع واجهة سطر الأوامر (CLI)

> 🌐 **اللغات:** [English](../../en/reference/cli.md) · [简体中文](../../zh-CN/reference/cli.md) · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · [Español](../../es/reference/cli.md) · [Français](../../fr/reference/cli.md) · [Italiano](../../it/reference/cli.md) · [Português (BR)](../../pt-BR/reference/cli.md) · [Português (PT)](../../pt-PT/reference/cli.md) · [Русский](../../ru/reference/cli.md) · **العربية** · [हिन्दी](../../hi/reference/cli.md) · [বাংলা](../../bn/reference/cli.md) · [Tiếng Việt](../../vi/reference/cli.md)

كل أمر وأمر فرعي وعَلَم (flag) في Veles. شغّل `veles <command> --help` للحصول على
التوقيع المرجعي والمحدَّث دائمًا — تعكس هذه الصفحة مُحلِّلات الوسائط الموجودة في
`src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — تخطّي معالج الإعداد لأول مرة حتى لو كان `~/.veles/config.toml`
  غير موجود (مشروط أيضًا بوجود TTY وبالمتغير `VELES_NO_WIZARD=1`).
- بدون أي وسائط، يُطلق `veles` واجهة [TUI](tui.md) التفاعلية.

تقبل معظم أوامر الوكيل [أعلام حلقة الوكيل المشتركة](#shared-agent-loop-flags)
و[أسماء المزوّدين](#provider-names) المذكورة في الأسفل.

---

## دورة حياة المشروع

### `veles init [name]`
أنشئ مشروع Veles جديدًا في الدليل الحالي (دليل حالة `.veles/`
+ `AGENTS.md` + سقالة المحتوى لحزمة التخطيط المختارة).

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `name` (موضعي) | اسم قاعدة الدليل الحالي | اسم المشروع |
| `--layout <name>` | `llm-wiki` | حزمة التخطيط لسقالة المحتوى (`llm-wiki` أو `notes` أو `bare` أو حزمة مخصصة من `~/.veles/layouts/`) |
| `--force` | معطّل | إعادة إنشاء `.veles/` حتى لو كان موجودًا بالفعل |

### `veles schema {validate,edit,fix}`
تحقّق من صحة `AGENTS.md` (ملف سياق المشروع) أو حرّره.

- `validate` — تحقّق من وجود أقسام H2 المطلوبة.
- `edit` — افتح `AGENTS.md` في `$EDITOR` (الافتراضي `vi`)، مع التحقق عند الخروج.
- `fix` — أضِف الأقسام المفقودة تفاعليًا عبر معالج LLM.

### `veles self-doc [refresh|show]`
وَلِّد التوثيق الذاتي للمشروع واعرضه (`wiki/self-doc/overview.md`).
يعرض `veles self-doc` المجرّد الصفحة الحالية؛ بينما يعيد `refresh` توليدها.

### `veles doctor`
شغّل فحوصات الصحة على الحالة العامة للمستخدم والمشروع النشط. يعمل مع وجود
مشروع نشط أو بدونه.

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `--json` | معطّل | إصدار تقرير بصيغة JSON |
| `--strict` | معطّل | الخروج برمز غير صفري عند أي تحذير (بوّابة CI) |

### `veles export {full,template} <path>`
احزم المشروع في حزمة `.tar.gz`. راجع [النسخ الاحتياطي والمشاركة](../how-to/backup-and-share.md).

- `full <path>` — المشروع بأكمله (`.veles/` + `AGENTS.md`)، باستثناء العناصر العابرة وقت التشغيل.
- `template <path>` — مجموعة فرعية مُنقّاة (المخطط + المهارات + الوحدات + صفحات الويكي
  غير الجلسية)؛ تُجرّد `memory.db` و`sources/` و`sessions/` ومنح `trust`، وتُنقّح
  المعلومات الشخصية من النصوص.

### `veles import <path>`
استعِد حزمة أنشأها `veles export`.

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `path` (موضعي) | — | مسار الحزمة (`.tar.gz`) |
| `--into <dir>` | الدليل الحالي | الدليل الهدف |
| `--force` | معطّل | الكتابة فوق `.veles/` موجود في الهدف |

---

## تشغيل الوكيل

### `veles run "<prompt>"`
شغّل موجِّهًا واحدًا من البداية إلى النهاية مع بقاء الذاكرة ومحفّزات
المنسّق/التعلّم. يقبل جميع [أعلام حلقة الوكيل المشتركة](#shared-agent-loop-flags) بالإضافة إلى:

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `--resume <session_id>` | جلسة جديدة | متابعة جلسة قائمة |
| `--manager` | معطّل | التحليل عبر مدير متعدد الوكلاء (أيضًا `VELES_MANAGER_MODE=1`) |
| `--verify` | معطّل | بعد التشغيل، يحكم المستشار المُوجَّه على الإجابة؛ وعند فشل واثق، يُعاد التشغيل على النموذج الأقوى (أيضًا `VELES_VERIFY_MODE=1`) |
| `--plan` | معطّل | وضع التخطيط: القراءة/البحث/المسودّة مسموحة، والتعديلات محظورة |
| `--no-agents-md` | معطّل | عدم حقن `AGENTS.md` في موجِّه النظام |
| `--no-index` | معطّل | عدم حقن `wiki/INDEX.md` |
| `--no-compress` | معطّل | تعطيل ضغط السياق بنافذة منزلقة |
| `--no-curator` | معطّل | تعطيل محفّزات المنسّق لهذا التشغيل |
| `--no-insights` | معطّل | تعطيل استخراج الرؤى بعد التشغيل |
| `--no-proposer` | معطّل | تعطيل المحفّز التلقائي لمقترِح المشاريع الفرعية |
| `--no-route-refresh` | معطّل | تعطيل تحديث التوجيه باللغة الطبيعية من `AGENTS.md` |
| `--no-suggest-promote` | معطّل | تعطيل مُقترِح الترقية التلقائي |
| `--compressor-model <id>` | مُوجَّه | تجاوز نموذج الضغط |
| `--compress-threshold-tokens <n>` | `50000` | حجم السجلّ الذي يُحفّز الضغط |

### `veles tui`
افتح حلقة REPL التفاعلية. راجع [مرجع TUI](tui.md). يقبل أعلام حلقة
الوكيل المشتركة و`--resume` وأعلام الحقن/الضغط `--no-*` أعلاه، بالإضافة إلى:

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `--theme <name>` | حسب الإعداد أو `everforest` | سمة الألوان (everforest، dracula، gruvbox، tokyo-night، catppuccin) |

### `veles add <source>`
اقرأ مصدرًا (ملفًا محليًا أو رابط `http(s)://`) واصهره في صفحة ويكي.
يقبل أعلام حلقة الوكيل المشتركة.

### `veles curate`
شغّل تمريرة منسّق واحدة: اضغط الجلسات غير المعالجة في صفحات `wiki/sessions/`.

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `--limit <n>` | افتراضي صغير | الحدّ الأقصى للجلسات المعالَجة في هذا التشغيل |

بالإضافة إلى أعلام حلقة الوكيل المشتركة.

### `veles research "<question>"`
بحث معمّق: تحليل إلى أسئلة فرعية → استكشاف الويب بالتوازي →
صياغة تقرير مُستشهَد بالمصادر.

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `--max-subquestions <n>` | `4` | زوايا البحث المتوازية |

بالإضافة إلى أعلام حلقة الوكيل المشتركة.

### `veles dream`
شغّل دورة دمج ذاكرة خلفية واحدة (رؤى → إزالة تكرار المهارات → اقتراحات
الترقية → فحص الويكي، مع دمج LLM اختياري).

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `--include-consolidation` | معطّل | تشغيل دمج LLM المكلِف (يتطلب مفتاح API) |
| `--dry-run` | معطّل | تشغيل كل الخطوات مع تخطّي كتابات `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | معطّل | تخطّي خطوات فردية |
| `--consolidation-model <id>` | مُوجَّه (يعود إلى `anthropic/claude-haiku-4.5`) | تجاوز نموذج الدمج |
| `--provider <name>` | مُوجَّه | المزوّد لوكيل الدمج الفرعي (احذفه لاستخدام مزوّد المشروع المُوجَّه) |
| `--project-root <path>` | اكتشاف | تجاوز المشروع |

---

## المعرفة: المهارات والأدوات والوحدات

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد المهارات في المشروع النشط (مع القياسات عن بُعد) |
| `show <name>` | طباعة ملف `SKILL.md` لمهارة |
| `add <source> [--name N] [--scope project\|user] [-y]` | التثبيت من رابط git أو مسار محلي |
| `remove <name> [--scope project\|user] [-y]` | حذف مهارة مُثبَّتة |
| `promote <name> [--keep-telemetry]` | نسخ مهارة مشروع إلى نطاق المستخدم (`~/.veles/skills/`) |
| `demote <name> [-y]` | نسخ مهارة مستخدم إلى المشروع النشط |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | إيجاد المهارات شبه المكرّرة |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | سرد المهارات التي تستوفي حدّ الترقية التلقائي |

### `veles tool {list,show,promote}`

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد الأدوات المفهرسة في `memory.db` لهذا المشروع |
| `show <name>` | طباعة بيان أداة + القياسات عن بُعد |
| `promote <name> [-y]` | نقل أداة مشروع إلى `~/.veles/tools/` (عبر المشاريع) |

### `veles module {list,show,add,remove}`

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد الوحدات المُثبَّتة |
| `show <name>` | طباعة بيان وحدة |
| `add <source> [--name N] [-y]` | تثبيت وحدة من رابط git أو مسار محلي |
| `remove <name> [-y]` | حذف وحدة مُثبَّتة |

### `veles browse {modules,skills} [query]`
تصفّح السجلّات المُنسَّقة.

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `query` (موضعي) | `""` | مرشّح بسلسلة جزئية |
| `--source <url>` | المعياري | تجاوز مصدر السجلّ |
| `--json` | معطّل | إصدار JSON |

---

## الجلسات والذاكرة

### `veles sessions {list,show,delete,search}`

| الأمر الفرعي | الغرض |
|---|---|
| `list [--limit n]` | سرد الجلسات الأخيرة (الافتراضي 20) |
| `show <session_id>` | طباعة سجلّ الأدوار الكامل لجلسة |
| `delete <session_id>` | حذف جلسة وأدوارها |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | بحث نصّي كامل (FTS5) في محتوى الأدوار |

---

## تعدّد المشاريع

### `veles project {list,add,remove,switch}`

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد المشاريع المُسجَّلة، الأحدث أولًا |
| `add <path> [--slug S]` | تسجيل دليل مشروع قائم |
| `remove <slug>` | إلغاء تسجيل مشروع (دون المساس بالملفات) |
| `switch <slug>` | طباعة المسار المطلق للمشروع (استخدم `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| الأمر الفرعي | الغرض |
|---|---|
| `init <subdir> [--name N] [--description D]` | إنشاء وتسجيل مشروع فرعي |
| `list` | سرد المشاريع الفرعية للمشروع النشط |
| `switch <slug>` | طباعة المسار المطلق لمشروع فرعي |
| `remove <slug>` | إلغاء تسجيل مشروع فرعي |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | كشف التجمّعات الموضوعية واقتراح مشاريع فرعية |

---

## التوجيه والنماذج

### `veles route {show,set,reset,refresh}`
توجيه التجميع حسب المهمة — أي `provider:model` يتولّى كل نوع مهمة
(`default` و`curator` و`compressor` و`insights` و`skills` و`advisor` و`vision`
و`embedding`). راجع [التوجيه حسب المهمة](../how-to/per-task-routing.md).

| الأمر الفرعي | الغرض |
|---|---|
| `show` | طباعة جدول التوجيه المُحلَّل للمشروع النشط |
| `set <task> <provider:model>` | تثبيت مهمة على مواصفة |
| `reset [task]` | إعادة تعيين مهمة واحدة (أو الكل) إلى الافتراضيات |
| `refresh [--force]` | إعادة تحليل تلميحات التوجيه باللغة الطبيعية من `AGENTS.md` |

### `veles models <provider>`
سرد نماذج مزوّد. المزوّدون السحابيون (openrouter/openai/gemini) مُخزَّنون
مؤقتًا لمدة 24 ساعة؛ والمزوّدون المحليون دائمًا حيّون.

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `provider` (موضعي) | — | أحد [أسماء المزوّدين](#provider-names) |
| `--refresh` | معطّل | تجاوز التخزين المؤقت على القرص (السحابي فقط) |
| `--json` | معطّل | إصدار `{provider, source, models}` بصيغة JSON |

---

## المهام طويلة الأمد

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
أهداف بعيدة الأفق بميزانيات ونقاط تفتيش.

| الأمر الفرعي | الغرض |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | سرد الأهداف |
| `show <id> [--json]` | عرض هدف واحد |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | إنشاء هدف |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | إضافة تقدّم |
| `pause <id>` / `resume <id>` | إيقاف مؤقت / استئناف |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | إنهاء / إلغاء |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
مهام وكيل مجدولة.

| الأمر الفرعي | الغرض |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | إنشاء مهمة (الجدول = cron، أو `<N><s\|m\|h\|d>`، أو طابع زمني ISO) |
| `list [--json]` / `show <id>` | فحص المهام |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | دورة الحياة |
| `history <id> [--limit n]` | عمليات التشغيل الأخيرة |
| `tick` | تشغيل جميع المهام المستحقة مرة واحدة بشكل متزامن (لا حاجة إلى عفريت؛ يقبل أعلام حلقة الوكيل) |

---

## الأمان والتحكّم في الوصول

### `veles trust {list,set,revoke,clear}`
منح دائمة للأدوات الحسّاسة (`run_shell` و`write_file` و`fetch_url` …).
راجع [الأمان](../how-to/security-and-permissions.md).

| الأمر الفرعي | الغرض |
|---|---|
| `list` | عرض المنح (نطاق المستخدم + المشروع) |
| `set <tool> [--scope project\|user]` | منح أداة |
| `revoke <tool> [--scope project\|user\|both]` | إزالة منحة |
| `clear [--scope project\|user\|all]` | محو المنح في نطاق |

### `veles autopilot {enable,disable,status}`
نافذة محدودة زمنيًا تُجيز فيها مطالبات سُلَّم الثقة تلقائيًا.

| الأمر الفرعي | الغرض |
|---|---|
| `enable --until <DUR>` | فتح نافذة (`+30m` أو `+2h` أو `+1d` أو ISO `2026-05-12T18:00:00Z`) |
| `disable` | إغلاق النافذة الآن |
| `status` | الإبلاغ عمّا إذا كان الطيّار الآلي نشطًا |

### `veles secret {set,get,list,delete}`
أسرار مدعومة بسلسلة مفاتيح نظام التشغيل (مفاتيح API، رموز البوتات).

| الأمر الفرعي | الغرض |
|---|---|
| `set <name> [value]` | التخزين (احذف القيمة للإدخال التفاعلي / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | البحث (احتياطي البيئة افتراضيًا) |
| `list` | عرض الأسرار المعيارية المُهيّأة |
| `delete <name>` | إزالة سرّ |

---

## العفريت والقنوات

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
تشغيل/التحكم في عفريت HTTP+WS. يفتح `veles daemon` المجرّد **مُنتقي العفاريت**
في TUI (مشروع → عفاريت → قنوات). راجع [التشغيل كعفريت](../how-to/run-as-daemon.md).

| الأمر الفرعي | الغرض |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | بدء عفريت (ينفصل افتراضيًا) |
| `stop [--name N]` / `status [--name N]` | إيقاف / فحص |
| `list` | سرد العفاريت عبر جميع المشاريع |
| `restart [target] [--name N]` | إيقاف + إعادة إطلاق على المضيف/المنفذ نفسه |
| `delete <target> [-y]` | إيقاف + إزالة من السجلّ |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | إعلان جلسة عفريت مُسمّاة |
| `session list [--all]` / `session delete <name>` | إدارة الجلسات المُسمّاة |
| `token add <name>` / `token list` / `token remove <name>` | عمليات CRUD لرمز الحامل |

يقبل `start` أيضًا أعلام حلقة الوكيل المشتركة؛ وللعفريت، يأخذ `--model` /
`--provider` افتراضهما من إعداد المشروع ويُثبَّتان طوال عمر العفريت.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
بوّابات دردشة خارجية (Telegram …) تتحدّث إلى عفريت. راجع
[ربط Telegram](../how-to/connect-telegram.md).

| الأمر الفرعي | الغرض |
|---|---|
| `list` | سرد منصّات القنوات المُسجَّلة + أعداد الجلسات |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | بدء بوّابة في المقدّمة |
| `list-sessions [--channel C]` | عرض تعيينات `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | نسيان تعيين (تبدأ الرسالة التالية من جديد) |
| `add [--channel C] [--session S]` | ربط قناة بعفريت (معالج؛ بيانات الاعتماد ← سلسلة المفاتيح) |
| `remove <channel> [--session S]` | إزالة ربط قناة |

---

## MCP (خوادم أدوات خارجية)

### `veles mcp {list,test}`
فحص خوادم MCP الخارجية المُهيّأة ضمن `[mcp.servers.*]`. راجع
[خوادم MCP الخارجية](../how-to/external-mcp-servers.md).

| الأمر الفرعي | الغرض |
|---|---|
| `list [--connect-timeout f]` | عرض الخوادم المُهيّأة وحالة الاتصال وأعداد الأدوات |
| `test <server>` | الاتصال بخادم واحد وسرد أدواته |

---

## أعلام حلقة الوكيل المشتركة

تقبلها الأوامر `run` و`add` و`tui` و`curate` و`research` و`job tick` و`daemon
start`:

| العَلَم | الافتراضي | الغرض |
|---|---|---|
| `--model <id>` | محلول من نموذج `[provider]` للمشروع → `default_model` للمستخدم (لا افتراضي مُضمَّن) | معرّف النموذج |
| `--provider <name>` | `openrouter` | المزوّد (انظر أدناه) |
| `--max-tokens-total <n>` | `100000` | ميزانية الرموز التراكمية؛ يُعطِّلها `0` |
| `--max-iterations <n>` | `30` | الحدّ الأقصى لتكرارات استدعاء الأدوات لكل دور |
| `--stream` | معطّل | بثّ الاستجابة رمزًا برمز |
| `--verbose` / `-v` | معطّل | تقدّم كل دور إلى stderr |
| `--project-root <path>` | اكتشاف من الدليل الحالي | العمل على مشروع في مكان آخر |

## أسماء المزوّدين

`openrouter` (الافتراضي) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

لا يحتاج المزوّدون المحليون (`ollama` و`llamacpp` و`openai-compat`) إلى مفتاح API. راجع
[مرجع المزوّدين](providers.md) و[تهيئة المزوّدين](../how-to/configure-providers.md).
