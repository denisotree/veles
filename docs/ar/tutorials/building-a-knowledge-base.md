# بناء قاعدة معرفة

> 🌐 **اللغات:** [English](../../en/tutorials/building-a-knowledge-base.md) · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · [日本語](../../ja/tutorials/building-a-knowledge-base.md) · [한국어](../../ko/tutorials/building-a-knowledge-base.md) · [Español](../../es/tutorials/building-a-knowledge-base.md) · [Français](../../fr/tutorials/building-a-knowledge-base.md) · [Italiano](../../it/tutorials/building-a-knowledge-base.md) · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · [Português (PT)](../../pt-PT/tutorials/building-a-knowledge-base.md) · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · **العربية** · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · [বাংলা](../../bn/tutorials/building-a-knowledge-base.md) · [Tiếng Việt](../../vi/tutorials/building-a-knowledge-base.md)

في هذا الدرس ستحوّل مشروع Veles إلى قاعدة معرفة حيّة: تستوعب بضعة
مصادر، وتدع Veles يكتب صفحات ويكي، وتطرح أسئلة، وتُدمج ما تعلّمته.
هذا هو سير عمل **LLM-Wiki** الافتراضي. نحو 15 دقيقة.

ينبغي أن تكون قد أنهيت [البدء](getting-started.md) أولًا.

## الفكرة

لمشروع Veles منطقتا محتوى:

- `sources/` — المادة الخام غير القابلة للتغيير التي تعطيها له (للقراءة فقط بالنسبة للوكيل).
- `wiki/` — معرفة الوكيل الخاصة المُولَّدة بواسطة LLM (المنطقة الوحيدة التي يكتب
  المحتوى فيها).

أنت تُغذّي المصادر؛ ويقطّرها Veles إلى صفحات ويكي مترابطة؛ وأنت تستعلم عن
الويكي باللغة الطبيعية. راجع [حزم البنية وLLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)
لمعرفة السبب.

## 1. استيعاب مصدر

يقرأ `veles add` ملفًا أو رابطًا ويكتب صفحة ويكي تلخّصه:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

ينتج كل `add` صفحةً تحت `wiki/` ويربطها داخل رسم الويكي البياني.

## 2. راقب نمو الويكي

انظر إلى ما كُتِب:

```bash
ls wiki/concepts wiki/entities wiki/sources
```

تتقاطع الصفحات في الإشارة إلى بعضها. ويحتفظ فهرس `wiki/INDEX.md` العامل عند الطلب
بخريطة يحمّلها الوكيل عند حاجته إليها (وليس تفريغًا متراصًا للسياق).

## 3. اطرح أسئلة

الآن استعلم عن قاعدة معرفتك باللغة الطبيعية:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

يبحث Veles في الويكي، ويقرأ الصفحات ذات الصلة، ويجيب — مرتكزًا على ما
استوعبته بدلًا من بيانات تدريبه وحدها.

للأخذ والرد التفاعلي، افعل الشيء ذاته في TUI (`veles tui`).

## 4. دمج الجلسات

مع عملك، تتراكم المحادثات. شغّل المنسّق (curator) لضغطها في
صفحات ويكي دائمة واستخلاص الدروس:

```bash
veles curate
```

يكتب هذا صفحات `wiki/sessions/` ويحدّث رؤى المشروع وقواعده.
ويفعل Veles ذلك تلقائيًا أيضًا مع مرور الوقت — راجع
[ذاكرة المشروع وحلقة التعلّم](../explanation/project-memory-and-learning-loop.md).

## 5. حافظ على صحة الويكي

مع الوقت تصبح الصفحات قديمة أو يتيمة. تجدها عملية `lint`:

```bash
veles run "lint"
```

(`ingest` و`query` و`lint` هي مهارات مرفقة مع بنية LLM-Wiki؛
تستدعيها بـ `veles run "<operation>"` أو تدع الوكيل يستدعيها.)

## ما الذي بنيته

قاعدة معرفة ذاتية التنظيم: مصادر تدخل، صفحات ويكي مترابطة تخرج، قابلة
للاستعلام باللغة الطبيعية، تزداد ترتيبًا مع دمج Veles لها. من هنا:

- **[إدارة المهارات والأدوات والوحدات](../how-to/manage-skills-and-tools.md)** —
  علّم Veles سير عمل قابلة لإعادة الاستخدام.
- **[التشغيل كبرنامج خفي](../how-to/run-as-daemon.md)** + **[توصيل تيليجرام](../how-to/connect-telegram.md)** —
  تحدّث إلى قاعدة معرفتك من هاتفك.
- **[مشاريع متعددة ومشاريع فرعية](../how-to/multi-project-and-subprojects.md)** —
  توسّع إلى قواعد معرفة عديدة.
