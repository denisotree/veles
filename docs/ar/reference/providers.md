# المزوّدون

> 🌐 **اللغات:** [English](../../en/reference/providers.md) · [Русский](../../ru/reference/providers.md)

Veles محايد تجاه المزوّد. مرّر `--provider <name>` لأي أمر وكيل، أو اضبط
افتراضيًا في الإعدادات. تستخدم معرّفات النماذج تسمية المزوّد الخاصة به.

| المزوّد | النوع | مفتاح API | ملاحظات |
|---|---|---|---|
| `openrouter` | بوابة سحابية | `OPENROUTER_API_KEY` | **الافتراضي.** يمرّر مئات النماذج؛ معرّفات النماذج مثل `anthropic/claude-sonnet-4.6` |
| `anthropic` | سحابي مباشر | `ANTHROPIC_API_KEY` | Claude Messages API، التخزين المؤقت للموجّهات |
| `openai` | سحابي مباشر | `OPENAI_API_KEY` | إكمالات محادثة GPT |
| `gemini` | سحابي مباشر | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | عملية فرعية | — (جلسة CLI) | يفوّض إلى `claude` CLI محلي في وضع تدفّق JSON |
| `gemini-cli` | عملية فرعية | — (جلسة CLI) | يفوّض إلى `gemini` CLI محلي |
| `ollama` | محلي | لا شيء | `OLLAMA_BASE_URL` (الافتراضي `http://localhost:11434/v1`) |
| `llamacpp` | محلي | لا شيء | `LLAMACPP_BASE_URL` (الافتراضي `http://localhost:8080/v1`) |
| `openai-compat` | محلي/مخصّص | لا شيء | `OPENAI_COMPAT_BASE_URL` (مطلوب، بلا افتراضي) |

الافتراضات: المزوّد `openrouter`، النموذج `anthropic/claude-sonnet-4.6`، الضاغط
`anthropic/claude-haiku-4.5`.

## المزوّدون المحليون

لا يحتاج `ollama` و`llamacpp` و`openai-compat` إلى مفتاح API. اسرد النماذج المثبَّتة
بـ `veles models <provider>` (حيّة دائمًا للمزوّدين المحليين).

**استدعاء الأدوات مُعطَّل افتراضيًا** على المزوّدين المحليين — إذ تُصدر العديد من
النماذج المحلية استدعاءات أدوات مشوّهة. فعّله بمجرد اختيارك نموذجًا قادرًا على الأدوات:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

تجاوَز نقاط النهاية بمتغيّرات البيئة `*_BASE_URL` (راجع
[متغيّرات البيئة](environment-variables.md)).

## تفويض CLI (`claude-cli`، `gemini-cli`)

إذا كان لديك اشتراك في Claude أو Gemini CLI، يمكن لـ Veles تشغيل الملف التنفيذي
في وضع تدفّق JSON والعمل كمنسّق — مع إبقاء الحلقة محلية أولًا دون
مفتاح API منفصل. ولا تصل أدوات Veles إلى العملية الفرعية إلا عند تهيئة جسر MCP.

## حالة الوسائط المتعددة (الرؤية / تحويل الكلام إلى نص)

يعرّف Veles `VisionAdapter` وبروتوكول محوّل STT (`modules/vision.py`،
`modules/stt.py`) بالإضافة إلى سجل عمومي على مستوى العملية، **لكن لا يُشحَن أي محوّل
محدد ولا يسجّل شيء واحدًا عند بدء البرنامج الخفي (daemon)**. لذلك فإن صورة أو رسالة
صوتية تُرسَل إلى قناة تُعيد حاليًا إشعار "غير مهيّأ" بدلًا من تحليلها.
وتوجد مهمة التوجيه `vision` لحين توصيل محوّل. راجع
[توصيل تيليجرام](../how-to/connect-telegram.md#multimodal-limitation).

## اختيار نموذج

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

لاستخدام نماذج مختلفة لمهام مختلفة (رخيص للضغط، قوي للتخطيط)،
راجع [التوجيه لكل مهمة](../how-to/per-task-routing.md).
