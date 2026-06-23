# كيفية توجيه المهام إلى نماذج مختلفة

> 🌐 **اللغات:** [English](../../en/how-to/per-task-routing.md) · [简体中文](../../zh-CN/how-to/per-task-routing.md) · [繁體中文](../../zh-TW/how-to/per-task-routing.md) · [日本語](../../ja/how-to/per-task-routing.md) · [한국어](../../ko/how-to/per-task-routing.md) · [Español](../../es/how-to/per-task-routing.md) · [Français](../../fr/how-to/per-task-routing.md) · [Italiano](../../it/how-to/per-task-routing.md) · [Português (BR)](../../pt-BR/how-to/per-task-routing.md) · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · **العربية** · [हिन्दी](../../hi/how-to/per-task-routing.md) · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

Veles غير مقيَّد بنموذج واحد. يمكن لكل **مهمة** داخلية استخدام
`provider:model` مختلف — نموذج رخيص لضغط السياق، وآخر قوي للوكيل
الرئيسي، ونموذج رؤية للصور. هذا هو نظام *توجيه التجميع*.

## أنواع المهام

| المهمة | تُستخدم لـ |
|---|---|
| `default` | حلقة الوكيل الرئيسية |
| `curator` | دمج الجلسة ← الويكي |
| `compressor` | ضغط السياق بنافذة منزلقة |
| `insights` | استخراج الرؤى بعد التشغيل |
| `skills` | تنفيذ المهارات |
| `advisor` | الفحص الذاتي `advisor_review` |
| `vision` | `image_describe` (عند توصيل محوّل رؤية) |
| `embedding` | تشابه `veles skill dedup` |

## اطّلع على التوجيه الحالي

```bash
veles route show
```

يطبع هذا `provider:model` المُحلَّل لكل مهمة وعلامة `source`
تبيّن أي طبقة قرّرته.

## ثبّت مهمة على نموذج

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

تكتب هذه `[routing.tasks]` في `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## إعادة التعيين

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## تلميحات اللغة الطبيعية في AGENTS.md

يمكنك التعبير عن التوجيه نثرًا في `AGENTS.md` (مثل "استخدم نموذجًا رخيصًا
للضغط"). يحلّل Veles هذه التلميحات إلى ملف `routing.nl.toml` مُولَّد تلقائيًا:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

تفوز إدخالات `[routing.tasks]` الصريحة دائمًا على تلميحات اللغة الطبيعية.

## ترتيب الحلّ

لكل مهمة، تفوز أول طبقة تُنتج مواصفة:

1. `[routing.tasks][task]` على مستوى المشروع
2. `[routing.tasks].default` على مستوى المشروع
3. تلميح اللغة الطبيعية على مستوى المشروع (`routing.nl.toml`)
4. أساس `[provider]` على مستوى المشروع
5. `[routing.tasks][task]` / `.default` على مستوى المستخدم
6. `[user] default_provider` + `default_model` على مستوى المستخدم

إذا لم يَحُلَّ أيٌّ من هذه، فلا يوجد **بديل احتياطي مُضمَّن** — تُترَك المهمة
غير محدَّدة ويتدهور مستدعيها (يتخطّى الميزة) أو يُخطئ بوضوح، بدل أن
يلجأ بصمت إلى نموذج سحابي.

(تتخطّى `embedding` خيارات الالتقاط الشامل — فنموذج الدردشة ليس نموذج تضمين — لذا
لا يجيب عنها إلا `[routing.tasks].embedding` صريح.)
