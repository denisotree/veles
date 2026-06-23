# كيفية العمل مع مشاريع متعددة ومشاريع فرعية

> 🌐 **اللغات:** [English](../../en/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · **العربية**

يشغّل Veles مشاريع كثيرة في حلقة وكيل واحدة. لكل مشروع ذاكرته
ومهاراته وأدواته الخاصة. **المشاريع الفرعية** مشاريع متداخلة تحت مشروع أب — وهي مفيدة في
تفكيك مستودع أحادي كبير أو قاعدة معرفة إلى ذاكرات مُحدَّدة النطاق.

## المشاريع

يكتشف Veles المشروع النشط بالصعود من مجلّد عملك الحالي حتى يصل إلى مجلّد `.veles/`
(مثل `git`). أدِر السجل:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

يطبع `switch` مسارًا، حتى تتمكّن من الانتقال `cd` إلى مشروع:

```bash
cd "$(veles project switch web)"
```

شغّل أمرًا على مشروع في مكان آخر دون `cd`:

```bash
veles run --project-root /path/to/project "..."
```

## المشاريع الفرعية

المشروع الفرعي هو مشروع Veles ابن داخل مشروع أب. أنشئ واحدًا:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### دع Veles يقترح تقسيمًا

عندما تنمو ويكي مشروع ما، يستطيع Veles رصد التجمّعات الموضوعية واقتراحها
كمشاريع فرعية:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## متى تستخدم أيًّا منها

- **مشاريع منفصلة** — قواعد معرفة / قواعد شيفرة غير مرتبطة.
- **مشاريع فرعية** — أجزاء من شيء أكبر واحد تستفيد من ذاكرة مُحدَّدة النطاق لكنها
  تشترك في سياق أب.

انظر [البنية المعمارية](../explanation/architecture.md) لمعرفة كيف يُحمَّل سياق
المشاريع المتعددة عند الطلب بدلًا من تفريغ أحادي ضخم واحد.
