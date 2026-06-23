# توثيق Veles

> 🌐 **اللغات:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · **العربية** · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles إطار عمل وكلاء بواجهة سطر أوامر، بسيط ومحلي أولًا. توجّهه إلى دليل
مشروع؛ فيحتفظ بـ**ذاكرة مشروع** مُهيكَلة، و**يتعلّم** من جلساتك، ويشغّل أي
مزوّد LLM (سحابي أو محلي)، ويراكم **مهارات** و**أدوات** قابلة لإعادة الاستخدام
أثناء عمله.

يتبع هذا التوثيق نموذج [Diátaxis](https://diataxis.fr/). اختر
الربع الذي يطابق ما تحتاجه الآن.

## ابدأ من هنا

إذا لم تشغّل Veles من قبل، أنجز الدرسين بالترتيب:

1. **[البدء](tutorials/getting-started.md)** — ثبّت Veles، واضبط مفتاح
   API، وأنشئ مشروعك الأول، وشغّل موجّهك الأول.
2. **[بناء قاعدة معرفة](tutorials/building-a-knowledge-base.md)** — استوعب
   المصادر في LLM-Wiki، واطرح أسئلة، وادمج الجلسات.

## الدروس — تعلّم بالممارسة

- [البدء](tutorials/getting-started.md)
- [بناء قاعدة معرفة](tutorials/building-a-knowledge-base.md)

## أدلة الكيفية — أنجز مهمة

- [تهيئة المزوّدين (السحابي والمحلي)](how-to/configure-providers.md)
- [توجيه مهام مختلفة إلى نماذج مختلفة](how-to/per-task-routing.md)
- [تشغيل Veles كبرنامج خفي](how-to/run-as-daemon.md)
- [توصيل قناة تيليجرام](how-to/connect-telegram.md)
- [إدارة المهارات والأدوات والوحدات](how-to/manage-skills-and-tools.md)
- [العمل مع مشاريع متعددة ومشاريع فرعية](how-to/multi-project-and-subprojects.md)
- [الأمان: الثقة، الطيّار الآلي، الأسرار](how-to/security-and-permissions.md)
- [المهام طويلة الأمد: الأهداف، الوظائف، الحلم، البحث](how-to/long-running-tasks.md)
- [توصيل خوادم MCP خارجية](how-to/external-mcp-servers.md)
- [النسخ الاحتياطي للمشروع ومشاركته](how-to/backup-and-share.md)

## المرجع — ابحث عنه

- [مرجع أوامر CLI](reference/cli.md)
- [التهيئة (`config.toml`)](reference/configuration.md)
- [متغيّرات البيئة](reference/environment-variables.md)
- [المزوّدون](reference/providers.md)
- [اختصارات لوحة المفاتيح وأوامر الشرطة المائلة في TUI](reference/tui.md)
- [بنية المشروع وحالته](reference/project-layout.md)

## الشرح — افهم التصميم

- [نظرة عامة على البنية المعمارية](explanation/architecture.md)
- [ذاكرة المشروع وحلقة التعلّم](explanation/project-memory-and-learning-loop.md)
- [المهارات والأدوات كقدرة متراكمة](explanation/skills-and-tools.md)
- [أوضاع التشغيل](explanation/modes.md)
- [تنسيق الوكلاء المتعددين](explanation/multi-agent-orchestration.md)
- [حزم البنية وLLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [الثقة والبيئة المعزولة](explanation/trust-and-sandbox.md)

---

لرؤية المنتج ومبرّرات التصميم راجع `VISION.md` (في جذر المستودع)؛
ولسجل التنفيذ الكامل راجع `MILESTONES.md`. هذان موجّهان للمطوّرين —
أما هذا التوثيق فهو لـ**استخدام** Veles.
