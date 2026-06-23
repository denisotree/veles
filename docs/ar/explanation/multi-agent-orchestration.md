# التنسيق متعدد الوكلاء

> 🌐 **اللغات:** [English](../../en/explanation/multi-agent-orchestration.md) · [简体中文](../../zh-CN/explanation/multi-agent-orchestration.md) · [繁體中文](../../zh-TW/explanation/multi-agent-orchestration.md) · [日本語](../../ja/explanation/multi-agent-orchestration.md) · [한국어](../../ko/explanation/multi-agent-orchestration.md) · [Español](../../es/explanation/multi-agent-orchestration.md) · [Français](../../fr/explanation/multi-agent-orchestration.md) · [Italiano](../../it/explanation/multi-agent-orchestration.md) · [Português (BR)](../../pt-BR/explanation/multi-agent-orchestration.md) · [Português (PT)](../../pt-PT/explanation/multi-agent-orchestration.md) · [Русский](../../ru/explanation/multi-agent-orchestration.md) · **العربية** · [हिन्दी](../../hi/explanation/multi-agent-orchestration.md) · [বাংলা](../../bn/explanation/multi-agent-orchestration.md) · [Tiếng Việt](../../vi/explanation/multi-agent-orchestration.md)

للعمل المعقّد، يستطيع Veles تقسيم المهمة بين **مدير** ووكلاء
**عمّال** فرعيين متخصصين بدلًا من فعل كل شيء في سياق واحد. تشرح هذه الصفحة
النموذج؛ ولتفعيله، راجع
[وضع المدير](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt).

## الشكل

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- يخطّط **المدير** للتفكيك وينسّق — لكنه **لا**
  يكتب المُسلَّم النهائي بنفسه.
- يملك **العمّال** موجّهات نظام خاصة بالأدوار: يجمع `explorer`، ويُنتج `writer`
  الإجابة، ويراجع `advisor`. والمجموعة قابلة للتوسعة.
- في النهاية، يكتب المدير تقريرًا قصيرًا في الذاكرة.

## لا لعبة هاتف

قاعدة أساسية: تصل الآثار الوسيطة إلى المُركِّب **حرفيًا**، لا بصياغة
المدير. تُسلَّم نتائج المستكشف إلى الكاتب مباشرة، فلا
تُفقد التفاصيل عبر سلسلة من الملخّصات. هذا ما يجعل التفكيك
يضيف جودة بدلًا من أن يخفّفها.

## لماذا "المدير لا يكتب أبدًا"

لو كتب المنسّق الإجابة أيضًا، لانساق إلى اختصار طريق
العمّال وخسر فائدة التخصص. إبقاء التركيب في `writer`
مخصّص (يُغذّى بمدخلات حرفية) يفرض تقسيم العمل. ويجعل Veles من هذا
ضمانة زمن تشغيل.

## متى يفيد — ومتى لا

يؤتي التفكيك ثماره في المهام الواسعة أو المتعددة الأوجه (دقّق هذا المستودع،
ابحث في هذا السؤال من عدة زوايا). أما الطلب السريع ذو السياق الواحد فيُضيف
عبئًا فحسب — ولهذا فإن وضع المدير **اشتراكٌ صريح**، معطّل
افتراضيًا (`veles run --manager` أو `VELES_MANAGER_MODE=1`).
