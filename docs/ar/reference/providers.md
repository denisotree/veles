# المزوّدون

> 🌐 **اللغات:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · **العربية** · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles مستقل عن المزوّد. مرّر `--provider <id>` إلى أي أمر وكيل، أو اضبط
مزوّدًا افتراضيًا في الإعداد. تستخدم معرّفات النماذج تسمية المزوّد نفسه.

## كتالوج المزوّدين

كل مزوّد يعرفه Veles هو مُدخَل في كتالوج واحد، يُبنى من ثلاثة مصادر:

1. **المضمَّنة** — الجدول أدناه، ويُشحَن مع Veles.
2. **الخاصة بك** — `~/.veles/providers.toml`: واجهة API مستضافة متوافقة مع OpenAI
   أو خادم تشغّله بنفسك، بإضافة مُدخَل (راجع
   [إضافة مزوّد خاص بك](../how-to/configure-providers.md#إضافة-مزوّد-خاص-بك)).
   يتجاوز المُدخَل ذو المعرّف المضمَّن إعدادات ذلك المزوّد (مثل `base_url`).
3. **الوحدات** — تُسهم وحدة من السجلّ بمزوّد (`antigravity-cli`). تسميته في
   `[engine] provider` أو في مسار أو عبر `--provider` تثبّته من سجلّاتك المتصلة
   عند التشغيل التالي، كما تُثبَّت قناة مُعلَنة.

يقرأ كلٌّ من `--provider` و`veles models` ومعالجات الإعداد والتوجيه و`veles doctor`
الكتالوج، فيعمل مزوّد من أي مصدر في كل موضع يعمل فيه المزوّد المضمَّن. المعرّف
المجهول خطأ من سطر واحد يسرد ما هو موجود؛ كما يفحص `veles doctor` الملف
`~/.veles/providers.toml` وكل مزوّد تسمّيه مساراتك.

| المزوّد | النوع | مفتاح API | ملاحظات |
|---|---|---|---|
| `openrouter` | بوّابة سحابية | `OPENROUTER_API_KEY` | **الافتراضي.** يُمرِّر مئات النماذج؛ معرّفات النماذج مثل `anthropic/claude-sonnet-4.6` |
| `anthropic` | سحابي مباشر | `ANTHROPIC_API_KEY` | واجهة Claude Messages API، التخزين المؤقت للموجِّهات |
| `openai` | سحابي مباشر | `OPENAI_API_KEY` | إكمالات دردشة GPT |
| `gemini` | سحابي مباشر | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | مفوَّض CLI | — (جلسة CLI) | يفوّض إلى `claude` CLI محلي في وضع بثّ JSON |
| `codex` | مفوَّض CLI | — (جلسة CLI) | يفوّض إلى `codex` CLI محلي (اشتراك ChatGPT) |
| `ollama` | محلي | لا شيء | `OLLAMA_BASE_URL` (الافتراضي `http://localhost:11434/v1`) |
| `llamacpp` | محلي | لا شيء | `LLAMACPP_BASE_URL` (الافتراضي `http://localhost:8080/v1`) |
| `openai-compat` | محلي/مخصّص | اختياري `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL` (مطلوب، دون افتراضي) |

أُزيل `gemini-cli` في 1.2.6 — لم تعد Google تقدّم Gemini CLI للحسابات الشخصية.
استخدم `gemini` مع مفتاح API، أو وحدة `antigravity-cli`.

المزوّد الافتراضي: `openrouter`. **لا يوجد نموذج افتراضي مُضمَّن** — اضبط واحدًا
عبر معالج الإعداد أو `[engine] model` أو `--model` (وإلا أبلغ الوكيل
"no model configured"). ترث مسارات المهام `[engine]` كأساس لها ما لم يُتجاوز
ذلك في `[routing.tasks]` — راجع [التوجيه حسب المهمة](../how-to/per-task-routing.md).

## المزوّدون المحليون

لا يحتاج `ollama` و`llamacpp` و`openai-compat` إلى مفتاح API. اسرد النماذج المُثبَّتة
عبر `veles models <provider>` (دائمًا حيّة للمزوّدين المحليين).

**يُكتشَف استدعاء الأدوات** مما يعلنه الخادم: يُبلغ ollama بقدرات كل نموذج، ويُبلغ خادم
llama.cpp بقدرات قالب الدردشة لديه. يفرض `VELES_LOCAL_TOOLS=1` تفعيل استدعاء الأدوات
و`=0` تعطيله؛ وعند عدم الضبط يُكتشَف تلقائيًا.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

تجاوز نقاط النهاية عبر متغيّرات البيئة `*_BASE_URL` (راجع
[متغيّرات البيئة](environment-variables.md)).

## تفويض CLI (`claude-cli`, `codex`, `antigravity-cli`)

إذا كان لديك اشتراك في Claude أو ChatGPT أو Google، فيمكن لـ Veles تشغيل الـ CLI الخاص
به بلا واجهة والعمل كمنسّق — دون مفتاح API منفصل. `claude-cli` و`codex` مضمَّنان؛ أما
`antigravity-cli` (الـ CLI المسمّى `agy`) فهو وحدة من السجلّ تثبّت نفسها عند تسميتها.

المفوَّض هو النموذج فقط: تصل إليه أدوات Veles عبر جسر MCP، ويمرّ كل استدعاء عبر سلّم
الثقة في Veles. يقع إعداد الجسر في مجلد خاص بالعملية الجارية،
`.veles/tmp/delegate-<pid>/`، ويُحذف عند انتهائها. يعمل `agy` في مساحة عمل مؤقتة خارج
مشروعك (تحت `~/.veles/tmp/`)، فلا يصل إليه إعداد `.agents/` الخاص بالمشروع نفسه، خلف
بوّابة ترفض أدوات الصدفة والملفات الخاصة به.

يعمل `codex` أيضًا خارج مشروعك (تحت `~/.veles/tmp/`)، مع تجاهل إعداد codex الخاص بك
وتعطيل أدواته الخاصة — الصدفة وتحرير الملفات والصور والوكلاء الفرعيين والمتصفّح والبحث
في الويب؛ ويتحقق Veles من أسماء تلك الأعلام مرة واحدة لكل عملية ويرفض تشغيل codex أعاد
تسمية أحدها مما يعتمد عليه. يُمرَّر خادم MCP الخاص به في الوسائط، لا في ملف. وفي
`veles run`، يتبع codex بروتوكول أدوات Veles بموثوقية أقل من claude: فقد يجيب بأنه لا
يستطيع قراءة ملف دون أن يستدعي الأداة — أعد السؤال، أو سمِّ الأداة ("use read_file on …").

## حالة الوسائط المتعددة (الرؤية / تحويل الكلام إلى نص)

يُعرّف Veles بروتوكول `VisionAdapter` ومحوّل STT (`modules/vision.py`
و`modules/stt.py`) بالإضافة إلى سجلّ عام للعملية، **لكن لا يُشحَن أي محوّل ملموس
ولا يُسجَّل أي منها عند بدء تشغيل العفريت**. لذا فإن صورة أو رسالة صوتية تُرسَل إلى
قناة تُرجِع حاليًا إشعار "غير مُهيّأ" بدل أن تُحلَّل.
توجد مهمة التوجيه `vision` لِما إذا وُصِّل محوّل لاحقًا. راجع
[ربط Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## اختيار نموذج

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

لاستخدام نماذج مختلفة لمهام مختلفة (رخيص للضغط، قوي للتخطيط)،
راجع [التوجيه حسب المهمة](../how-to/per-task-routing.md).
