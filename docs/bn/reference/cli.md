# CLI রেফারেন্স

> 🌐 **ভাষা:** [English](../../en/reference/cli.md) · [简体中文](../../zh-CN/reference/cli.md) · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · [Español](../../es/reference/cli.md) · [Français](../../fr/reference/cli.md) · [Italiano](../../it/reference/cli.md) · [Português (BR)](../../pt-BR/reference/cli.md) · [Português (PT)](../../pt-PT/reference/cli.md) · [Русский](../../ru/reference/cli.md) · [العربية](../../ar/reference/cli.md) · [हिन्दी](../../hi/reference/cli.md) · **বাংলা** · [Tiếng Việt](../../vi/reference/cli.md)

Veles-এর প্রতিটি কমান্ড, সাবকমান্ড এবং ফ্ল্যাগ। নির্ভরযোগ্য, সর্বদা-হালনাগাদ
সিগনেচার পেতে `veles <command> --help` চালান — এই পৃষ্ঠাটি
`src/veles/cli/_parsers/`-এর আর্গুমেন্ট পার্সারগুলোর প্রতিচ্ছবি।

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — `~/.veles/config.toml` অনুপস্থিত থাকলেও প্রথম-রানের সেটআপ
  উইজার্ড এড়িয়ে যায় (এটি একটি TTY এবং `VELES_NO_WIZARD=1`-এর উপরও নির্ভরশীল)।
- কোনো আর্গুমেন্ট ছাড়া `veles` ইন্টারঅ্যাক্টিভ [TUI](tui.md) চালু করে।

বেশিরভাগ এজেন্ট কমান্ড নিচে তালিকাভুক্ত [শেয়ার্ড এজেন্ট-লুপ ফ্ল্যাগ](#shared-agent-loop-flags)
এবং [প্রোভাইডার নাম](#provider-names) গ্রহণ করে।

---

## প্রজেক্ট লাইফসাইকেল

### `veles init [name]`
বর্তমান ডিরেক্টরিতে একটি নতুন Veles প্রজেক্ট তৈরি করে (একটি `.veles/` স্টেট
ডিরেক্টরি + `AGENTS.md` + নির্বাচিত লেআউট প্যাকের কন্টেন্ট স্ক্যাফোল্ড)।

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `name` (positional) | cwd basename | প্রজেক্টের নাম |
| `--layout <name>` | `llm-wiki` | কন্টেন্ট স্ক্যাফোল্ডের জন্য লেআউট প্যাক (`llm-wiki`, `notes`, `bare`, অথবা `~/.veles/layouts/` থেকে একটি কাস্টম প্যাক) |
| `--force` | off | `.veles/` ইতিমধ্যে বিদ্যমান থাকলেও পুনরায় তৈরি করে |

### `veles schema {validate,edit,fix}`
`AGENTS.md` (প্রজেক্ট কনটেক্সট ফাইল) যাচাই বা সম্পাদনা করে।

- `validate` — প্রয়োজনীয় H2 সেকশনগুলোর জন্য পরীক্ষা করে।
- `edit` — `$EDITOR`-এ (ডিফল্ট `vi`) `AGENTS.md` খোলে, প্রস্থানে যাচাই করে।
- `fix` — একটি LLM উইজার্ডের মাধ্যমে অনুপস্থিত সেকশন ইন্টারঅ্যাক্টিভভাবে যোগ করে।

### `veles self-doc [refresh|show]`
প্রজেক্টের সেলফ-ডকুমেন্টেশন (`wiki/self-doc/overview.md`) তৈরি ও প্রদর্শন করে।
শুধু `veles self-doc` বর্তমান পৃষ্ঠা দেখায়; `refresh` এটি পুনরায় তৈরি করে।

### `veles doctor`
ইউজার-গ্লোবাল স্টেট এবং সক্রিয় প্রজেক্টের উপর হেলথ চেক চালায়। একটি সক্রিয়
প্রজেক্ট থাকা বা না থাকা — উভয় অবস্থায় কাজ করে।

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `--json` | off | একটি JSON রিপোর্ট প্রদান করে |
| `--strict` | off | যেকোনো ওয়ার্নিং-এ non-zero exit (CI গেটিং) |
| `--fix` | off | চেক করার আগে নিরাপদ মেরামতের চেষ্টা করে — বর্তমানে একটি ক্ষতিগ্রস্ত memory-recall (FTS) ইনডেক্স পুনর্নির্মাণ করে |

`doctor` `config.toml`-এর নিরাপত্তা-সংশ্লিষ্ট সেকশনগুলোও (`[channels.*]`,
`[daemon.*]`, `[mcp.servers.*]`) যাচাই করে এবং অজানা কী-কে একটি এরর হিসেবে রিপোর্ট
করে — `whitelist`-এর জায়গায় `whitlist`-এর মতো একটি টাইপো নীরবে একটি অ্যাক্সেস
কন্ট্রোল নিষ্ক্রিয় করে দেয়, তাই এখানে এটি জোরালোভাবে ব্যর্থ হয়।

### `veles export {full,template} <path>`
প্রজেক্টটিকে একটি `.tar.gz` বান্ডলে প্যাক করে। দেখুন [ব্যাকআপ ও শেয়ার করুন](../how-to/backup-and-share.md)।

- `full <path>` — সম্পূর্ণ প্রজেক্ট (`.veles/` + `AGENTS.md`), রানটাইম ক্ষণস্থায়ী ফাইল বাদে।
- `template <path>` — পরিশোধিত উপসেট (schema + skills + modules + non-session
  উইকি পৃষ্ঠা); `memory.db`, `sources/`, `sessions/`, `trust` গ্রান্ট সরিয়ে দেয়, এবং
  টেক্সট থেকে PII রিড্যাক্ট করে।

### `veles import <path>`
`veles export` দিয়ে তৈরি একটি বান্ডল পুনরুদ্ধার করে।

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `path` (positional) | — | বান্ডল পাথ (`.tar.gz`) |
| `--into <dir>` | cwd | টার্গেট ডিরেক্টরি |
| `--force` | off | টার্গেটে বিদ্যমান `.veles/` ওভাররাইট করে |

---

## এজেন্ট চালানো

### `veles run "<prompt>"`
মেমরি পার্সিস্টেন্স এবং কিউরেটর/লার্নিং ট্রিগারসহ একটি একক প্রম্পট
এন্ড-টু-এন্ড চালায়। সমস্ত [শেয়ার্ড এজেন্ট-লুপ ফ্ল্যাগ](#shared-agent-loop-flags) এবং এর সাথে:

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `--resume <session_id>` | new session | একটি বিদ্যমান সেশন চালিয়ে যায় |
| `--manager` | off | মাল্টি-এজেন্ট ম্যানেজারের মাধ্যমে বিভাজন করে (`VELES_MANAGER_MODE=1`-ও) |
| `--verify` | off | রানের পরে, রাউট করা advisor উত্তরটি বিচার করে; আত্মবিশ্বাসী ব্যর্থতায়, শক্তিশালী মডেলে পুনরায় চালায় (`VELES_VERIFY_MODE=1`-ও) |
| `--plan` | off | প্ল্যানিং মোড: read/search/draft অনুমোদিত, mutations ব্লক করা |
| `--no-agents-md` | off | সিস্টেম প্রম্পটে `AGENTS.md` ইনজেক্ট করে না |
| `--no-index` | off | `wiki/INDEX.md` ইনজেক্ট করে না |
| `--no-compress` | off | স্লাইডিং-উইন্ডো কনটেক্সট কম্প্রেশন নিষ্ক্রিয় করে |
| `--no-curator` | off | এই রানের জন্য কিউরেটর ট্রিগার নিষ্ক্রিয় করে |
| `--no-insights` | off | রান-পরবর্তী insight এক্সট্রাকশন নিষ্ক্রিয় করে |
| `--no-proposer` | off | সাবপ্রজেক্ট প্রপোজার অটো-ট্রিগার নিষ্ক্রিয় করে |
| `--no-route-refresh` | off | `AGENTS.md` থেকে NL রাউটিং রিফ্রেশ নিষ্ক্রিয় করে |
| `--no-suggest-promote` | off | অটো-প্রোমোট সাজেস্টার নিষ্ক্রিয় করে |
| `--compressor-model <id>` | routed | কম্প্রেশন মডেল ওভাররাইড করে |
| `--compress-threshold-tokens <n>` | `50000` | যে হিস্ট্রি সাইজে কম্প্রেশন শুরু হয় |

### `veles tui`
ইন্টারঅ্যাক্টিভ REPL খোলে। দেখুন [TUI রেফারেন্স](tui.md)। শেয়ার্ড এজেন্ট-লুপ
ফ্ল্যাগ, `--resume`, উপরের `--no-*` ইনজেকশন/কম্প্রেশন ফ্ল্যাগ এবং এর সাথে গ্রহণ করে:

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `--theme <name>` | config or `everforest` | কালার থিম (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
একটি সোর্স (একটি লোকাল ফাইল বা `http(s)://` URL) পড়ে এবং একটি উইকি পৃষ্ঠায়
সংশ্লেষ করে। শেয়ার্ড এজেন্ট-লুপ ফ্ল্যাগ গ্রহণ করে।

### `veles curate`
একটি কিউরেটর পাস চালায়: অপ্রসেসড সেশনগুলোকে `wiki/sessions/` পৃষ্ঠায় সংকুচিত করে।

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `--limit <n>` | a small default | এই রানে সর্বোচ্চ যত সেশন প্রসেস করা হবে |

এর সাথে শেয়ার্ড এজেন্ট-লুপ ফ্ল্যাগ।

### `veles research "<question>"`
ডিপ রিসার্চ: সাবকোয়েশ্চনে বিভাজন → সমান্তরালে ওয়েব অন্বেষণ →
উদ্ধৃতিসহ একটি রিপোর্ট সংশ্লেষ।

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `--max-subquestions <n>` | `4` | সমান্তরাল রিসার্চ অ্যাঙ্গেল |

এর সাথে শেয়ার্ড এজেন্ট-লুপ ফ্ল্যাগ।

### `veles dream`
একটি ব্যাকগ্রাউন্ড মেমরি-কনসলিডেশন সাইকেল চালায় (insights → skill dedup → promote
সাজেশন → wiki lint, ঐচ্ছিকভাবে LLM কনসলিডেশন)।

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `--include-consolidation` | off | ব্যয়বহুল LLM কনসলিডেশন চালায় (একটি API কী প্রয়োজন) |
| `--dry-run` | off | সব ধাপ চালায় কিন্তু `wiki/state` লেখা এড়িয়ে যায় |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | পৃথক ধাপ এড়িয়ে যায় |
| `--consolidation-model <id>` | routed (`anthropic/claude-haiku-4.5`-এ ফলব্যাক) | কনসলিডেশন মডেল ওভাররাইড করে |
| `--provider <name>` | routed | কনসলিডেশন সাব-এজেন্টের জন্য প্রোভাইডার (প্রজেক্টের রাউট করা প্রোভাইডার ব্যবহার করতে বাদ দিন) |
| `--project-root <path>` | discover | প্রজেক্ট ওভাররাইড |

---

## জ্ঞান: skills, tools, modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `list` | সক্রিয় প্রজেক্টের skills তালিকাভুক্ত করে (টেলিমেট্রিসহ) |
| `show <name>` | একটি skill-এর `SKILL.md` প্রিন্ট করে |
| `add <source> [--name N] [--scope project\|user] [-y]` | একটি git URL বা লোকাল পাথ থেকে ইনস্টল করে |
| `remove <name> [--scope project\|user] [-y]` | একটি ইনস্টল করা skill মুছে ফেলে |
| `promote <name> [--keep-telemetry]` | একটি প্রজেক্ট skill ইউজার স্কোপে কপি করে (`~/.veles/skills/`) |
| `demote <name> [-y]` | একটি ইউজার skill সক্রিয় প্রজেক্টে কপি করে |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | প্রায়-ডুপ্লিকেট skills খুঁজে বের করে |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | অটো-প্রোমোট মানদণ্ড পূরণ করা skills তালিকাভুক্ত করে |

### `veles tool {list,show,promote,approve}`

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `list` | এই প্রজেক্টের `memory.db`-তে ক্যাটালগ করা tools তালিকাভুক্ত করে |
| `show <name>` | একটি tool-এর ম্যানিফেস্ট + টেলিমেট্রি প্রিন্ট করে |
| `promote <name> [-y]` | একটি প্রজেক্ট tool `~/.veles/tools/`-এ সরায় (ক্রস-প্রজেক্ট) |
| `approve [<name>] [--all] [-y]` | একটি সেলফ-অথরড tool ফাইল রিভিউ + অনুমোদন করে যাতে লোডার এটি চালায় |

সেলফ-অথরড tools (`.veles/tools/*.py`) লোডার ইমপোর্ট করার সময় তাদের মডিউল-লেভেল
কোড চালায়, তাই একটি নতুন বা সম্পাদিত ফাইল **আপনি অনুমোদন না করা পর্যন্ত লোড হয়
না** — `veles tool approve` কোডটি দেখায় এবং এর হ্যাশ রেকর্ড করে। শুধু
`veles tool approve` কী কী পেন্ডিং আছে তা তালিকাভুক্ত করে। এই কারণেই একটি
এজেন্ট-লিখিত tool কলযোগ্য হওয়ার আগে একটি রিভিউ ধাপ প্রয়োজন।

### `veles module {list,show,add,remove}`

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `list` | ইনস্টল করা modules তালিকাভুক্ত করে |
| `show <name>` | একটি module-এর ম্যানিফেস্ট প্রিন্ট করে |
| `add <source> [--name N] [-y]` | একটি git URL বা লোকাল পাথ থেকে একটি module ইনস্টল করে |
| `remove <name> [-y]` | একটি ইনস্টল করা module মুছে ফেলে |

### `veles browse {modules,skills} [query]`
কিউরেটেড রেজিস্ট্রিগুলো ব্রাউজ করে।

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `query` (positional) | `""` | সাবস্ট্রিং ফিল্টার |
| `--source <url>` | canonical | রেজিস্ট্রি সোর্স ওভাররাইড করে |
| `--json` | off | JSON প্রদান করে |

---

## সেশন ও মেমরি

### `veles sessions {list,show,delete,search}`

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `list [--limit n]` | সাম্প্রতিক সেশন তালিকাভুক্ত করে (ডিফল্ট 20) |
| `show <session_id>` | একটি সেশনের সম্পূর্ণ টার্ন হিস্ট্রি প্রিন্ট করে |
| `delete <session_id>` | একটি সেশন এবং এর টার্ন মুছে ফেলে |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | টার্ন কন্টেন্টের উপর ফুল-টেক্সট (FTS5) সার্চ |

---

## মাল্টি-প্রজেক্ট

### `veles project {list,add,remove,switch}`

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `list` | নিবন্ধিত প্রজেক্ট তালিকাভুক্ত করে, সাম্প্রতিকতম প্রথমে |
| `add <path> [--slug S]` | একটি বিদ্যমান প্রজেক্ট ডিরেক্টরি নিবন্ধন করে |
| `remove <slug>` | একটি প্রজেক্ট আন-রেজিস্টার করে (ফাইল অক্ষত থাকে) |
| `switch <slug>` | প্রজেক্টের অ্যাবসোলিউট পাথ প্রিন্ট করে (`cd $(veles project switch <slug>)` ব্যবহার করুন) |

### `veles subproject {init,list,switch,remove,suggest}`

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `init <subdir> [--name N] [--description D]` | একটি সাবপ্রজেক্ট তৈরি + নিবন্ধন করে |
| `list` | সক্রিয় প্রজেক্টের সাবপ্রজেক্ট তালিকাভুক্ত করে |
| `switch <slug>` | একটি সাবপ্রজেক্টের অ্যাবসোলিউট পাথ প্রিন্ট করে |
| `remove <slug>` | একটি সাবপ্রজেক্ট আন-রেজিস্টার করে |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | থিম্যাটিক ক্লাস্টার শনাক্ত করে সাবপ্রজেক্ট প্রস্তাব করে |

---

## রাউটিং ও মডেল

### `veles route {show,set,reset,refresh}`
পার-টাস্ক ensemble রাউটিং — কোন `provider:model` প্রতিটি টাস্ক টাইপ
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`) সামলায়। দেখুন [পার-টাস্ক রাউটিং](../how-to/per-task-routing.md)।

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `show` | সক্রিয় প্রজেক্টের জন্য রিজলভ করা রাউটিং টেবিল প্রিন্ট করে |
| `set <task> <provider:model>` | একটি টাস্ককে একটি স্পেকে পিন করে |
| `reset [task]` | একটি টাস্ক (বা সব) ডিফল্টে রিসেট করে |
| `refresh [--force]` | `AGENTS.md` থেকে ন্যাচারাল-ল্যাঙ্গুয়েজ রাউটিং হিন্ট পুনরায় পার্স করে |

### `veles models <provider>`
একটি প্রোভাইডারের মডেল তালিকাভুক্ত করে। ক্লাউড প্রোভাইডার (openrouter/openai/gemini)
24 ঘণ্টা ক্যাশ করা হয়; লোকাল প্রোভাইডার সর্বদা লাইভ।

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `provider` (positional) | — | [প্রোভাইডার নাম](#provider-names)-এর একটি |
| `--refresh` | off | ডিস্ক ক্যাশ বাইপাস করে (শুধু ক্লাউড) |
| `--json` | off | `{provider, source, models}` JSON হিসেবে প্রদান করে |

---

## দীর্ঘমেয়াদী টাস্ক

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
বাজেট ও চেকপয়েন্টসহ দীর্ঘ-দিগন্তের লক্ষ্য।

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | লক্ষ্য তালিকাভুক্ত করে |
| `show <id> [--json]` | একটি লক্ষ্য দেখায় |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | একটি লক্ষ্য তৈরি করে |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | অগ্রগতি যোগ করে |
| `pause <id>` / `resume <id>` | বিরতি / পুনরায় শুরু |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | সমাপ্ত / বাতিল |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
শিডিউল করা এজেন্ট জব।

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | একটি জব তৈরি করে (schedule = cron, `<N><s\|m\|h\|d>`, বা ISO timestamp) |
| `list [--json]` / `show <id>` | জব পরিদর্শন করে |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | লাইফসাইকেল |
| `history <id> [--limit n]` | সাম্প্রতিক রান |
| `tick` | সব ডিউ জব একবার সিনক্রোনাসভাবে চালায় (কোনো ডিমন প্রয়োজন নেই; এজেন্ট-লুপ ফ্ল্যাগ গ্রহণ করে) |

---

## নিরাপত্তা ও অ্যাক্সেস কন্ট্রোল

### `veles trust {list,set,revoke,clear}`
সংবেদনশীল tools-এর (`run_shell`, `write_file`, `fetch_url`, …) জন্য পার্সিস্টেড গ্রান্ট।
দেখুন [নিরাপত্তা](../how-to/security-and-permissions.md)।

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `list` | গ্রান্ট দেখায় (user + project স্কোপ) |
| `set <tool> [--scope project\|user]` | একটি tool গ্রান্ট করে |
| `revoke <tool> [--scope project\|user\|both]` | একটি গ্রান্ট সরায় |
| `clear [--scope project\|user\|all]` | একটি স্কোপে গ্রান্ট মুছে ফেলে |

### `veles autopilot {enable,disable,status}`
একটি সময়-সীমিত উইন্ডো যেখানে trust-ladder প্রম্পট স্বয়ংক্রিয়ভাবে অনুমোদিত হয়।

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `enable --until <DUR>` | একটি উইন্ডো খোলে (`+30m`, `+2h`, `+1d`, বা ISO `2026-05-12T18:00:00Z`) |
| `disable` | এখনই উইন্ডো বন্ধ করে |
| `status` | অটোপাইলট সক্রিয় কিনা রিপোর্ট করে |

### `veles secret {set,get,list,delete}`
OS-keychain-সমর্থিত সিক্রেট (API কী, বট টোকেন)।

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `set <name> [value]` | সংরক্ষণ করে (ইন্টারঅ্যাক্টিভ / stdin-এর জন্য value বাদ দিন) |
| `get <name> [--reveal] [--no-env-fallback]` | খুঁজে বের করে (ডিফল্টভাবে env ফলব্যাক) |
| `list` | কোন canonical সিক্রেটগুলো কনফিগার করা আছে দেখায় |
| `delete <name>` | একটি সিক্রেট সরায় |

---

## ডিমন ও চ্যানেল

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
HTTP+WS ডিমন চালায়/নিয়ন্ত্রণ করে। শুধু `veles daemon` **ডিমন পিকার**
TUI খোলে (project → daemons → channels)। দেখুন [ডিমন হিসেবে চালান](../how-to/run-as-daemon.md)।

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | একটি ডিমন চালু করে (ডিফল্টভাবে ডিট্যাচ করে) |
| `stop [--name N]` / `status [--name N]` | বন্ধ / পরিদর্শন |
| `list` | সব প্রজেক্ট জুড়ে ডিমন তালিকাভুক্ত করে |
| `restart [target] [--name N]` | একই host/port-এ বন্ধ + পুনরায় চালু |
| `delete <target> [-y]` | বন্ধ + রেজিস্ট্রি থেকে সরায় |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | একটি নামকৃত ডিমন সেশন ঘোষণা করে |
| `session list [--all]` / `session delete <name>` | নামকৃত সেশন পরিচালনা করে |
| `token add <name>` / `token list` / `token remove <name>` | Bearer-token CRUD |

`start` শেয়ার্ড এজেন্ট-লুপ ফ্ল্যাগও গ্রহণ করে; ডিমনের জন্য, `--model` /
`--provider` প্রজেক্ট কনফিগে ডিফল্ট হয় এবং ডিমনের পুরো জীবনকালের জন্য নির্দিষ্ট থাকে।

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
এক্সটার্নাল চ্যাট গেটওয়ে (Telegram, …) যা একটি ডিমনের সাথে কথা বলে। দেখুন
[Telegram সংযুক্ত করুন](../how-to/connect-telegram.md)।

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `list` | নিবন্ধিত চ্যানেল প্ল্যাটফর্ম + সেশন সংখ্যা তালিকাভুক্ত করে |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | ফোরগ্রাউন্ডে একটি গেটওয়ে চালু করে |
| `list-sessions [--channel C]` | `chat_id → session_id` ম্যাপিং দেখায় |
| `reset-session <chat_id> [--channel C]` | একটি ম্যাপিং ভুলে যায় (পরের মেসেজ নতুনভাবে শুরু হয়) |
| `add [--channel C] [--session S]` | একটি চ্যানেল একটি ডিমনের সাথে সংযুক্ত করে (উইজার্ড; creds → keychain) |
| `remove <channel> [--session S]` | একটি চ্যানেল বাইন্ডিং সরায় |

---

## MCP (এক্সটার্নাল টুল সার্ভার)

### `veles mcp {list,test}`
`[mcp.servers.*]`-এর অধীনে কনফিগার করা এক্সটার্নাল MCP সার্ভার পরিদর্শন করে। দেখুন
[এক্সটার্নাল MCP সার্ভার](../how-to/external-mcp-servers.md)।

| সাবকমান্ড | উদ্দেশ্য |
|---|---|
| `list [--connect-timeout f]` | কনফিগার করা সার্ভার, কানেকশন স্ট্যাটাস, টুল সংখ্যা দেখায় |
| `test <server>` | একটি সার্ভারে সংযুক্ত হয় এবং এর tools তালিকাভুক্ত করে |

---

## শেয়ার্ড এজেন্ট-লুপ ফ্ল্যাগ

`run`, `add`, `tui`, `curate`, `research`, `job tick`, এবং `daemon
start`-এ গৃহীত:

| ফ্ল্যাগ | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `--model <id>` | প্রজেক্ট `[engine]` model → user `default_model` থেকে রিজলভড (কোনো হার্ডকোডেড ডিফল্ট নেই) | মডেল ID |
| `--provider <name>` | `openrouter` | প্রোভাইডার (নিচে দেখুন) |
| `--max-tokens-total <n>` | `100000` | ক্রমবর্ধমান টোকেন বাজেট; `0` নিষ্ক্রিয় করে |
| `--max-iterations <n>` | `1000` | প্রতি টার্নে সর্বোচ্চ টুল-কলিং ইটারেশন |
| `--stream` | off | টোকেন-বাই-টোকেন রেসপন্স স্ট্রিম করে |
| `--verbose` / `-v` | off | stderr-এ প্রতি-টার্ন অগ্রগতি |
| `--project-root <path>` | cwd থেকে discover | অন্যত্র একটি প্রজেক্টে কাজ করে |

## প্রোভাইডার নাম

`openrouter` (default) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

লোকাল প্রোভাইডারগুলোর (`ollama`, `llamacpp`, `openai-compat`) কোনো API কী লাগে না। দেখুন
[প্রোভাইডার রেফারেন্স](providers.md) এবং [প্রোভাইডার কনফিগার করুন](../how-to/configure-providers.md)।
