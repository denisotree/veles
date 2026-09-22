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
request_timeout_s = 180                              # اختياري؛ مدة انتظار ردّ واحد
max_retries = 1                                      # اختياري؛ عدد المحاولات لكل طلب

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
| `[engine]` | المزوّد الأساس (`provider` = اسم المزوّد) + النموذج (`model` = معرّف النموذج) للوكيل الرئيسي وسلسلة التوجيه، إضافةً إلى ميزانيتَي العميل `request_timeout_s` / `max_retries` |
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

### كم ننتظر الردّ، وكم مرّة نعيد المحاولة

```toml
[engine]
request_timeout_s = 180
max_retries = 1
```

كلاهما من معاملات **العميل**، ولهذا يوضعان مباشرةً تحت `[engine]` لا داخل
`[engine.request.<provider>]`: ذلك القسم هو *جسم* الطلب، ومهلة الانتظار لا تسافر فيه
أبداً.

بدونهما تُشتقّ المهلة من معرّف النموذج: عائلة الاستدلال تحصل على 900 ثانية، ونسخة
`flash`/`mini` منها على 450 ثانية، وما عدا ذلك 120 ثانية. هذا الاشتقاق تخمين ضعيف
بنيوياً: **الاسم يصف عائلة، بينما زمن الاستجابة يحدّده الخادم الخلفي الذي يقدّمها.**
المعرّف الواحد قد يعمل بسرعة 33 رمزاً/ثانية على خادم و0.8 رمز/ثانية على آخر. فإن لم
يناسب الرقم المشتقّ تشغيلك، فحدّده بنفسك؛ وثبّت الخادم الخلفي (أدناه) إن أردت للرقم
أن يعني الشيء نفسه مرّتين.

`max_retries` مهمّ للسبب ذاته. بدونه تعيد حزمة التطوير المحاولة مرّتين، فتصير مهلة
450 ثانية في الواقع حتى 1350 ثانية في دور واحد — وهو ما يكفي لتفجير ميزانية بدت
سخيّة. القيمة `0` قيمة مشروعة وليست مثل حذف المفتاح.

أولوية كليهما: وسيط صريح في الشيفرة ← `[engine]` ← القيمة المشتقّة من النموذج. أي
قيمة ليست عدداً موجباً (أو، بالنسبة إلى `max_retries`، عدداً صحيحاً غير سالب) توقف
التشغيل بخطأ `ConfigError` يذكر اسم الملف.

**النطاق:** لا يقرأ هذين المفتاحين اليوم سوى محوّل OpenRouter. أمّا عملاء Anthropic
وOpenAI وGemini فيُبنون دون كلا المعاملين ويتجاهلون المفتاحين.

### تثبيت الخادم الخلفي، ومفاتيح أخرى في جسم الطلب

يُمرَّر `[engine.request.<provider>]` **كما هو** إلى جسم الطلب الخاص بذلك المزوّد.
لا يُنمذج Veles مخطط المزوّد، لذا يعمل فورًا أي خيار يقبله المزوّد، دون انتظار أن
يتعرّف عليه Veles:

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

يُفهرَس القسم باسم **المزوّد** (`openrouter`، `anthropic`، `openai`، `gemini`،
`ollama`، `llamacpp`، `openai-compat`) كي يصمد إعداد المشروع الواحد أمام تبديل
الخادم الخلفي: إرسال كتلة `provider` الخاصة بـ OpenRouter إلى llama.cpp يعطي 400،
لذلك يقرأ كل خادم قسمه الفرعي وحده. ومن دون قسم معلَن تبقى الطلبات مطابقة
بايتًا ببايت لما كانت عليه.

**متى تحتاج إليه: قياسات قابلة للتكرار.** يوزّع مُرحِّل مثل OpenRouter النموذج
الواحد على خوادم كثيرة بمستويات تكميم مختلفة، فيختلف تشغيلان على المدخل نفسه
لأسباب لا علاقة لها بالمدخل. التوجيه اللاصق عبر `session_id` يُبقي المحادثة على
خادم واحد، لكنه لا يخبرك **أيّها**.

ثبِّت عبر `order` لا عبر `quantizations`. حتى 2026-09-18 يملك
`z-ai/glm-5.3-flash` تسعة وعشرين نقطة نهاية: 16 على `fp8`، و3 على `fp4`، وواحدة
`nvfp4`، و**تسع لا تُعلن أي تكميم إطلاقًا**، ولا واحدة على `bf16`. أي أن
`quantizations = ["fp8"]` تُبقي 16 مرشّحًا بنوافذ سياق تتراوح بين 262144 و1310720
رمزًا، بينما `order` بعنصر واحد مع `allow_fallbacks = false` يحدّد الخادم قطعًا.
لعرض نقاط نهاية نموذج ما:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

أبقِ التثبيت في مشروع القياس وحده — فالإنتاج يحتاج إلى التوجيه اللاصق، الذي يحفظ
التوافر والرجوع الاحتياطي.

**التحقق من أن التثبيت صمد.** يسجّل كل نداء للنموذج النية والنتيجة معًا في
`.veles/traces.jsonl`: `request_extra` هو ما أُرسل، و`upstream_provider` هو الخادم
الذي أجاب. سطر واحد يكفي:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

أكثر من سطر يعني أن هذا التشغيل خلط الخوادم. وتحمل السجلات نفسها
`reasoning_tokens` (كم من الميزانية ذهب إلى التفكير) و`est_cost_usd` (الكلفة
الفعلية التي يبلّغ عنها المزوّد).

**الأخطاء صاخبة عن قصد.** خطأ إملائي في اسم المزوّد، أو في مسار القسم
(`[engine.reqest.…]`)، يوقف التشغيل بـ `ConfigError` يسمّي الملف والمزوّدين
المعروفين: فالتثبيت الذي لم يصل إلى السلك أصلًا كان سيُبطل بصمت القياس الذي كُتب
من أجله. أما المفاتيح *داخل* القسم الفرعي للمزوّد فلا يفحصها Veles، لأن المزوّد
يفحصها: يردّ OpenRouter بـ `400 provider: Unrecognized key: "quantization"` على
مفتاح مجهول، وبـ `404 No endpoints found …` على قيمة لا تطابق شيئًا.

### كم تُحفظ نصوص المحادثات

**لا يُحذف شيء ما لم تطلب ذلك.** القيمة الافتراضية لـ `turn_retention_days` هي
`0`، أي الاحتفاظ بكل أدوار المحادثة إلى الأبد. اضبطها على عدد من الأيام إن أردت
سقفًا لـ `memory.db`:

```toml
[memory]
turn_retention_days = 90   # 0 (الافتراضي) يحفظ كل شيء
```

عند تفعيلها تُحذف أدوار المحادثة الخام الأقدم من تلك المدة، بينما تُحفظ إلى الأبد
في كل الأحوال **الاستنتاجات** والقواعد المستخلَصة منها. النص الخام هو المادة
الأولية، والاستنتاجات هي الغاية التي قُرئ من أجلها.

يلزم تحقّق **الشرطين معًا** قبل إسقاط أي نص: أن يكون أقدم من النافذة، **وأن** يكون
المنسِّق قد عالج تلك الجلسة فعلًا. أما جلسة لم يبلغها المنسِّق بعد فلا تُحذف أبدًا
مهما بلغ عمرها، وإلا لأُتلف النص قبل أن يُتعلَّم منه شيء.

كلفة التفعيل: لا يجد `veles sessions search` إلا النص الواقع داخل النافذة. أما
`veles sessions list` فيظل يعرض عمليات التشغيل القديمة، لأن صفوف الجلسات (المعرّف
والعنوان والطوابع الزمنية) تبقى — ولا يذهب إلا متن الرسائل. ويجري التنظيف أثناء
`veles dream`، بعد استخلاص الاستنتاجات.

### تدوير السجلات

يُدوَّر `traces.jsonl` و`events.jsonl` عند 50 ميغابايت إلى `<الاسم>.<unix_ts>`،
ويُحتفَظ بأحدث **10** عمليات تدوير — وتُحذف الأقدم منها عند التدوير التالي. وكانت
تُحفَظ من قبل إلى الأبد.

لا شيء يحتاج إلى ضبط عند الأحجام المعتادة: بمعدل ~530 بايت لكل سجل تتبّع و~1.1
كيلوبايت من الأحداث لكل دور للوكيل، يبعد التدوير الأول سنوات. وُجد هذا الإعداد لأن
النمو بلا حدّ وبلا سياسة تسريبٌ سيضطر إلى اكتشافه من يرث هذا الجهاز.

### الصور

تُوصَف الصورة المرسلة إلى قناة قبل أن يبدأ الدور، بالنموذج الذي يشير إليه
`[routing.tasks].vision` — وهو، من دون مسار صريح، نموذج `[engine]` لديك. لذا لا
يحتاج المحرك متعدد الوسائط إلى أي ضبط على الإطلاق.

يختار `[vision] mode` المسار:

- `model` (الافتراضي) — يصف نموذج الرؤية الصورة.
- `ocr` — Tesseract وحده. محلي ومجاني وبلا نداء لأي نموذج لغوي؛ مناسب لمسح
  النصوص.
- `ocr+model` — النص الحرفي أولًا، ثم وصف النموذج.
- `off` — لا يُقرأ شيء؛ ومع ذلك يُحفظ الملف، وللوكيل أن ينادي
  `image_describe` / `image_ocr` بنفسه إن شاء.

اضبط `[vision] model` حين يكون المحرك نصيًّا فقط. ويصلح أي مزوّد قادر على الرؤية،
بما في ذلك خادم محلي: `ollama:llava`، `llamacpp:…`، `openai-compat:…`.

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
