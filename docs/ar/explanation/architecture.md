# نظرة عامة على البنية

> 🌐 **اللغات:** [English](../../en/explanation/architecture.md) · [简体中文](../../zh-CN/explanation/architecture.md) · [繁體中文](../../zh-TW/explanation/architecture.md) · [日本語](../../ja/explanation/architecture.md) · [한국어](../../ko/explanation/architecture.md) · [Español](../../es/explanation/architecture.md) · [Français](../../fr/explanation/architecture.md) · [Italiano](../../it/explanation/architecture.md) · [Português (BR)](../../pt-BR/explanation/architecture.md) · [Português (PT)](../../pt-PT/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md) · **العربية** · [हिन्दी](../../hi/explanation/architecture.md) · [বাংলা](../../bn/explanation/architecture.md) · [Tiếng Việt](../../vi/explanation/architecture.md)

تشرح هذه الصفحة *ماهية* Veles وكيف تتلاءم أجزاؤه معًا، حتى تصبح بقية
الوثائق مفهومة. للاطلاع على رؤية المنتج المرجعية، راجع `VISION.md` في
جذر المستودع.

## القصد التصميمي

صُمم Veles عن قصد ليكون **بسيطًا وذا تفكيك نظيف** — وحدات بمسؤولية
واحدة، دون ملفات عملاقة. وهو **يعمل محليًا أولًا**: تشغّله على دليل في
جهازك، فيحتفظ بذاكرته المنظّمة الخاصة هناك.

## الركائز الخمس (النواة)

كل شيء في النواة يخدم واحدة من خمس وظائف:

1. **ذاكرة المشروع** — أثرٌ منظّم (منفصل عن محتواك) يحتوي على
   سجل الجلسات، والقواعد/الرؤى المتعلَّمة، وخريطة ملفات المشروع، وسجلات
   المهارات/الأدوات مع القياسات. راجع [ذاكرة المشروع وحلقة التعلّم](project-memory-and-learning-loop.md).
2. **حلقة التعلّم** — المنسّق، ومستخلص الرؤى، والحلم (dreaming) التي تُبقي
   الذاكرة طازجة وتحوّل الخبرة إلى قواعد قابلة لإعادة الاستخدام.
3. **تنسيق متعدد الوكلاء** — مدير يفكّك المهمة ويطلق عمّالًا
   متخصصين. راجع [التنسيق متعدد الوكلاء](multi-agent-orchestration.md).
4. **بروتوكول مزوّد** — واجهة واحدة فوق العديد من خلفيات نماذج LLM (السحابة، المحلية،
   تفويض CLI). راجع [المزوّدون](../reference/providers.md).
5. **أدوات ومهارات مصغّرة** — مجموعة إقلاع صغيرة **تتراكم** كلما كتب Veles
   أدواته الخاصة وصاغ العمليات المتكررة في مهارات. راجع
   [المهارات والأدوات](skills-and-tools.md).

## كل شيء آخر هو وحدة اختيارية

البوابات/القنوات، والخادم الخفي (daemon)، والمجدول، وواجهة TUI، والرؤية/تحويل الكلام إلى نص — كلها
**قابلة للتوصيل** وتُحمَّل فقط عند الاستخدام. يُقلع Veles بالحد الأدنى ويتوسّع حسب
الطلب، حتى يبقى أمر `veles run` البسيط بسيطًا.

## كيف يجري دور واحد

```
your prompt
   │
   ▼
context: AGENTS.md (small) + on-demand recall from project memory
   │
   ▼
agent loop  ──►  provider (routed per task)  ──►  tool calls
   │                                               │
   │            (trust ladder gates sensitive tools)
   ▼
response  ──►  saved to memory  ──►  learning triggers (insights, curator)
```

يُبقى ملف السياق (`AGENTS.md`) صغيرًا عن قصد؛ أما المعرفة المساعدة
(صفحات الويكي، خريطة ملفات المشروع، الأدوار السابقة ذات الصلة) فتُسحب **عند
الطلب** بدلًا من إغراق السياق بها مسبقًا.

## أين تعيش الحالة

- `<project>/.veles/` — ذاكرة هذا المشروع، وإعداداته، ومهاراته/أدواته المحلية.
- `~/.veles/` — الإعداد العام للمستخدم، والمهارات/الأدوات العابرة للمشاريع، والذاكرات المؤقتة، والثقة.
- `<project>/AGENTS.md`, `wiki/`, `sources/` — محتواك (تخطيط LLM-Wiki).

راجع [تخطيط المشروع](../reference/project-layout.md).

## تعدد المشاريع في حلقة واحدة

تخدم حلقة وكيل واحدة مشاريع عديدة. يحصل كل مشروع على دليله الخاص مع
سياقه وذاكرته الخاصين؛ ويُربط `AGENTS.md` رمزيًا بـ `CLAUDE.md`/`GEMINI.md` بحيث
تَرى أيُّ واجهة CLI خارجية تُطلق هناك السياقَ نفسه. راجع
[المشاريع المتعددة](../how-to/multi-project-and-subprojects.md).

## الواجهات

- **CLI** (`veles run`, `veles add`, …) — الاستخدام لمرة واحدة والمؤتمت بالبرمجة.
- **TUI** (`veles tui`) — حلقة REPL تفاعلية مع [أوضاع التشغيل](modes.md).
- **الخادم الخفي + القنوات** — واجهة برمجية بلا رأس، وTelegram، ومهام مجدولة.

تقود الواجهات الثلاث جميعها حلقة الوكيل الأساسية نفسها.
