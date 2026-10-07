# كيفية ربط خوادم MCP خارجية

> 🌐 **اللغات:** [English](../../en/how-to/external-mcp-servers.md) · [简体中文](../../zh-CN/how-to/external-mcp-servers.md) · [繁體中文](../../zh-TW/how-to/external-mcp-servers.md) · [日本語](../../ja/how-to/external-mcp-servers.md) · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · [Français](../../fr/how-to/external-mcp-servers.md) · [Italiano](../../it/how-to/external-mcp-servers.md) · [Português (BR)](../../pt-BR/how-to/external-mcp-servers.md) · [Português (PT)](../../pt-PT/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · **العربية** · [हिन्दी](../../hi/how-to/external-mcp-servers.md) · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

Veles هو **عميل** [MCP](https://modelcontextprotocol.io/): يمكنه الاتصال بـ
خوادم MCP خارجية وكشف أدواتها للوكيل كأنها مدمجة فيه
(GitHub، وتوثيق المكتبات، والبحث على الويب، وخدماتك الخاصة، …).

## تهيئة خادم

أضف كتلة `[mcp.servers.<name>]` إلى `<project>/.veles/config.toml` — تُقرأ
الخوادم من إعدادات المشروع فقط. يجب أن يطابق `<name>`
النمط `[A-Za-z0-9][A-Za-z0-9_-]{0,31}` — فهو يصبح جزءًا من اسم كل أداة. هناك ثلاثة
أنواع نقل مدعومة: `stdio` (الافتراضي)، و`http`، و`sse`.

| المفتاح | النقل | الافتراضي | الغرض |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (مطلوب) | — | الملف التنفيذي المراد تشغيله — **البرنامج فقط، وليس وسائطه** |
| `args` | stdio | `[]` | قائمة الوسائط، رمز واحد لكل عنصر |
| `env` | stdio | `{}` | بيئة إضافية للعملية الفرعية (تُدمج فوق البيئة الموروثة) |
| `url` | http/sse (مطلوب) | — | نقطة نهاية الخادم |
| `timeout_s` | — | `120` | الميزانية لاستدعاء أداة واحد |
| `connect_timeout_s` | — | `30` | الميزانية للاتصال الأولي |
| `enabled` | — | `true` | عيّنها `false` للإبقاء على الإدخال مع تخطّي الاتصال |

تُستبدل القيم النصية في `command`، و`args`، و`env`، و`url` بقيمة `${VAR}` من
البيئة (المتغيّر غير المعيَّن يصبح سلسلة فارغة مع تحذير) — أبقِ
الأسرار خارج الملف.

> **`command` مقابل `args`.** يشغّل Veles البرنامج مباشرةً (دون صدفة)، لذا فإن
> الملف التنفيذي ووسائطه حقلان **منفصلان**. اكتب
> `command = "npx"`, `args = ["-y", "pkg"]` — **وليس** `command = "npx -y pkg"`.

### stdio (عملية فرعية محلية)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

يعمل الخادم الذي تشغّله بنفسك بالطريقة نفسها — وجّه `command`/`args` إليه:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### خادم يحتاج مفتاح API (context7)

يقدّم [Context7](https://context7.com) توثيق مكتبات محدّثًا. مرّر
المفتاح كوسيط حتى يبقيه `${VAR}` خارج الملف:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse (عن بُعد)

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **لا توجد ترويسات مخصّصة (بعد).** يرسل النقلان `http`/`sse` عنوان `url` فقط —
> ولا يستطيع Veles إرفاق ترويسة `Authorization`. بالنسبة لخادم بعيد يحتاج
> مفتاحًا، فضّل نسخته عبر `stdio` (مثل `npx`) مع وضع المفتاح في `args`/`env`، أو
> نقطة نهاية تقبل المفتاح في عنوان URL.

## إخفاء أدوات محدّدة

عيّن `[mcp] disabled_tools` — وهو جدول يربط كل خادم بأسماء الأدوات المراد تخطّيها:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## الموافقة والفحص والاختبار

```bash
veles mcp approve github    # review the recipe, type `yes` — the server may now start
veles mcp list              # every configured server: transport, approved, status, tool count
veles mcp test github       # connect to one server and list its tools
```

لا يبدأ الخادم إلا بعد أن توافق على وصفته (recipe) بالضبط. يعرض `veles mcp approve`
الجدول كاملًا — `command` و`args` وقيم `env` (فقيمة `PATH` هناك تحدّد أيّ ملف
تنفيذي يُشغَّل؛ وتظهر مراجع `${VAR}` كما كُتبت) و`url` و`transport` وأي مفتاح آخر —
ويسجّل تجزئة (hash) للجدول كما هو في `config.toml`، قبل توسيع `${VAR}`: فتدوير
الرمز المميّز يُبقي الموافقة، بينما أيّ تعديل على الجدول (مشروع مُستنسَخ، أو وسيط
غُيّر) يجعل الخادم `changed` ويمنعه من البدء حتى توافق عليه من جديد. تشمل الموافقة
سطر الأوامر؛ أمّا الملفات التي يشغّلها من المشروع (سكربت في `args`) فلا تُثبَّت —
راجعها هي أيضًا. تُحفظ الموافقات في `~/.veles/mcp-approvals.json`. ويعرض
`veles registry install` لامتداد MCP الوصفة نفسها في تأكيده ويوافق عليها؛ ويسحب
`veles registry uninstall` الموافقة.

يخرج `veles mcp list` دائمًا بالرمز 0 — فهو أداة فحص، وليس بوّابة صحّة؛ ولا يبدأ
أبدًا خادمًا غير موافَق عليه. يخرج `veles mcp test` بالرمز 1 عندما يكون الخادم غير
موافَق عليه أو يفشل الاتصال، وبالرمز 2 لاسم خادم غير معروف.

## كيف تظهر الأدوات

بمجرد التهيئة والموافقة، تُركّب الخوادم **تلقائيًا** عند تشغيل `veles run` التالي /
بدء TUI / بدء الخادم الخلفي — لا توجد راية منفصلة لـ "تفعيل MCP". ويُتخطّى الخادم
غير الموافَق عليه مع تحذير واحد لكل عملية. تدخل كل أداة السجل العادي باسم `mcp_<server>_<tool>`
ويستطيع الوكيل استدعاءها كأي أداة مدمجة. تُنقّى المخططات (حدود الاسم/الطول،
وإزالة محارف التحكّم) حتى لا يستطيع خادم غير موثوق الحقن في المُحَثّ (prompt).
تُربط تلميحات الأدوات بسلّم الثقة: الأدوات المدمّرة تؤكَّد دائمًا، والأدوات
للقراءة فقط تُنفَّذ دون مطالبة، وكل ما عداها يمرّ عبر تدفّق
[الثقة](security-and-permissions.md) المعتاد — امنح موافقة دائمة عبر
`veles trust set` إذا لم ترغب في أن تُسأل في كل مرة.

## معالجة الإخفاقات

الخادم الذي يفشل في الاتصال — `command` مفقود، أو `url` خاطئ، أو أي إدخال
غير صالح — يُسجَّل كتحذير ويُتخطّى. ولا يحجب أبدًا بدء التشغيل أو الوكيل.
أعد تشغيل `veles mcp list` لرؤية الحالة والخطأ.
