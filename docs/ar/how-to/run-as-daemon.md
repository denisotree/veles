# كيفية تشغيل Veles كخدمة خفيّة (daemon)

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

العفريت خادم HTTP+WS اختياري طويل العمر يعرض الوكيل كواجهة برمجية —
وهو الأساس لـ [القنوات](connect-telegram.md) (Telegram …)، و[المهام](long-running-tasks.md) المجدولة،
والاستخدام البعيد/بدون واجهة.

## البدء والإيقاف

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

ينفصل `start` ويعيد لك الصدفة. للحصول على عملية في المقدّمة (systemd
`Type=simple`، Docker، التنقيح) مرّر `--foreground`. تجاوز الربط:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

يأتي نموذج العفريت ومزوّده من إعداد المشروع وهما **ثابتان طوال
عمره** — اضبطهما قبل البدء:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## رموز المصادقة

تصادق عملاء الواجهة البرمجية برمز حامل:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## مُنتقي العفاريت (TUI)

شغّل `veles daemon` دون أمر فرعي لفتح لوحة التحكم — شجرة عفاريت
مشروعك وقنوات كل عفريت:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

المفاتيح: `Enter` يفتح سجلّ عفريت؛ و`s`/`t`/`r` للبدء/الإيقاف/إعادة التشغيل؛ و`d` للحذف؛
و`c`/`x` لإضافة/إزالة قناة؛ و`q` للإنهاء.

## عدّة عفاريت لكل مشروع (الجلسات المُسمّاة)

يمكن للمشروع تشغيل عدّة عفاريت بنماذج/منافذ مختلفة دفعة واحدة. أعلِن عن
جلسة مُسمّاة، ثم ابدأها:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

لكل جلسة مُسمّاة كتلة إعداد `[daemon.<name>]` خاصة بها وقنواتها
الخاصة (`[daemon.<name>.channels.*]`).

## اسرد العفاريت عبر المشاريع

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## التالي

- [اربط قناة Telegram](connect-telegram.md)
- [جدوِل المهام](long-running-tasks.md)
