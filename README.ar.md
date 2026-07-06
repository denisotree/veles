# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <a href="README.ru.md">Русский</a> ·
  <b>العربية</b> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**إطار عمل بسيط لوكيل سطر الأوامر يزداد ذكاءً مع كل جلسة.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles REPL — اطرح سؤالاً واحصل على إجابة مستندة إلى ذاكرة المشروع نفسه" width="800">
</p>

على عكس أدوات المحادثة التي تبدأ من الصفر في كل مرة، يحتفظ Veles بـ**ذاكرة مشروع منظّمة** — استنتاجات وقواعد ومعرفة منسَّقة تتراكم عبر الجلسات وتجعل الوكيل أكثر فائدة كلما طالت مدة استخدامك له. وطريقة تنظيم *محتواك* قابلة للتوصيل: ويكي LLM على نمط Karpathy افتراضيًا، أو ملاحظات مسطّحة، أو بلا أي بنية على الإطلاق لمستودعات الشيفرة. مبنيّ بنظافة: لا ملفات عملاقة، ولا تقييد بمورّد، ولا مزامنة سحابية.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (just run `veles` with no subcommand)
```

---

## لماذا Veles؟

**ذاكرة متراكمة** — يُختزَل كل جلسة بواسطة المُنسِّق (Curator) إلى ذاكرة خاصة بكل مشروع (استنتاجات، وقواعد سلوكية، وملخّصات جلسات في `.veles/`). يستدعي الوكيل تلقائيًا الحقائق ذات الصلة والقرارات السابقة — فتتوقف عن إعادة شرح السياق نفسه. وتعمل الذاكرة تحت *أي* تخطيط للمحتوى.

**تخطيطات محتوى قابلة للتوصيل** — يُنشئ `veles init` افتراضيًا ويكي LLM على نمط Karpathy؛ ويمنحك `--layout notes` دليل ملاحظات مسطّحًا؛ بينما لا يضيف `--layout bare` أي بنية على الإطلاق (مثالي لمستودعات الشيفرة). حِزَم التخطيط المخصّصة هي مجرد ملف TOML واحد في `~/.veles/layouts/`.

**توجيه مستقل عن المورّد** — OpenRouter أو Anthropic أو OpenAI أو Gemini أو Ollama أو llamacpp أو اشتراك سطر الأوامر `claude`/`gemini` الخاص بك. ويمكن توجيه أنواع المهام المختلفة (التخطيط، الضغط، الاستنتاجات) إلى نماذج مختلفة.

**مهارات تتراكم** — تتحوّل كتل التوجيه القابلة لإعادة الاستخدام إلى أدوات للوكيل. رقِّ مهارة من مشروع إلى نطاق المستخدم العام فتصبح متاحة في كل مكان. كما يعثر إزالة التكرار المدمج على المهارات شبه المكرّرة قبل أن تتشعّب.

**محلّي أولًا + معزول** — لا تتبّع، ولا مزامنة سحابية. لا يرى الوكيل سوى دليل المشروع النشط. يطلب سُلَّم الثقة الإذن عند كل استدعاء أداة حسّاسة؛ مع إمكانية المنح المسبق لأجل CI.

**معياري لا متجانس** — نواة بسيطة (الذاكرة، حلقة الوكيل، بروتوكول المورّد، سجل الأدوات). وكل ما عداها — الواجهة النصية، والخادم الخفي، وبوابة Telegram، والبحث المعمّق، ومجدول المهام — وحدة اختيارية قابلة للتحميل.

---

## بداية سريعة

**المتطلبات:** Python 3.13+، وmacOS / Linux (وWindows بأفضل جهد ممكن). ثبِّت [uv](https://docs.astral.sh/uv/) أولًا.

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

افتح REPL التفاعلية بدلًا من ذلك (الأمر المجرّد `veles` يفعل الشيء نفسه):

```bash
veles
```

عند التشغيل الأول، سيطلب منك معالج الإعداد لغتك المفضّلة، والمورّد، واسم المشروع.

---

## المورّدون

| المورّد | متغيّر البيئة | ملاحظات |
|---|---|---|
| **OpenRouter** *(مُوصى به)* | `OPENROUTER_API_KEY` | Claude وGPT وGemini وLlama — مفتاح واحد، مئات النماذج |
| Anthropic | `ANTHROPIC_API_KEY` | واجهة برمجة مباشرة |
| OpenAI | `OPENAI_API_KEY` | واجهة برمجة مباشرة |
| Gemini | `GEMINI_API_KEY` أو `GOOGLE_API_KEY` | واجهة برمجة مباشرة |
| `claude` CLI | — | يستخدم اشتراك Claude الخاص بك؛ لا حاجة لمفتاح واجهة برمجة |
| `gemini` CLI | — | يستخدم اشتراك Gemini الخاص بك؛ لا حاجة لمفتاح واجهة برمجة |
| Ollama | — | نماذج محلية، `http://localhost:11434/v1` |
| llamacpp | — | نماذج محلية، `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | أي نقطة نهاية متوافقة مع OpenAI |

التجاوز لكل تشغيل:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

خزّن مفاتيح واجهة البرمجة في سلسلة مفاتيح نظام التشغيل بدلًا من متغيّرات البيئة:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## سير العمل الأساسي

### اختر تخطيطًا للمحتوى

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

تعمل ذاكرة الوكيل الخاصّة (الاستنتاجات والقواعد وملخّصات الجلسات في `.veles/`) بالطريقة نفسها تحت كل تخطيط. والحِزَم المخصّصة هي ملف `layout.toml` واحد في `~/.veles/layouts/<name>/`.

### ابنِ قاعدة معرفة (تخطيط llm-wiki)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="قاعدة معرفة Veles — ابتلاع مصدر إلى صفحة ويكي، ثم اطرح سؤالاً واحصل على إجابة تستشهد به" width="800">
</p>

يعمل المُنسِّق تلقائيًا بعد الجلسات. ويلتقط استخراج الاستنتاجات عبارات مثل "always prefer X" أو "never do Y" ويكتبها كاستنتاجات دائمة للمشروع.

### البحث المعمّق

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

يفكّك السؤال إلى أسئلة فرعية متوازية، ويستكشف كلًا منها، ثم يركّب تقريرًا منظّمًا.

### الأهداف طويلة المدى

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### المهام المجدولة

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## توجيه النماذج (المجموعات)

وجِّه أنواع المهام المختلفة إلى نماذج مختلفة — اضبطه مرة واحدة وانسَه.

**عبر سطر الأوامر:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**عبر اللغة الطبيعية في `AGENTS.md`:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## المهارات والوحدات

**المهارات** هي كتل توجيه قابلة لإعادة الاستخدام (`SKILL.md`) تتحوّل تلقائيًا إلى أدوات للوكيل.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**الوحدات** هي إضافات Python يمكنها الارتباط بدورة حياة الوكيل (`pre_turn` و`post_turn` و`pre_tool_call` و`post_tool_call`) والاعتراض على استدعاءات الأدوات.

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## جلسة تفاعلية (REPL)

```bash
veles                        # new session (bare `veles` launches the interactive REPL)
veles --resume <id>          # resume a specific session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="Veles REPL — أدوات الفحص بالشرطة المائلة (‎/status و‎/context)، وتبديل الأوضاع، ولوحة الأوامر" width="800">
</p>

تُظهِر أوامر الشرطة المائلة كل شيء مباشرةً — `/status` و`/tokens` و`/context` و`/mode` و`/help` — ويتنقّل `Shift+Tab` بين الأوضاع (تلقائي / تخطيط / كتابة / هدف).

| المفتاح | الإجراء |
|---|---|
| `Enter` | إرسال الرسالة |
| `Shift+Enter` | سطر جديد في المحرّر |
| `Ctrl+I` | تبديل مُفتِّش نشاط الأدوات |
| `Ctrl+R` | طبقة منتقي الجلسات |
| `Ctrl+G` | فتح `$EDITOR` على المسوّدة الحالية |
| `Tab` | إكمال تلقائي لأوامر الشرطة المائلة |
| `Ctrl+D` | إنهاء |

أوامر الشرطة المائلة: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` وغيرها.

---

## الخادم الخفي + Telegram

شغِّل Veles كخادم خفي دائم بواجهة HTTP/WebSocket. في دليل مشروع جديد، يقودك `veles daemon start` عبر الإعداد — تهيئة المشروع، وتمكين الخادم الخفي، و**توصيل قناة**: اختر أولًا *نوع* القناة (Telegram هو المنصّة الوحيدة المتاحة اليوم، لكن المنتقي هو الوصلة التي تُسجَّل عليها القنوات الجديدة)، ثم املأ حقول تلك القناة (رمز البوت، القائمة البيضاء). لا حاجة لفتح الواجهة النصية أولًا.

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — معالج يُشغِّل الخادم الخفي ويوصِل قناة Telegram (نوع القناة أولًا، ثم رمزها وقائمتها البيضاء)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

يفتح الأمر المجرّد `veles daemon` لوحة تحكّم حيّة — شجرة من المشروع ← الخوادم الخفية ← القنوات. ابدأ الخوادم الخفية أو أوقِفها أو أعِد تشغيلها أو احذفها، وأضِف القنوات أو أزِلها (نفس تدفّق نوع-القناة-أولًا، المفتاح `c`) عبر كل مشروع، كل ذلك من لوحة المفاتيح:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — واجهة لوحة التحكّم النصية: شجرة من المشروع ← الخوادم الخفية ← القنوات مع بدء/إيقاف/إعادة تشغيل/حذف وإدارة قنوات مدمجة" width="800">
</p>

كما يتوفّر معالج القناة نفسه بشكل مستقل (`veles channel add`) على مشروع قيد التشغيل بالفعل.

نقاط نهاية واجهة البرمجة: `POST /v1/runs` لإرسال توجيه، و`WS /v1/runs/{id}/events` لبث الاستجابة، و`GET /v1/sessions` لسرد الجلسات. وتتطلّب جميعها — عدا `GET /v1/health` — ترويسة `Authorization: Bearer <token>` (أنشئ واحدًا بـ `veles daemon token add <name>`).

يحصل كل مستخدم Telegram على جلسة دائمة. استخدم `veles channel list-sessions` / `reset-session` لإدارة الربط.

---

## تعدد المشاريع

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## الثقة والأمان

يطلب كل استدعاء أداة حسّاسة (تنفيذ صدفة، كتابة ملفات، جلب عناوين URL) الإذن:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

المنح المسبق لأجل CI أو التشغيلات المستقلّة الممتدّة:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

لا يرى الوكيل سوى دليل المشروع النشط — أمّا المشاريع الأخرى وهروب الروابط الرمزية واجتياز `..` فمحجوبة.

---

## التصدير / الاستيراد

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## مرجع سطر الأوامر

| الأمر | الغرض |
|---|---|
| `veles init [name]` | إنشاء مشروع جديد |
| `veles run "<prompt>"` | تشغيل وكيل بدورة واحدة |
| `veles` | واجهة REPL التفاعلية (دون أمر فرعي) |
| `veles add <file\|url>` | ابتلاع مصدر ← صفحة ويكي |
| `veles research "<question>"` | بحث معمّق متعدّد الزوايا |
| `veles curate` | دمج الجلسات في الويكي |
| `veles sessions {list,show,delete,search}` | إدارة الجلسات |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | إدارة المهارات |
| `veles tool {list,show,promote}` | إدارة الأدوات |
| `veles module {list,add,remove}` | إدارة الإضافات |
| `veles route {show,set,reset,refresh}` | توجيه النماذج |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | الأهداف طويلة الأفق |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | المهام المجدولة |
| `veles dream` | دورة دمج الذاكرة في الخلفية |
| `veles project {list,add,remove,switch}` | سجل تعدّد المشاريع |
| `veles subproject {init,list,switch,remove,suggest}` | المشاريع الفرعية |
| `veles trust {list,set,revoke,clear}` | منح الثقة |
| `veles autopilot {enable,disable,status}` | تجاوز مؤقت للثقة |
| `veles secret {set,get,list,delete}` | أسرار سلسلة مفاتيح نظام التشغيل |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | خادم HTTP/WS الخفي |
| `veles channel {run,list-sessions,reset-session}` | بوابة القنوات الخارجية |
| `veles mcp {list,test}` | خوادم MCP الخارجية |
| `veles models <provider>` | سرد نماذج المورّد |
| `veles doctor` | فحوص السلامة |
| `veles export / import` | نسخ المشروع احتياطيًا ونقله |

لكل أمر خيار `--help`.

---

## التوثيق

التوثيق الكامل — منظّم وفق Diátaxis (دروس تعليمية · أدلة إرشادية · مرجع · شرح):

- **العربية:** [`docs/ar/index.md`](docs/ar/index.md)

لغات أخرى: استخدم محوّل 🌐 أعلى أي صفحة من صفحات التوثيق.

---

## المساهمة

المساهمات مرحَّب بها للغاية — فـ Veles **مبنيّ ليُوسَّع**. تبقى النواة صغيرة (حلقة الوكيل + ذاكرة المشروع + بروتوكول المورّد)؛ وكل ما عداها تقريبًا نقطة توسيع قابلة للتوصيل، لذا فإن إضافة قدرة نادرًا ما تعني المساس بالنواة:

- **محوّلات المورّدين** (`src/veles/adapters/`) — صِل خلفية نموذج جديدة.
- **المهارات** — كتل توجيه وأدوات قابلة لإعادة الاستخدام مع وراثة `extends:`، قابلة للترقية من مشروع إلى نطاق المستخدم العام.
- **الأدوات** — شيفرة Python مكتوبة الأنواع يكتبها الوكيل ويعيد استخدامها، تحت `<project>/.veles/tools/`.
- **حِزَم التخطيط** — ملف `layout.toml` واحد في `~/.veles/layouts/<name>/` يُعرِّف تخطيط محتوى كاملًا.
- **خطّافات الوحدات** — قابلية الرصد والتسجيل والسياسات عبر خطّافات `pre_turn` / `post_turn` (`src/veles/core/modules.py`).
- **القنوات وخوادم MCP** — بوابات جديدة ومصادر أدوات خارجية.
- **اللغات** — الترجمات في `src/veles/locales/`.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

الشيفرة مفكّكة عن قصد — مسؤولية واحدة، لا ملفات عملاقة. اقرأ [`CONTRIBUTING.md`](CONTRIBUTING.md) للاطلاع على الاصطلاحات و[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) قبل فتح طلب سحب. أفضل المساهمات الأولى: محوّلات المورّدين، ومهارات سير العمل، وخطّافات الوحدات، وملفات اللغات.

---

## الترخيص

Apache 2.0 مع منح براءات الاختراع — انظر [`LICENSE`](LICENSE) و[`NOTICE`](NOTICE).
