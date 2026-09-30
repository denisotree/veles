# كيفية إدارة المهارات والأدوات والوحدات

> 🌐 **اللغات:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · **العربية** · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

يراكم Veles القدرات مع مرور الوقت. **المهارات** هي سير عمل قابلة لإعادة الاستخدام،
و**الأدوات** هي إجراءات قابلة للتنفيذ، و**الوحدات** إضافات اختيارية. يعيش كلٌّ منها على
نطاقين: محلي للمشروع (`<project>/.veles/`) وعام على مستوى المستخدم (`~/.veles/`). للاطلاع على
المفاهيم، انظر [المهارات والأدوات](../explanation/skills-and-tools.md).

## المهارات

المهارة هي ملف `SKILL.md` (بيانات أوّلية في المقدّمة + نص المُحَثّ) يستطيع الوكيل استدعاءها كأداة.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### الترقية / التخفيض بين النطاقات

المهارة التي تثبت فائدتها في مشروع واحد يمكن نقلها إلى نطاق المستخدم حتى يراها كل
مشروع (أو العكس):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### العثور على التكرارات ومرشّحي الترقية

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## الأدوات

تُفهرس الأدوات في ملف `memory.db` الخاص بالمشروع مع قياس استخدامها. يستطيع Veles
كتابة أدواته الخاصة أثناء عمله؛ وتديرها أنت عبر:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

الأدوات الحسّاسة (`run_shell`، و`write_file`، و`fetch_url`، …) يحكمها
[سلّم الثقة](security-and-permissions.md).

## الوحدات

الوحدة شيفرة Python (`module.toml` + نقطة دخول) تعمل داخل Veles — وتضيف قدرات
اختيارية (مزوّدو الذاكرة، والتضمينات، والرؤية، وتحويل الكلام إلى نص) دون تضخيم
النواة. يتطلّب تثبيت أيٍّ منها تأكيدًا افتراضيًا، ولا تُحمَّل في كل تشغيل إلا ما دامت
ملفاتها ما تزال مطابقة لما وافقت عليه (انظر [إبقاء التثبيتات
موثوقة](../../en/how-to/extension-registries.md#keep-installs-honest)).

```bash
veles module list                              # both scopes, with a `scope` column
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # install to ~/.veles/modules/, all projects
veles module show <name> [--user]
veles module remove <name> [--user]
veles module approve <name> [--user]
```

تعيش الوحدات في نطاقين، كالمهارات والأدوات: محلّي بالمشروع
(`<project>/.veles/modules/`) وعامّ بالمستخدم (`~/.veles/modules/`، يُحمَّل في كل
مشروع). تمرّ وحدة المستخدم عبر بوّابة الموافقة نفسها التي تمرّ بها وحدة المشروع،
وتعمل البوّابة قبل مقارنة الأسماء. إذا تشارك وحدة مشروع ووحدة مستخدم الاسم نفسه،
تُحمَّل وحدة المشروع الموافَق عليها ويحذّر Veles من أن وحدة المستخدم صارت محجوبة؛
أمّا وحدة المشروع غير الموافَق عليها فتُتخطّى (ويذكر التحذير دليلها) وتُحمَّل وحدة
المستخدم. وإذا تشارك وحدتان موافَق عليهما في النطاق نفسه الاسم — تُحمَّل الأولى
(بترتيب الدليل) وتحذّر البقية وتُتخطّى. تقبل `veles module {show,approve,remove}`
اسم البيان (manifest) (ما يعرضه `list`) وترفض اسمًا يعلنه أكثر من دليل في النطاق
وتسرد تلك الأدلة؛ ويرفض `veles module add` تثبيت وحدة يعلن دليل آخر في النطاق
اسمها مسبقًا.

### كتابة وحدة تضيف مزوّد ذاكرة

يمكن لنقطة الدخول `register(api)` في الوحدة أن تستدعي
`api.add_memory_provider(name, factory)` لتوصيل مصدر ذاكرة خارجي بالاستدعاء
(recall). يجب أن يطابق `name` قسم `[memory.external.<name>]` في
`~/.veles/config.toml`؛ وتُستدعى `factory` بذلك القسم (`dict`) ويجب أن تُرجع كائنًا
ينفّذ بروتوكول `MemoryProvider` في Veles (`veles.core.memory.provider`)، أو `None`
لتخطّي المزوّد:

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

المزوّد الذي ينفّذ أيضًا `ingest(title, body, *, insight_id) ->
bool` (بروتوكول `IngestingMemoryProvider`) يتلقّى كتابات Veles كذلك، لا القراءات
فقط. إذا سجّلت وحدتان اسم المزوّد نفسه، يفشل تحميل الثانية — فتُتخطّى مع تحذير،
ولا يبقى شيء مسجَّلًا جزئيًّا. والقسم المهيّأ في `config.toml` الذي لم تُثبَّت وحدته
يطبع تحذيرًا واحدًا مع أمر التثبيت؛ ويستمر الاستدعاء (recall) في العمل بدونه.

يضم السجلّ Honcho وMem0 وSupermemory كوحدات مزوّدين جاهزة — ثبّتها بـ
`veles registry install --user {honcho,mem0,supermemory}`، ثم شغّل أمر
`uv tool install veles-ai --with '<package>'` الذي يطبعه التثبيت (تعلن كل وحدة عن
SDK — `mem0ai>=2.0` و`honcho-ai>=2.5` و`supermemory>=3.62` — لا يثبّته Veles عنك
أبدًا)، واملأ القسم المطابق `[memory.external.<name>]`:

- **mem0**: `api_key` و`user_id` و`agent_id` اختياري (ليستدعي كذلك ذكريات ذلك
  الوكيل) و`host`. تتبّع SDK (telemetry) معطَّل افتراضيًا؛ وكل استدعاء يُجري طلب
  `GET /v1/ping/` إضافيًا واحدًا.
- **supermemory**: `api_key` و`user_id` اختياري (يُرسل بوصفه `container_tag` للبحث)
  و`base_url`.
- **honcho**: `api_key` و`workspace_id` و`peer_id` اختياري (للبحث في رسائل ذلك
  النظير فقط) و`base_url`. يُجري كل استدعاء get-or-create لمساحة العمل — فينشئ
  `workspace_id` إن لم تكن موجودة.

## اكتشف المزيد

ابحث في السجلّات المتصلة:

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```
