# كيفية تهيئة المزوّدين

> 🌐 **اللغات:** [English](../../en/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · **العربية**

بدّل Veles بين OpenRouter، وAnthropic، وOpenAI، وGemini، والنماذج المحلية، أو اشتراك في
أداة CLI. قائمة المزوّدين الكاملة: [مرجع المزوّدين](../reference/providers.md).

## اختيار مزوّد لكل أمر

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## تعيين مزوّد افتراضي للمشروع

ضع قاعدة في `<project>/.veles/config.toml`:

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
```

أو افتراضيًا عامًا على مستوى المستخدم في `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## توفير مفتاح الـ API

المزوّدون السحابيون يحتاجون مفتاحًا. خزّنه مرة واحدة في سلسلة مفاتيح نظام التشغيل:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…أو صدّر [متغيّر البيئة](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

ترتيب البحث: سلسلة المفاتيح (نطاق المشروع) ← سلسلة المفاتيح (الافتراضية) ← متغيّر البيئة. المفاتيح
**لا** تُكتب أبدًا في ملفات التهيئة.

## استخدام نموذج محلي بالكامل (بدون مفتاح)

ثبّت [Ollama](https://ollama.com)، واسحب نموذجًا، ووجّه Veles إليه:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

استدعاء الأدوات **معطّل افتراضيًا** على المزوّدين المحليين. فعّله بعد أن
تختار نموذجًا قادرًا على استخدام الأدوات:

```bash
export VELES_LOCAL_TOOLS=1
```

تجاوز نقاط النهاية إذا لم يكن خادمك على المنفذ الافتراضي:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## التفويض إلى اشتراك CLI الخاص بـ Claude / Gemini

إذا كانت أداة `claude` أو `gemini` لديك مصادَقًا عليها، يمكن لـ Veles تشغيلها:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

لا حاجة لمفتاح API — تتولّى أداة CLI المصادقة.

## سرد النماذج المتاحة

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## التالي

- [توجيه مهام مختلفة إلى نماذج مختلفة](per-task-routing.md) — نموذج رخيص
  للضغط، ونموذج قوي للتخطيط.
