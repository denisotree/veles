# البدء

> 🌐 **اللغات:** [English](../../en/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md)

في هذا الدرس ستثبّت Veles، وتمنحه مفتاح API، وتنشئ مشروعك الأول،
وتشغّل موجّهك الأول. نحو 10 دقائق. ستنتهي بمشروع Veles عامل
يمكنك التحدّث إليه.

## المتطلبات المسبقة

- **Python 3.13+** (يتطلّب Veles الإصدار `>=3.13`).
- مفتاح API لنموذج LLM. سنستخدم **OpenRouter** (المزوّد الافتراضي)؛ ويعمل أي من
  [المزوّدين الآخرين](../reference/providers.md) كذلك، بما في ذلك المزوّدون
  المحليون بالكامل بلا مفتاح.

## 1. التثبيت

يُثبَّت Veles كأمر عمومي `veles` عبر [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

للتحديث لاحقًا: `uv tool install . --reinstall`.

## 2. امنح Veles مفتاح API

احصل على مفتاح من [openrouter.ai](https://openrouter.ai) وصدّره:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

يمكنك أيضًا تخزينه في سلسلة مفاتيح نظام التشغيل حتى لا تعيد تصديره في كل صدفة:

```bash
veles secret set OPENROUTER_API_KEY
```

(تفضّل إعدادًا محليًا بالكامل بلا مفتاح؟ ثبّت [Ollama](https://ollama.com)،
ثم `ollama pull qwen3:4b-instruct`، واستخدم `--provider ollama` أدناه.)

## 3. أنشئ مشروعك الأول

مشروع Veles هو مجرد دليل يحتوي مجلد حالة `.veles/`. أنشئ واحدًا:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

ينشئ هذا `AGENTS.md` (سياق مشروعك)، و`sources/` و`wiki/`
([بنية LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) الافتراضية)، و
`.veles/` (حالة آلية). راجع [بنية المشروع](../reference/project-layout.md).

## 4. شغّل موجّهك الأول

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

يحمّل Veles سياق مشروعك، ويستدعي النموذج، ويطبع الإجابة. ويُحفَظ
الدور في ذاكرة المشروع.

أضف `--stream` لرؤية الرموز فور وصولها، أو `--verbose` للتقدّم لكل دور:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. افتح واجهة REPL التفاعلية

لمحادثة متعدّدة الأدوار، افتح TUI:

```bash
veles tui
```

اكتب رسالة واضغط Enter. مفاتيح مفيدة: `Ctrl+D` للخروج، و`Shift+Tab` لتدوير
[أوضاع التشغيل](../explanation/modes.md)، و`/help` لسرد أوامر الشرطة المائلة.
القائمة الكاملة في [مرجع TUI](../reference/tui.md).

## 6. اطّلع على ما يتذكّره Veles

يُحفَظ كل تشغيل. اسرد جلساتك وابحث فيها:

```bash
veles sessions list
veles sessions search "three sentences"
```

## إلى أين تذهب بعد ذلك

- **[بناء قاعدة معرفة](building-a-knowledge-base.md)** — استوعب المصادر
  في الويكي واطرح أسئلة عنها.
- **[تهيئة المزوّدين](../how-to/configure-providers.md)** — انتقل إلى
  Anthropic أو OpenAI أو Gemini أو نموذج محلي بالكامل.
- **[نظرة عامة على البنية المعمارية](../explanation/architecture.md)** — افهم ما
  يفعله Veles تحت الغطاء.
