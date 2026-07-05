# المزوّدون

> 🌐 **اللغات:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · **العربية** · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles مستقل عن المزوّد. مرّر `--provider <name>` إلى أي أمر وكيل، أو اضبط
مزوّدًا افتراضيًا في الإعداد. تستخدم معرّفات النماذج تسمية المزوّد نفسه.

| المزوّد | النوع | مفتاح API | ملاحظات |
|---|---|---|---|
| `openrouter` | بوّابة سحابية | `OPENROUTER_API_KEY` | **الافتراضي.** يُمرِّر مئات النماذج؛ معرّفات النماذج مثل `anthropic/claude-sonnet-4.6` |
| `anthropic` | سحابي مباشر | `ANTHROPIC_API_KEY` | واجهة Claude Messages API، التخزين المؤقت للموجِّهات |
| `openai` | سحابي مباشر | `OPENAI_API_KEY` | إكمالات دردشة GPT |
| `gemini` | سحابي مباشر | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | عملية فرعية | — (جلسة CLI) | يفوّض إلى `claude` CLI محلي في وضع بثّ JSON |
| `gemini-cli` | عملية فرعية | — (جلسة CLI) | يفوّض إلى `gemini` CLI محلي |
| `ollama` | محلي | لا شيء | `OLLAMA_BASE_URL` (الافتراضي `http://localhost:11434/v1`) |
| `llamacpp` | محلي | لا شيء | `LLAMACPP_BASE_URL` (الافتراضي `http://localhost:8080/v1`) |
| `openai-compat` | محلي/مخصّص | لا شيء | `OPENAI_COMPAT_BASE_URL` (مطلوب، دون افتراضي) |

المزوّد الافتراضي: `openrouter`. **لا يوجد نموذج افتراضي مُضمَّن** — اضبط واحدًا
عبر معالج الإعداد أو `[engine] model` أو `--model` (وإلا أبلغ الوكيل
"no model configured"). ترث مسارات المهام `[engine]` كأساس لها ما لم يُتجاوز
ذلك في `[routing.tasks]` — راجع [التوجيه حسب المهمة](../how-to/per-task-routing.md).

## المزوّدون المحليون

لا يحتاج `ollama` و`llamacpp` و`openai-compat` إلى مفتاح API. اسرد النماذج المُثبَّتة
عبر `veles models <provider>` (دائمًا حيّة للمزوّدين المحليين).

**استدعاء الأدوات معطّل افتراضيًا** على المزوّدين المحليين — إذ تُصدِر كثير من النماذج
المحلية استدعاءات أدوات مشوَّهة. فعّله بعد اختيار نموذج قادر على استخدام الأدوات:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

تجاوز نقاط النهاية عبر متغيّرات البيئة `*_BASE_URL` (راجع
[متغيّرات البيئة](environment-variables.md)).

## تفويض CLI (`claude-cli`, `gemini-cli`)

إذا كان لديك اشتراك في Claude أو Gemini CLI، فيمكن لـ Veles تشغيل البرنامج
التنفيذي في وضع بثّ JSON والعمل كمنسّق — مع إبقاء الحلقة محلية أولًا دون
مفتاح API منفصل. لا تصل أدوات Veles إلى العملية الفرعية إلا عند تهيئة جسر MCP.

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
