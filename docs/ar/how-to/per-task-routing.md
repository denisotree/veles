# كيفية توجيه المهام إلى نماذج مختلفة

> 🌐 **اللغات:** [English](../../en/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · **العربية**

ليست Veles مقيّدة بنموذج واحد. يمكن لكل **مهمة** داخلية أن تستخدم
`provider:model` مختلفًا — نموذجًا رخيصًا لضغط السياق، ونموذجًا قويًّا
للوكيل الرئيسي، ونموذجًا بصريًّا للصور. هذا هو نظام *التوجيه المجمّع* (ensemble routing).

## أنواع المهام

| المهمة | تُستخدم لـ |
|---|---|
| `default` | حلقة الوكيل الرئيسية |
| `curator` | دمج الجلسة → الويكي |
| `compressor` | ضغط السياق بنافذة منزلقة |
| `insights` | استخلاص الرؤى بعد التشغيل |
| `skills` | تنفيذ المهارات |
| `advisor` | الفحص الذاتي `advisor_review` |
| `vision` | `image_describe` (عند توصيل محوّل بصري) |
| `embedding` | تشابه `veles skill dedup` |

## عرض التوجيه الحالي

```bash
veles route show
```

يطبع هذا الأمر `provider:model` المحلول لكل مهمة، إضافةً إلى وسم `source`
يبيّن أي طبقة قرّرته.

## تثبيت مهمة على نموذج

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

تكتب هذه الأوامر `[routing.tasks]` في `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## إعادة الضبط

```bash
veles route reset compressor   # إعادة مهمة واحدة إلى الافتراضي
veles route reset              # إعادة كل المهام إلى الافتراضي
```

## تلميحات بلغة طبيعية في AGENTS.md

يمكنك التعبير عن التوجيه بصيغة نثرية في `AGENTS.md` (مثلًا "استخدم نموذجًا رخيصًا
للضغط"). تحلّل Veles هذه التلميحات إلى ملف `routing.nl.toml` مُولَّد تلقائيًّا:

```bash
veles route refresh            # إعادة تحليل تلميحات AGENTS.md
veles route refresh --force    # حتى لو لم يتغيّر AGENTS.md
```

تتفوّق مدخلات `[routing.tasks]` الصريحة دائمًا على التلميحات بلغة طبيعية.

## ترتيب الحلّ

لكل مهمة، تفوز أول طبقة تُنتج مواصفة:

1. مشروع `[routing.tasks][task]`
2. مشروع `[routing.tasks].default`
3. تلميح مشروع بلغة طبيعية (`routing.nl.toml`)
4. أساس المشروع `[provider]`
5. مستخدم `[routing.tasks][task]` / `.default`
6. مستخدم `[user] default_provider` + `default_model`
7. الافتراضي المُدمَج لتلك المهمة

(تتخطّى `embedding` المُلتقِطات الشاملة — فنموذج الدردشة ليس نموذج تضمين.)
