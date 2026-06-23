# كيفية إدارة المهارات والأدوات والوحدات

> 🌐 **اللغات:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · **العربية** · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

يراكم Veles القدرات مع مرور الوقت. **المهارات** هي سير عمل قابلة لإعادة الاستخدام،
و**الأدوات** هي إجراءات قابلة للتنفيذ، و**الوحدات** إضافات اختيارية. يعيش كلٌّ منها على
نطاقين: محلي للمشروع (`<project>/.veles/`) وعام على مستوى المستخدم (`~/.veles/`). للاطلاع على
المفاهيم، انظر [المهارات والأدوات](../explanation/skills-and-tools.md).

## المهارات

المهارة هي ملف `SKILL.md` (بيانات أوّلية في المقدّمة + نص المُحَثّ) يستطيع الوكيل استدعاءها كأداة.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### الترقية / التخفيض بين النطاقات

المهارة التي تثبت فائدتها في مشروع واحد يمكن نقلها إلى نطاق المستخدم حتى يراها كل
مشروع (أو العكس):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### العثور على التكرارات ومرشّحي الترقية

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## الأدوات

تُفهرس الأدوات في ملف `memory.db` الخاص بالمشروع مع قياس استخدامها. يستطيع Veles
كتابة أدواته الخاصة أثناء عمله؛ وتديرها أنت عبر:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

الأدوات الحسّاسة (`run_shell`، و`write_file`، و`fetch_url`، …) يحكمها
[سلّم الثقة](security-and-permissions.md).

## الوحدات

تضيف الوحدات قدرات اختيارية (التضمينات، والرؤية، وتحويل الكلام إلى نص) دون تضخيم
النواة. يتطلّب تثبيت أيٍّ منها تأكيدًا افتراضيًا.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## اكتشف المزيد

تصفّح السجلّات المنسَّقة:

```bash
veles browse skills [query]
veles browse modules [query]
```
