# متغيّرات البيئة

> 🌐 **اللغات:** [English](../../en/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · **العربية**

تقرأ Veles هذه المتغيّرات في وقت التشغيل. يُفضَّل تخزين مفاتيح API والرموز في سلسلة
مفاتيح نظام التشغيل (`veles secret set …`)؛ ومتغيّرات البيئة هي البديل الاحتياطي وأداة التجاوز.

## مفاتيح API للمزوّدين

تسلسل البحث عن مفتاح API: سلسلة المفاتيح (نطاق المشروع) ← سلسلة المفاتيح (النطاق الافتراضي)
← متغيّر البيئة.

| المتغيّر | المزوّد | ملاحظات |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | المزوّد الافتراضي |
| `ANTHROPIC_API_KEY` | anthropic | واجهة Anthropic المباشرة |
| `OPENAI_API_KEY` | openai | واجهة OpenAI المباشرة |
| `GEMINI_API_KEY` | gemini | المفتاح الأساسي لـ Google Gemini |
| `GOOGLE_API_KEY` | gemini | بديل احتياطي لـ Google Gemini |

يصادق `claude-cli` و`gemini-cli` عبر ملفّيهما التنفيذيّين — دون متغيّر بيئة.

## المزوّدات المحلية

| المتغيّر | الافتراضي | الغرض |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | نقطة نهاية Ollama |
| `OLLAMA_HOST` | يتبع `OLLAMA_BASE_URL` | مضيف Ollama للتضمينات |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | نقطة نهاية خادم llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (مطلوب) | نقطة النهاية لمزوّد `openai-compat` |
| `VELES_LOCAL_TOOLS` | معطّل | تفعيل استدعاء الأدوات على المزوّدات المحلية (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | افتراضي المزوّد | تجاوز نموذج تضمين Ollama |

## القنوات والخدمة الخفيّة

| المتغيّر | الافتراضي | الغرض |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | رمز بوت تيليجرام لـ `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | عنوان URL الأساسي للخدمة الخفيّة الذي تستخدمه بوابات القنوات |
| `VELES_DAEMON_TOKEN` | — | رمز الحامل لمصادقة الخدمة الخفيّة |

## المسارات واللغة

| المتغيّر | الافتراضي | الغرض |
|---|---|---|
| `VELES_USER_HOME` | `~` | تجاوز الدليل الرئيسي الذي يحوي `~/.veles/` (الحالة، الذاكرة المؤقتة، فهرس سلسلة المفاتيح) |
| `VELES_HOME` | — | اسم بديل قديم لـ `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | تجاوز مسار سجلّ تعدّد المشاريع |
| `VELES_LOCALE` | `[user] language` أو `en` | تجاوز لغة الواجهة النشطة لتشغيل واحد |
| `VELES_LOG_LEVEL` | `INFO` | إسهاب سجلّ الخدمة الخفيّة (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | تجاوز اسم ملف الإعداد (للاختبار) |

## رايات السلوك والميزات

| المتغيّر | الافتراضي | الغرض |
|---|---|---|
| `VELES_NO_WIZARD` | معطّل | تخطّي معالج أول تشغيل (يحتاج أيضًا طرفية TTY) |
| `VELES_MANAGER_MODE` | معطّل | فرض مدير متعدّد الوكلاء لـ `veles run` (`1` تشغيل / `0` مفتاح إيقاف) |
| `VELES_FENCED_TOOLS` | معطّل | تشغيل الأدوات في مسار التنفيذ المسوَّر/المعزول |
| `VELES_TRUST_AUTO_ALLOW` | معطّل | تجاوز سلّم الثقة (CI / الطيّار الآلي / الوكلاء الفرعيون المُصرَّح لهم مسبقًا) |
| `VELES_SANDBOX_ROOTS` | المشروع + `~/.veles` | تجاوز مفصول بـ `:` لجذور الصندوق الرملي للقراءة/الكتابة |
| `VELES_FETCH_ALLOW_PRIVATE` | معطّل | السماح للأدوات بجلب عناوين RFC-1918 / خاصّة |
| `VELES_MEMORY_RERANK` | مُفعَّل | إعادة ترتيب متّجهيّة لاسترجاع الذاكرة (`0`/`false` يعطّلها) |
| `VELES_WEB_SEARCH_BACKEND` | تلقائي | الخلفية لبحث الويب في `research` و`web_search` |

## السجلّات

| المتغيّر | الغرض |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | المصدر لـ `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | المصدر لـ `veles browse modules` |

## الداخلية / الاختبار

`VELES_BUNDLE_VERSION`، `VELES_CACHE_BREAKPOINT` — داخلية؛ لا ينبغي أن تحتاج
إلى ضبطها.
