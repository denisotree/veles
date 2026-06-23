# كيفية ربط قناة Telegram

> 🌐 **اللغات:** [English](../../en/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · **العربية**

تحدّث إلى مشروع Veles من Telegram. القناة هي بوّابة تمرّر
الرسائل إلى [خادم خلفي (daemon)](run-as-daemon.md) وتبثّ الردود مرة أخرى. كل دردشة تحصل
على جلسة محادثة خاصة بها.

## المتطلبات المسبقة

- خادم خلفي قيد التشغيل (انظر [التشغيل كخادم خلفي](run-as-daemon.md)).
- رمز بوت Telegram من [@BotFather](https://t.me/BotFather).

## الخيار أ — الربط عبر المعالج (موصى به)

من داخل المشروع، شغّل معالج القناة؛ فيكتب التهيئة ويخزّن
الرمز في سلسلة مفاتيح نظام التشغيل:

```bash
veles channel add --channel telegram
```

أو اربط بجلسة خادم خلفي مُسمّاة محدّدة:

```bash
veles channel add --channel telegram --session api
```

يمكنك أيضًا فعل ذلك من [واجهة منتقي الخادم الخلفي (TUI)](run-as-daemon.md#the-daemon-picker-tui):
اضغط `c` على خادم خلفي واتبع التعليمات.

ينتج عن ذلك كتلة تهيئة:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

تقيّد **القائمة البيضاء (whitelist)** من يردّ عليه البوت (`@username` في Telegram أو معرّف المستخدم
الرقمي). اتركها فارغة ليردّ على الجميع — وهو أمر غير موصى به، لأن كل
رسالة تستهلك رموز النموذج (tokens).

أعد تشغيل الخادم الخلفي لتطبيق التغييرات:

```bash
veles daemon restart
```

## الخيار ب — تشغيل بوّابة مستقلّة

إذا كنت تفضّل عملية منفصلة (بدلًا من القناة المضمّنة في الخادم الخلفي)، شغّل:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## إدارة جلسات الدردشة

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## قيود الوسائط المتعددة

إرسال **صورة أو رسالة صوتية** يعيد حاليًا إشعار "غير مهيّأ".
يعرّف Veles بروتوكولات `VisionAdapter` / محوّل STT وسجلًّا
(`modules/vision.py`، `modules/stt.py`)، لكن **لا يُشحن أي محوّل ملموس ولا يُسجَّل
أيٌّ منها عند بدء تشغيل الخادم الخلفي**، لذا لا تُحلَّل الصور والصوت بعد. تعمل دردشة
النص بالكامل. انظر [مرجع المزوّدين](../reference/providers.md#multimodal-status-vision--speech-to-text).
