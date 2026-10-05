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

**يُكتشَف** استدعاء الأدوات مما يعلنه الخادم. افرضه بـ
`VELES_LOCAL_TOOLS=1` (أو عطّله بـ `=0`).

تجاوز نقاط النهاية إذا لم يكن خادمك على المنفذ الافتراضي:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## إضافة مزوّد خاص بك

يصبح أي API مستضاف متوافق مع OpenAI، أو خادم تشغّله بنفسك، مزوّدًا بمُدخَل في
`~/.veles/providers.toml` — دون كتابة شيفرة. المعرّف هو اسم الجدول:

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

ثم استخدمه كأي مزوّد مضمَّن:

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| المفتاح | المعنى |
|---|---|
| `kind` | `openai-api` (واجهة API مستضافة) أو `local` (خادم تشغّله بنفسك) |
| `base_url` | نقطة النهاية المتوافقة مع OpenAI، وتنتهي بـ `/v1` (أو ما يعادلها لدى المزوّد) |
| `base_url_env` | متغيّر بيئة يتجاوز `base_url` عند ضبطه |
| `key_env` | أسماء متغيّرات البيئة التي يُقرأ منها المفتاح؛ تُجرَّب سلسلة المفاتيح أولًا |
| `label`, `tagline` | كيف تعرضه المعالجات |
| `tools` | `auto` (الافتراضي) أو `on` أو `off` — هل يتلقى النموذج استدعاءات الأدوات |

يغيّر المُدخَل ذو المعرّف المضمَّن (`[providers.ollama]`) إعدادات ذلك المزوّد —
مثل `base_url` — لكنه لا يغيّر نوعه. يُبلَّغ عن الملف التالف مرة واحدة، ويتابع Veles
بالمزوّدين المضمَّنين؛ ويسرد `veles doctor` ما فيه من خلل.

نقاط انطلاق لواجهات API الشائعة — **لم يتحقق منها فريق Veles**، فراجع وثائق
المزوّد لمعرفة نقطة النهاية الحالية:

| المعرّف | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## التفويض إلى اشتراك Claude / Google

إذا كان لديك `claude` CLI مُصادَقًا عليه، فيمكن لـ Veles تشغيله:

```bash
veles run --provider claude-cli "..."
```

لاشتراك Google، ثبّت Antigravity CLI (`agy`) وسجّل الدخول إليه مرة واحدة، ثم سمِّ
مزوّده — تثبّت وحدة `antigravity-cli` نفسها من سجلّاتك المتصلة عند ذلك التشغيل:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
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
