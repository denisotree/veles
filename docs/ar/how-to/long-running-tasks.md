# كيفية تشغيل المهام الطويلة الأمد: الأهداف، والوظائف، والحلم، والبحث

> 🌐 **اللغات:** [English](../../en/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · **العربية**

إلى جانب المُحَثّات المفردة، يستطيع Veles السعي وراء **أهداف** متعددة الخطوات بميزانيات، وتشغيل
**وظائف مجدولة**، و**الحلم** لتوحيد الذاكرة، و**البحث** على الويب
بالتوازي، وتفكيك العمل عبر **مدير** ووكلاء فرعيين.

## الأهداف — غايات بميزانيات ونقاط تفتيش

الهدف غاية بعيدة المدى ذات حدود صريحة وسجلّ تقدّم:

```bash
veles goal start "Draft a competitor analysis report" \
  --done-when "report.md exists and cites >=3 sources" \
  --max-steps 30 --max-cost-usd 5 --max-wall-time-s 3600

veles goal list
veles goal show <id>
veles goal checkpoint <id> "Outlined sections; cited 2 sources" --cost-usd 0.40
veles goal pause <id> ; veles goal resume <id>
veles goal done <id> --evidence report.md
veles goal cancel <id> --reason "scope changed"
```

في الـ TUI، يشغّل وضع تشغيل **goal** (تنقّل عبره بـ `Shift+Tab`) آلة الحالة المنتهية نفسها
بشكل تفاعلي: فيقابلك بأسئلة، ويؤكّد خطة، وينفّذ، ويتحقّق.

## الوظائف — تشغيلات الوكيل المجدولة

جدوِل تشغيل مُحَثّ وفق تعبير cron، أو فترة زمنية، أو مرّة واحدة في وقت محدّد:

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # run on the next tick
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

يقبل `--schedule` تعبير cron، أو `<N><s|m|h|d>` (مثل `30m`)، أو طابعًا زمنيًا
بصيغة ISO. تعمل الوظائف عندما يكون الخادم الخلفي قيد التشغيل، أو شغّلها كلها مرّة واحدة بشكل متزامن:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

سلّم ناتج وظيفة إلى قناة باستخدام `--deliver-to telegram:<chat_id>`.

## الحلم — توحيد الذاكرة في الخلفية

يستخرج `dream` الرؤى، ويزيل تكرار المهارات، ويقترح الترقيات، ويفحص
الويكي — مبقيًا الذاكرة منتعشة دون أن تنتظر:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

يحلم الخادم الخلفي قيد التشغيل تلقائيًا عندما يكون خاملًا.

## البحث — تحقيق متوازٍ على الويب

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

يفكّك Veles السؤال، ويستكشف الزوايا بالتوازي، ويصوغ
تقريرًا موثّق المصادر.

## وضع المدير — تفكيك أي مُحَثّ

فعّل التفكيك متعدد الوكلاء لتشغيل واحد (يُنشئ المدير وكلاء فرعيين من نوع
المستكشف / الكاتب / المستشار ولا يكتب الإجابة النهائية بنفسه أبدًا):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

انظر [تنسيق الوكلاء المتعددين](../explanation/multi-agent-orchestration.md).
