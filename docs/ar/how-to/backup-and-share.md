# كيفية إنشاء نسخة احتياطية لمشروع ومشاركته

> 🌐 **اللغات:** [English](../../en/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · **العربية**

مشاريع Veles قابلة للنقل. صدِّر مشروعًا إلى حزمة `.tar.gz` واحدة من أجل
النسخ الاحتياطي أو الترحيل، أو إلى قالب منقّى لمشاركته دون تسريب بياناتك.

## نسخة احتياطية كاملة

تحزم المشروع بالكامل (`.veles/` + `AGENTS.md`)، باستثناء العناصر العابرة وقت التشغيل (الأقفال،
وحالة الميزانية):

```bash
veles export full ./my-project-backup.tar.gz
```

استعدها في أي مكان:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

تتضمن الحزمة الكاملة ملف `memory.db` الخاص بك (الجلسات، والرؤى)، لذا تعامل معها كأنها
بيانات خاصة.

## قالب قابل للمشاركة

يحزم فقط الهيكل القابل لإعادة الاستخدام — المخطط، والمهارات، والوحدات، وصفحات الويكي
غير المرتبطة بالجلسات. وهو **يجرّد** `memory.db`، و`sources/`، و`sessions/`، ومنح الثقة، كما
يحجب المعلومات الشخصية القابلة للتعريف (PII) من النصوص:

```bash
veles export template ./my-template.tar.gz
```

سلّم القالب إلى زميل؛ فيقوم باستيراده عبر `veles import` ويحصل على هيكلك
ومهاراتك دون سجلّ محادثاتك أو مصادرك الخام.

## أيهما تستخدم

| الهدف | الأمر |
|---|---|
| إنشاء نسخة احتياطية لمشروع / نقله سليمًا | `veles export full` |
| مشاركة الهيكل + المهارات، دون البيانات | `veles export template` |
