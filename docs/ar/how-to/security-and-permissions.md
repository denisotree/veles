# كيفية إدارة الأمان: الثقة، الطيّار الآلي، الأسرار

> 🌐 **اللغات:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · **العربية** · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

تحجز Veles الإجراءات الخطرة خلف **سلّم الثقة**، وتعزل الوصول إلى الملفات في صندوق
رمليّ (sandbox)، وتحفظ الأسرار في سلسلة مفاتيح نظام التشغيل. للاطلاع على المبرّرات،
راجع [الثقة والصندوق الرملي](../explanation/trust-and-sandbox.md).

## سلّم الثقة

تطلب الأدوات الحسّاسة (`run_shell`، `write_file`، `fetch_url`، …) تأكيدًا قبل التشغيل.
أنت تختار: السماح **مرة واحدة**، أو **دائمًا لهذا المشروع**، أو **دائمًا في كل مكان**،
أو **الرفض**. تظلّ التصاريح محفوظة كي لا تُسأل مجددًا.

أدِر التصاريح دون انتظار طلب:

```bash
veles trust list                          # التصاريح الحالية (مستخدم + مشروع)
veles trust set run_shell --scope project # تصريح مسبق لهذا المشروع
veles trust set write_file --scope user   # تصريح مسبق في كل مكان
veles trust revoke run_shell              # إزالة تصريح
veles trust clear --scope all             # محو كل شيء
```

تُؤكَّد بعض الإجراءات **دائمًا** حتى مع وجود تصريح — حذف الملفات، وجلب
عناوين URL، وتثبيت مهارة/أداة/وحدة جديدة، وربط قناة، والكتابة خارج المشروع.

## الطيّار الآلي — تجاوز محدود زمنيًّا

لتشغيلٍ بلا إشراف (دفعة ليلية)، افتح نافذة تُسمح فيها طلبات الثقة تلقائيًّا:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

يُسجَّل كل إجراء للطيّار الآلي لمراجعته لاحقًا. ترفض السياقات غير التفاعلية
(الخدمة الخفيّة، الدفعات) افتراضيًّا ما لم يكن الطيّار الآلي نشطًا.

## الأسرار

تعيش مفاتيح واجهات البرمجة ورموز البوتات في سلسلة مفاتيح نظام التشغيل، ولا توضع
أبدًا في ملفات الإعداد:

```bash
veles secret set OPENROUTER_API_KEY       # يطلب الإدخال (أو مرّره عبر stdin)
veles secret list                         # أيُّ الأسرار مُهيَّأة
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
```

يلجأ البحث احتياطيًّا إلى [متغيّر البيئة](../reference/environment-variables.md) المطابق
ما لم تمرّر `--no-env-fallback`.

## الصندوق الرملي

تستطيع الأدوات القراءة داخل المشروع النشط و`~/.veles/`، والكتابة فقط في المناطق
القابلة للكتابة في التخطيط (`wiki/` و`.veles/` افتراضيًّا). تجاوز الجذور
للإعدادات المتقدّمة باستخدام `VELES_SANDBOX_ROOTS` (مفصولة بـ `:`). تحتفظ عمليات
جلب عناوين URL بقائمة رفض ضد SSRF؛ ويرفع `VELES_FETCH_ALLOW_PRIVATE=1` حظر
الشبكة الخاصة.
