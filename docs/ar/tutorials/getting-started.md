# البدء

> 🌐 **Languages:** **English** · [Русский](../../ru/tutorials/getting-started.md)

في هذا الدرس ستثبّت Veles، وتمنحه مفتاح API، وتنشئ مشروعك الأول،
وتشغّل موجِّهك الأول. نحو 10 دقائق. ستنتهي بمشروع Veles عامل يمكنك
التحدّث إليه.

## المتطلبات المسبقة

- **Python 3.13+** (يتطلب Veles `>=3.13`).
- مفتاح API لنموذج لغوي. سنستخدم **OpenRouter** (المزوّد الافتراضي)؛ ويعمل أيٌّ من
  [المزوّدين الآخرين](../reference/providers.md) أيضًا، بما في ذلك المزوّدون المحليون
  بالكامل دون مفتاح.

## 1. التثبيت

يُثبَّت Veles كأمر `veles` عام عبر [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

للتحديث لاحقًا: `uv tool upgrade veles-ai`.

## 2. امنح Veles مفتاح API

احصل على مفتاح من [openrouter.ai](https://openrouter.ai) وصدّره:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

يمكنك أيضًا تخزينه في سلسلة مفاتيح نظام التشغيل حتى لا تُعيد تصديره في كل صدفة:

```bash
veles secret set OPENROUTER_API_KEY
```

(تفضّل إعدادًا محليًا بالكامل دون مفتاح؟ ثبّت [Ollama](https://ollama.com)، ثم
`ollama pull qwen3:4b-instruct`، واستخدم `--provider ollama` أدناه.)

## 3. أنشئ مشروعك الأول

مشروع Veles هو مجرّد دليل به مجلّد حالة `.veles/`. أنشئ واحدًا:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

ينشئ هذا `AGENTS.md` (سياق مشروعك)، و`sources/` و`wiki/` (تخطيط
[LLM-Wiki الافتراضي](../explanation/layout-packs-and-llm-wiki.md))، و
`.veles/` (حالة الآلة). راجع [تخطيط المشروع](../reference/project-layout.md).

## 4. شغّل موجِّهك الأول

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

يحمّل Veles سياق مشروعك، ويستدعي النموذج، ويطبع الإجابة. ويُحفَظ
الدور في ذاكرة المشروع.

أضِف `--stream` لرؤية الرموز عند وصولها، أو `--verbose` لتقدّم كل دور:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. افتح حلقة REPL التفاعلية

لمحادثة متعددة الأدوار، افتح واجهة TUI:

```bash
veles tui
```

اكتب رسالة واضغط Enter. مفاتيح مفيدة: `Ctrl+D` للخروج، و`Shift+Tab` للتنقّل بين
[أوضاع التشغيل](../explanation/modes.md)، و`/help` لسرد أوامر الشرطة المائلة. القائمة
الكاملة في [مرجع TUI](../reference/tui.md).

## 6. اطّلع على ما يتذكّره Veles

يُحفَظ كل تشغيل. اسرد جلساتك وابحث فيها:

```bash
veles sessions list
veles sessions search "three sentences"
```

## إلى أين بعد ذلك

- **[بناء قاعدة معرفة](building-a-knowledge-base.md)** — استورِد المصادر
  إلى الويكي واطرح أسئلة عنها.
- **[تهيئة المزوّدين](../how-to/configure-providers.md)** — انتقل إلى
  Anthropic أو OpenAI أو Gemini أو نموذج محلي بالكامل.
- **[نظرة عامة على البنية](../explanation/architecture.md)** — افهم ما الذي
  يفعله Veles تحت الغطاء.
