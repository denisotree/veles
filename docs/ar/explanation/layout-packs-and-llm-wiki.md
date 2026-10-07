# حِزم التخطيط وLLM-Wiki

> 🌐 **اللغات:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · **العربية** · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

تُعرّف **حزمة التخطيط** كيفية تنظيم *محتوى المستخدم* في المشروع — أي
الأدلة الموجودة، وأيّها يجوز للوكيل الكتابة فيها، وأي العمليات يقدّمها.
الافتراضي هو **`bare`**، الذي لا يضيف إلى دليلك شيئًا سوى `.veles/` و
`AGENTS.md`. أما **LLM-Wiki** فهو خيار واحد من سجلّ الامتدادات، **وليس**
مبدأً أساسيًا في Veles.

## ما هي حزمة التخطيط

حزمة التخطيط هي دليل يحوي بيانًا تعريفيًا `layout.toml` (بالإضافة إلى ملفات
مهارات وقوالب اختيارية). يصرّح البيان التعريفي بما يلي:

- **المناطق القابلة للكتابة** — الأدلة التي يجوز للوكيل كتابة المحتوى فيها
  (يُفرَض ذلك في كل عملية `write_file`).
- **المناطق للقراءة فقط** — المواد التي يقرؤها الوكيل لكنه لا يعدّلها أبدًا.
- **العمليات** — تدفقات عمل مُسمّاة، تُشحن كمهارات داخل الحزمة.
- **السقالة** (`[layout.scaffold]`) — ما ينشئه `veles init`: الأدلة
  وقالب `AGENTS.md` اختياري (يُستبدل `{name}`).
- **المحرّكات** (`[layout.engines]`) — أيّ آلية محتوى تطلبها
  الحزمة. يوفّر المحرّك وحدة (وحدة `wiki` في السجلّ توفّر `wiki`).
  بدونه، لا توجد أدوات ويكي، ولا استدعاء ويكي، ولا حقن INDEX في المشروع.
- **ملف السياق** (`context_file`) — ملف يُحقن في موجّه النظام
  الثابت للوكيل (يستخدم LLM-Wiki ملف `INDEX.md`).

## الحِزم المتاحة

| الحزمة | المصدر | ما ينتجه `veles init --layout <name>` |
|---|---|---|
| `bare` *(الافتراضي)* | مضمّنة | لا توجد سقالة محتوى على الإطلاق — لمستودعات الشيفرة والعمل الحر. الكتابة متساهلة داخل جذر المشروع (مع خضوعها لسلّم الثقة). |
| `llm-wiki` | السجلّ (`public:official/llm-wiki`، وتجلب وحدة `wiki`) | [LLM-Wiki بأسلوب Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (خام، للقراءة فقط بالاتفاق — غير مفروض)، `wiki/` (قابل لكتابة الوكيل)، `INDEX.md` محقون في الموجّه، مهارات `ingest`/`query`/`lint`/`organize`/`structure_design`، ومحرّك الويكي مفعّل، مع `veles add` و`/wiki`. موجّه سلوكي يصرّح به التخطيط (`templates/behaviour.md`) يحمل انضباط sources/wiki وقواعد الترحيل/ترقيع السجل. |
| `notes` | السجلّ (`public:official/notes`) | دليل مسطّح واحد `notes/` يكتب فيه الوكيل. لا توجد آلية ويكي. |

يسأل `veles init` في الطرفية أيّ حزمة تريد استخدامها (المثبّتة وتلك الموجودة
في سجلّاتك)؛ واختيار حزمة غير مثبّتة يعرض تثبيتها.
`veles registry install llm-wiki` يثبّتها مسبقًا.

## المشاريع السابقة للإصدار 1.2.3

المشروع الذي لم يُثبَّت تخطيطه (مشروع `llm-wiki` بعد الترقية، أو مشروع بلا
مفتاح `layout` — وكلها كانت مشاريع ويكي) يفتح كالمعتاد. في الطرفية يعرض
`veles` و`veles run` تثبيت الحزمة (مع المحرّك الذي تحتاجه) بتأكيد واحد؛
وفي غير ذلك — الخدمة الخلفية، القنوات، الأوامر الأخرى — يطبع Veles أمر
التثبيت مرة واحدة ويعمل دون الويكي. لا يُمسّ أي شيء في `wiki/`.

## التخطيطات المخصّصة

ضع حزمة في `~/.veles/layouts/<name>/layout.toml` (عام للمستخدم) أو
في `<project>/.veles/layouts/<name>/` (محلي للمشروع؛ يحجب حِزم المستخدم
والحِزم المضمّنة التي تحمل الاسم نفسه)، ثم مرّر `veles init --layout <name>`. حزمة `notes`
في السجلّ هي مثال أدنى جاهز للنسخ. الحزمة التي تطلب محرّكًا لا توفّره أي وحدة
مثبّتة تحصل على عرض التثبيت نفسه. يمكنك أيضًا وصف الأعراف في
`AGENTS.md` — يَفرض التخطيط المناطق، ويوجّه AGENTS.md السلوك.

## ما **ليس** عليه

يحكم التخطيط **محتواك فقط**. أما ذاكرة Veles الخاصة بالمشروع —
`memory.db` بالإضافة إلى شجرة الأثر `.veles/memory/` (الرؤى، وملخصات
الجلسات، والمقترحات، وسجل عمليات النظام) — فهي على جانب النظام وتعمل
بشكل متطابق تحت أي تخطيط. لا يمسّ تبديل التخطيطات حلقة التعلّم
أو الجلسات أو السجلات أبدًا. راجع [البنية](architecture.md) و
[تخطيط المشروع](../reference/project-layout.md).
