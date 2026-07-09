# متغيّرات البيئة

> 🌐 **اللغات:** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · [繁體中文](../../zh-TW/reference/environment-variables.md) · [日本語](../../ja/reference/environment-variables.md) · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · **العربية** · [हिन्दी](../../hi/reference/environment-variables.md) · [বাংলা](../../bn/reference/environment-variables.md) · [Tiếng Việt](../../vi/reference/environment-variables.md)

يقرأ Veles هذه المتغيّرات وقت التشغيل. يُفضَّل تخزين مفاتيح API والرموز في سلسلة
مفاتيح نظام التشغيل (`veles secret set …`)؛ ومتغيّرات البيئة هي البديل الاحتياطي والتجاوز.

## مفاتيح API للمزوّدين

سلسلة البحث عن مفتاح API: سلسلة مفاتيح نظام التشغيل (نطاق المشروع) → سلسلة مفاتيح نظام التشغيل (النطاق الافتراضي)
→ متغيّر البيئة.

| المتغيّر | المزوّد | ملاحظات |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | المزوّد الافتراضي |
| `ANTHROPIC_API_KEY` | anthropic | واجهة Anthropic API المباشرة |
| `OPENAI_API_KEY` | openai | واجهة OpenAI API المباشرة |
| `GEMINI_API_KEY` | gemini | المفتاح الأساسي لـ Google Gemini |
| `GOOGLE_API_KEY` | gemini | البديل الاحتياطي لـ Google Gemini |

يصادق `claude-cli` و`gemini-cli` عبر برامجهما التنفيذية الخاصة — دون متغيّر بيئة.

## المزوّدون المحليون

| المتغيّر | الافتراضي | الغرض |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | نقطة نهاية Ollama |
| `OLLAMA_HOST` | يتبع `OLLAMA_BASE_URL` | مضيف Ollama للتضمينات (embeddings) |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | نقطة نهاية خادم llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (مطلوب) | نقطة نهاية المزوّد `openai-compat` |
| `VELES_LOCAL_TOOLS` | معطّل | تمكين استدعاء الأدوات على المزوّدين المحليين (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | افتراضي المزوّد | تجاوز نموذج تضمين Ollama |

## القنوات والعفريت

| المتغيّر | الافتراضي | الغرض |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | رمز بوت Telegram لـ `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | الرابط الأساس للعفريت الذي تستخدمه بوّابات القنوات |
| `VELES_DAEMON_TOKEN` | — | رمز الحامل لمصادقة العفريت |

## المسارات واللغة

| المتغيّر | الافتراضي | الغرض |
|---|---|---|
| `VELES_USER_HOME` | `~` | تجاوز المنزل الذي يحوي `~/.veles/` (الحالة، الذاكرة المؤقتة، فهرس سلسلة المفاتيح) |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | تجاوز مسار سجلّ تعدّد المشاريع |
| `VELES_LOCALE` | `[user] language` أو `en` | تجاوز لغة الواجهة النشطة لتشغيل واحد |
| `VELES_LOG_LEVEL` | `INFO` | إسهاب العفريت/السجلّ (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |

## أعلام السلوك والميزات

| المتغيّر | الافتراضي | الغرض |
|---|---|---|
| `VELES_NO_WIZARD` | معطّل | تخطّي معالج التشغيل لأول مرة (يحتاج أيضًا إلى TTY) |
| `VELES_MANAGER_MODE` | معطّل | فرض المدير متعدد الوكلاء لـ `veles run` (`1` تشغيل / `0` مفتاح إيقاف) |
| `VELES_VERIFY_MODE` | معطّل | فرض تمريرة التحقق→التصعيد لـ `veles run` (`1` تشغيل / `0` مفتاح إيقاف) |
| `VELES_FENCED_TOOLS` | معطّل | تشغيل الأدوات في مسار التنفيذ المُسوَّر/المعزول |
| `VELES_TRUST_AUTO_ALLOW` | معطّل | تجاوز سُلَّم الثقة (CI / الطيّار الآلي / الوكلاء الفرعيون المُصرَّح لهم مسبقًا) |
| `VELES_SANDBOX_ROOTS` | المشروع + `~/.veles` | تجاوز مفصول بـ `:` لجذور القراءة/الكتابة في صندوق الحماية |
| `VELES_FETCH_ALLOW_PRIVATE` | معطّل | السماح للأدوات بجلب عناوين RFC-1918 / الخاصة |
| `VELES_MEMORY_RERANK` | مُفعَّل | إعادة ترتيب متجهية لاستدعاء الذاكرة (يُعطِّلها `0`/`false`) |
| `VELES_WEB_SEARCH_BACKEND` | تلقائي | خلفية بحث الويب لـ `research` و`web_search` |

## السجلّات

| المتغيّر | الغرض |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | مصدر `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | مصدر `veles browse modules` |

## داخلية / للاختبار

| المتغيّر | الغرض |
|---|---|
| `VELES_BUNDLE_VERSION` | داخلي؛ لا ينبغي أن تحتاج إلى ضبطه |
| `VELES_REPL_SIMPLE` | اضبطه على `1` لفرض حلقة REPL البسيطة القائمة على الأسطر بدلًا من تطبيق `prompt_toolkit` بملء الشاشة (بديل احتياطي للطرفيات المحدودة) |
