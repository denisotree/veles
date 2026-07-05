# كيفية تهيئة المزوّدين

> 🌐 **اللغات:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · **العربية** · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

بدّل Veles بين OpenRouter و Anthropic و OpenAI و Gemini والنماذج المحلية أو اشتراك
CLI. قائمة المزوّدين الكاملة: [مرجع المزوّدين](../reference/providers.md).

## اختر مزوّدًا لكل أمر

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## اضبط افتراضيًا للمشروع

ضع أساسًا في `<project>/.veles/config.toml`:

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

أو افتراضيًا عامًا للمستخدم في `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## وفّر مفتاح API

يحتاج المزوّدون السحابيون إلى مفتاح. خزّنه مرة واحدة في سلسلة مفاتيح نظام التشغيل:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…أو صدّر [متغيّر البيئة](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

ترتيب البحث: سلسلة المفاتيح (نطاق المشروع) → سلسلة المفاتيح (الافتراضي) → متغيّر البيئة. لا تُكتَب المفاتيح
**أبدًا** في ملفات الإعداد.

## استخدم نموذجًا محليًا بالكامل (دون مفتاح)

ثبّت [Ollama](https://ollama.com)، واسحب نموذجًا، ووجّه Veles إليه:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

استدعاء الأدوات **معطّل افتراضيًا** على المزوّدين المحليين. فعّله بعد
اختيار نموذج قادر على استخدام الأدوات:

```bash
export VELES_LOCAL_TOOLS=1
```

تجاوز نقاط النهاية إذا لم يكن خادمك على المنفذ الافتراضي:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## التفويض إلى اشتراك Claude / Gemini CLI

إذا كان لديك `claude` أو `gemini` CLI مُصادَقًا عليه، فيمكن لـ Veles تشغيله:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

لا حاجة إلى مفتاح API — تتولّى الـ CLI المصادقة.

## اسرد النماذج المتاحة

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## التالي

- [وجّه مهامًا مختلفة إلى نماذج مختلفة](per-task-routing.md) — نموذج رخيص
  للضغط، ونموذج قوي للتخطيط.
