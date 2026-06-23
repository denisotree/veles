# حِزم التخطيط وLLM-Wiki

> 🌐 **اللغات:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · **العربية** · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

تُعرّف **حزمة التخطيط** كيفية تنظيم *محتوى المستخدم* في المشروع — أي
الأدلة الموجودة، وأيّها يجوز للوكيل الكتابة فيها، وأي العمليات يقدّمها.
الافتراضي هو **LLM-Wiki**. هذا خيار محتوى، **وليس** مبدأً أساسيًا
في Veles.

## ما هي حزمة التخطيط

حزمة التخطيط هي دليل يحوي بيانًا تعريفيًا `layout.toml` (بالإضافة إلى ملفات
مهارات وقوالب اختيارية). يصرّح البيان التعريفي بما يلي:

- **المناطق القابلة للكتابة** — الأدلة التي يجوز للوكيل كتابة المحتوى فيها
  (يُفرَض ذلك في كل عملية `write_file`).
- **المناطق للقراءة فقط** — المواد التي يقرؤها الوكيل لكنه لا يعدّلها أبدًا.
- **العمليات** — تدفقات عمل مُسمّاة، تُشحن كمهارات داخل الحزمة.
- **السقالة** (`[layout.scaffold]`) — ما ينشئه `veles init`: الأدلة
  وقالب `AGENTS.md` اختياري (يُستبدل `{name}`).
- **المحرّكات** (`[layout.engines]`) — أيّ آلية محتوى أساسية تُفعّلها
  الحزمة. يوجد اليوم محرّك واحد: `wiki`. بدونه، لا توجد أدوات ويكي،
  ولا استدعاء ويكي، ولا حقن INDEX في المشروع.
- **ملف السياق** (`context_file`) — ملف يُحقن في موجّه النظام
  الثابت للوكيل (يستخدم LLM-Wiki ملف `INDEX.md`).

## الحِزم المضمّنة

| الحزمة | ما ينتجه `veles init --layout <name>` |
|---|---|
| `llm-wiki` *(الافتراضي)* | [LLM-Wiki بأسلوب Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (للقراءة فقط)، `wiki/` (قابل لكتابة الوكيل)، `INDEX.md` محقون في الموجّه، مهارات `ingest`/`query`/`lint`، ومحرّك الويكي مفعّل. |
| `notes` | دليل مسطّح واحد `notes/` يكتب فيه الوكيل. لا توجد آلية ويكي. |
| `bare` | لا توجد سقالة محتوى على الإطلاق — لمستودعات الشيفرة والعمل الحر. الكتابة متساهلة داخل جذر المشروع (مع خضوعها لسلّم الثقة). |

## التخطيطات المخصّصة

ضع حزمة في `~/.veles/layouts/<name>/layout.toml` (عام للمستخدم) أو
في `<project>/.veles/layouts/<name>/` (محلي للمشروع؛ يحجب حِزم المستخدم
والحِزم المضمّنة التي تحمل الاسم نفسه)، ثم مرّر `veles init --layout <name>`. حزمة `notes`
المضمّنة هي المثال الأدنى الجاهز للنسخ. يمكنك أيضًا وصف الأعراف في
`AGENTS.md` — يَفرض التخطيط المناطق، ويوجّه AGENTS.md السلوك.

## ما **ليس** عليه

يحكم التخطيط **محتواك فقط**. أما ذاكرة Veles الخاصة بالمشروع —
`memory.db` بالإضافة إلى شجرة الأثر `.veles/memory/` (الرؤى، وملخصات
الجلسات، والمقترحات، وسجل عمليات النظام) — فهي على جانب النظام وتعمل
بشكل متطابق تحت أي تخطيط. لا يمسّ تبديل التخطيطات حلقة التعلّم
أو الجلسات أو السجلات أبدًا. راجع [البنية](architecture.md) و
[تخطيط المشروع](../reference/project-layout.md).
