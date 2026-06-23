# كيفية تشغيل Veles كخدمة خفيّة (daemon)

> 🌐 **اللغات:** [English](../../en/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · **العربية**

الخدمة الخفيّة (daemon) هي خادم HTTP+WS اختياري طويل العمر يكشف الوكيل بوصفه
واجهة برمجية (API) — وهي الأساس لـ[القنوات](connect-telegram.md) (تيليجرام، …)،
و[المهام](long-running-tasks.md) المجدوَلة، والاستخدام البعيد/بلا واجهة.

## التشغيل والإيقاف

```bash
veles daemon start              # ينفصل افتراضيًّا؛ يرتبط بـ 127.0.0.1:8765
veles daemon status             # هل يعمل؟
veles daemon stop               # SIGTERM عبر ملف pid
```

يفصل `start` ويعيد لك الصدفة (shell). لعملية في المقدمة (systemd
`Type=simple`، Docker، التنقيح) مرّر `--foreground`. لتجاوز عنوان الربط:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

يأتي نموذج الخدمة الخفيّة ومزوّدها من إعدادات المشروع وهما **ثابتان طوال
مدة حياتها** — اضبطهما قبل البدء:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## رموز المصادقة

تتحقق عملاء واجهة البرمجة بهويتها باستخدام رمز حامل (bearer token):

```bash
veles daemon token add tui-client     # إصدار رمز
veles daemon token list               # عرض القائمة (مُقنّعة)
veles daemon token remove tui-client
```

## مُنتقي الخدمة الخفيّة (TUI)

شغّل `veles daemon` دون أمر فرعي لفتح لوحة التحكم — شجرة من خدمات
مشروعك الخفيّة وقنوات كل خدمة:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

المفاتيح: `Enter` يفتح سجلّ خدمة خفيّة؛ `s`/`t`/`r` للبدء/الإيقاف/إعادة التشغيل؛
`d` للحذف؛ `c`/`x` لإضافة/إزالة قناة؛ `q` للخروج.

## خدمات خفيّة متعددة لكل مشروع (جلسات مسمّاة)

يمكن لمشروع أن يشغّل عدة خدمات خفيّة بنماذج/منافذ مختلفة في آنٍ واحد. أعلن
جلسةً مسمّاة، ثم شغّلها:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

لكل جلسة مسمّاة كتلة إعداد `[daemon.<name>]` خاصة بها، وقنواتها الخاصة
(`[daemon.<name>.channels.*]`).

## سرد الخدمات الخفيّة عبر المشاريع

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## الخطوة التالية

- [اربط قناة تيليجرام](connect-telegram.md)
- [جدوِل المهام](long-running-tasks.md)
