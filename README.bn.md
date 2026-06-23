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
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <b>বাংলা</b> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**একটি ন্যূনতম CLI এজেন্ট ফ্রেমওয়ার্ক যা প্রতিটি সেশনের সাথে আরও স্মার্ট হয়ে ওঠে।**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles TUI — একটি প্রশ্ন করুন, প্রকল্পের নিজস্ব মেমরিতে ভিত্তি করে একটি উত্তর পান" width="800">
</p>

যেসব চ্যাট টুল প্রতিবার নতুন করে শুরু হয় তাদের বিপরীতে, Veles একটি **কাঠামোবদ্ধ প্রকল্প মেমরি** বজায় রাখে — অন্তর্দৃষ্টি (insights), নিয়ম এবং সংকলিত জ্ঞান যা সেশনের পর সেশন জমা হতে থাকে এবং আপনি যত বেশি সময় ব্যবহার করবেন এজেন্টকে তত বেশি কাজে লাগায়। আপনার *কনটেন্ট* কীভাবে সংগঠিত হবে তা প্লাগেবল: ডিফল্টভাবে একটি Karpathy-স্টাইল LLM উইকি, ফ্ল্যাট নোট, অথবা কোড রিপোজিটরির জন্য কোনো কাঠামো ছাড়াই। পরিষ্কারভাবে নির্মিত: কোনো god-file নেই, কোনো vendor lock-in নেই, কোনো ক্লাউড সিঙ্ক নেই।

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (bare `veles` == `veles tui`)
```

---

## Veles কেন?

**ক্রমবর্ধমান মেমরি** — প্রতিটি সেশন Curator দ্বারা প্রকল্প-ভিত্তিক মেমরিতে পরিশোধিত হয় (অন্তর্দৃষ্টি, আচরণগত নিয়ম, `.veles/`-এ সেশন ডাইজেস্ট)। এজেন্ট প্রাসঙ্গিক তথ্য এবং অতীত সিদ্ধান্ত স্বয়ংক্রিয়ভাবে স্মরণ করে — আপনি বারবার একই প্রেক্ষাপট ব্যাখ্যা করা বন্ধ করেন। মেমরি *যেকোনো* কনটেন্ট লেআউটের অধীনে কাজ করে।

**প্লাগেবল কনটেন্ট লেআউট** — `veles init` ডিফল্টভাবে একটি Karpathy-স্টাইল LLM উইকি স্ক্যাফোল্ড করে; `--layout notes` একটি ফ্ল্যাট নোট ডিরেক্টরি দেয়; `--layout bare` কোনো কাঠামো যোগ করে না (কোড রিপোজিটরির জন্য আদর্শ)। কাস্টম লেআউট প্যাক হলো `~/.veles/layouts/`-এ একটি একক TOML ফাইল।

**প্রোভাইডার-নিরপেক্ষ রাউটিং** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp, অথবা আপনার `claude`/`gemini` CLI সাবস্ক্রিপশন। বিভিন্ন ধরনের কাজ (পরিকল্পনা, কম্প্রেশন, অন্তর্দৃষ্টি) বিভিন্ন মডেলে রাউট করা যায়।

**জমা হতে থাকা স্কিল** — পুনঃব্যবহারযোগ্য প্রম্পট-ব্লক এজেন্ট টুলে পরিণত হয়। একটি স্কিলকে প্রকল্প থেকে user-global-এ প্রমোট করুন এবং তা সর্বত্র উপলব্ধ হয়। বিল্ট-ইন dedup স্কিলগুলো বিচ্যুত হওয়ার আগেই কাছাকাছি-ডুপ্লিকেট স্কিল খুঁজে বের করে।

**লোকাল-ফার্স্ট + স্যান্ডবক্সড** — কোনো টেলিমেট্রি নেই, কোনো ক্লাউড সিঙ্ক নেই। এজেন্ট শুধুমাত্র সক্রিয় প্রকল্প ডিরেক্টরি দেখতে পায়। ট্রাস্ট ল্যাডার প্রতিটি সংবেদনশীল টুল কলের জন্য জিজ্ঞাসা করে; CI-এর জন্য আগেভাগে অনুমতি দিন।

**মডিউলার, মনোলিথিক নয়** — ন্যূনতম কোর (মেমরি, এজেন্ট লুপ, প্রোভাইডার প্রোটোকল, টুল রেজিস্ট্রি)। বাকি সবকিছু — TUI, ডেমন, Telegram গেটওয়ে, গভীর গবেষণা, জব শিডিউলার — একটি ঐচ্ছিক, লোডযোগ্য মডিউল।

---

## দ্রুত শুরু

**প্রয়োজনীয়তা:** Python 3.13+, macOS / Linux (Windows best-effort)। প্রথমে [uv](https://docs.astral.sh/uv/) ইনস্টল করুন।

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

পরিবর্তে ইন্টারঅ্যাকটিভ TUI খুলুন (খালি `veles` একই কাজ করে):

```bash
veles
```

প্রথমবার চালানোর সময়, একটি সেটআপ উইজার্ড আপনার পছন্দের ভাষা, প্রোভাইডার এবং প্রকল্পের নাম জিজ্ঞাসা করবে।

---

## প্রোভাইডার

| প্রোভাইডার | এনভায়রনমেন্ট ভেরিয়েবল | নোট |
|---|---|---|
| **OpenRouter** *(প্রস্তাবিত)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — একটি কী, শত শত মডেল |
| Anthropic | `ANTHROPIC_API_KEY` | সরাসরি API |
| OpenAI | `OPENAI_API_KEY` | সরাসরি API |
| Gemini | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | সরাসরি API |
| `claude` CLI | — | আপনার Claude সাবস্ক্রিপশন ব্যবহার করে; কোনো API কী লাগে না |
| `gemini` CLI | — | আপনার Gemini সাবস্ক্রিপশন ব্যবহার করে; কোনো API কী লাগে না |
| Ollama | — | লোকাল মডেল, `http://localhost:11434/v1` |
| llamacpp | — | লোকাল মডেল, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | যেকোনো OpenAI-সামঞ্জস্যপূর্ণ এন্ডপয়েন্ট |

প্রতি-রান ওভাররাইড করুন:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

এনভায়রনমেন্ট ভেরিয়েবলের পরিবর্তে OS কীচেইনে API কী সংরক্ষণ করুন:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## মূল ওয়ার্কফ্লো

### একটি কনটেন্ট লেআউট বেছে নিন

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

এজেন্টের নিজস্ব মেমরি (অন্তর্দৃষ্টি, নিয়ম, `.veles/`-এ সেশন ডাইজেস্ট) প্রতিটি লেআউটের অধীনে একইভাবে কাজ করে। কাস্টম প্যাক হলো `~/.veles/layouts/<name>/`-এ একটি `layout.toml`।

### একটি জ্ঞানভাণ্ডার তৈরি করুন (llm-wiki লেআউট)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Veles জ্ঞানভাণ্ডার — একটি সোর্সকে উইকি পৃষ্ঠায় ইনজেস্ট করুন, তারপর একটি প্রশ্ন করুন এবং সেটি উদ্ধৃত করে এমন একটি উত্তর পান" width="800">
</p>

সেশনের পরে Curator স্বয়ংক্রিয়ভাবে চলে। অন্তর্দৃষ্টি নিষ্কাশন "always prefer X" বা "never do Y"-এর মতো বাক্যাংশ ধরে এবং সেগুলো স্থায়ী প্রকল্প অন্তর্দৃষ্টি হিসেবে লিখে রাখে।

### গভীর গবেষণা

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

প্রশ্নটিকে সমান্তরাল উপ-প্রশ্নে বিভক্ত করে, প্রতিটি অন্বেষণ করে, এবং একটি কাঠামোবদ্ধ প্রতিবেদন সংশ্লেষণ করে।

### দীর্ঘমেয়াদী লক্ষ্য

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### নির্ধারিত জব

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## মডেল রাউটিং (Ensembles)

বিভিন্ন ধরনের কাজ বিভিন্ন মডেলে রাউট করুন — একবার সেট করুন এবং ভুলে যান।

**CLI-এর মাধ্যমে:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**`AGENTS.md`-এ প্রাকৃতিক ভাষার মাধ্যমে:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## স্কিল এবং মডিউল

**স্কিল** হলো পুনঃব্যবহারযোগ্য প্রম্পট-ব্লক (`SKILL.md`) যা স্বয়ংক্রিয়ভাবে এজেন্ট টুলে পরিণত হয়।

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**মডিউল** হলো Python প্লাগইন যা এজেন্ট লাইফসাইকেলে হুক করতে পারে (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) এবং টুল ডিসপ্যাচ ভেটো করতে পারে।

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## TUI

```bash
veles                        # new session (bare `veles` launches the TUI)
veles tui --resume <id>      # continue a session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="Veles TUI — স্ল্যাশ ইন্সপেক্টর (/status, /context), মোড পরিবর্তন, এবং কমান্ড প্যালেট" width="800">
</p>

স্ল্যাশ কমান্ড সবকিছু লাইভ দেখায় — `/status`, `/tokens`, `/context`, `/mode`, `/help` — এবং `Shift+Tab` মোডের মধ্যে ঘোরে (auto / planning / writing / goal)।

| কী | কাজ |
|---|---|
| `Enter` | বার্তা পাঠান |
| `Shift+Enter` | কম্পোজারে নতুন লাইন |
| `Ctrl+I` | টুল-অ্যাক্টিভিটি ইন্সপেক্টর টগল করুন |
| `Ctrl+R` | সেশন পিকার ওভারলে |
| `Ctrl+G` | বর্তমান খসড়ায় `$EDITOR` খুলুন |
| `Tab` | স্ল্যাশ-কমান্ড অটোকমপ্লিট |
| `Ctrl+D` | প্রস্থান করুন |

স্ল্যাশ কমান্ড: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` এবং আরও অনেক।

---

## ডেমন + Telegram

একটি HTTP/WebSocket API সহ Veles-কে একটি স্থায়ী ডেমন হিসেবে চালান। একটি নতুন প্রকল্প ডিরেক্টরিতে, `veles daemon start` আপনাকে সেটআপের মধ্য দিয়ে নিয়ে যায় — প্রকল্প ইনিশিয়ালাইজ করা, ডেমন সক্রিয় করা, এবং **একটি চ্যানেল সংযুক্ত করা**: প্রথমে একটি চ্যানেল *টাইপ* বেছে নিন (Telegram আজকের একমাত্র প্ল্যাটফর্ম, তবে পিকার হলো সেই সংযোগস্থল যেখানে নতুন চ্যানেল নিবন্ধিত হয়), তারপর সেই চ্যানেলের ফিল্ডগুলো পূরণ করুন (বট টোকেন, হোয়াইটলিস্ট)। প্রথমে TUI খোলার দরকার নেই।

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — উইজার্ড যা ডেমন চালু করে এবং একটি Telegram চ্যানেল সংযুক্ত করে (প্রথমে চ্যানেল টাইপ, তারপর এর টোকেন ও হোয়াইটলিস্ট)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

খালি `veles daemon` একটি লাইভ কন্ট্রোল প্যানেল খোলে — প্রকল্প → ডেমন → চ্যানেলের একটি ট্রি। কীবোর্ড থেকেই প্রতিটি প্রকল্প জুড়ে ডেমন শুরু, বন্ধ, রিস্টার্ট বা ডিলিট করুন এবং চ্যানেল যোগ/অপসারণ করুন (একই চ্যানেল-টাইপ-প্রথম প্রবাহ, কী `c`):

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — কন্ট্রোল-প্যানেল TUI: start/stop/restart/delete এবং ইনলাইন চ্যানেল ব্যবস্থাপনা সহ একটি প্রকল্প → ডেমন → চ্যানেল ট্রি" width="800">
</p>

একই চ্যানেল উইজার্ড একটি ইতিমধ্যে-চলমান প্রকল্পে স্বতন্ত্রভাবেও (`veles channel add`) উপলব্ধ।

API এন্ডপয়েন্ট: একটি প্রম্পট জমা দিতে `POST /v1/runs`, রেসপন্স স্ট্রিম করতে `WS /v1/runs/{id}/events`, সেশন তালিকাভুক্ত করতে `GET /v1/sessions`। `GET /v1/health` ছাড়া বাকি সবগুলোর জন্য `Authorization: Bearer <token>` প্রয়োজন (`veles daemon token add <name>` দিয়ে একটি তৈরি করুন)।

প্রতিটি Telegram ব্যবহারকারী একটি স্থায়ী সেশন পান। ম্যাপিং ব্যবস্থাপনার জন্য `veles channel list-sessions` / `reset-session` ব্যবহার করুন।

---

## মাল্টি-প্রজেক্ট

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## ট্রাস্ট ও নিরাপত্তা

প্রতিটি সংবেদনশীল টুল কল (শেল এক্সিকিউশন, ফাইল রাইট, URL ফেচ) জিজ্ঞাসা করে:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

CI বা দীর্ঘস্থায়ী স্বায়ত্তশাসিত রানের জন্য আগেভাগে অনুমতি দিন:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

এজেন্ট শুধুমাত্র সক্রিয় প্রকল্প ডিরেক্টরি দেখতে পায় — অন্যান্য প্রকল্প, সিমলিংক এস্কেপ এবং `..` ট্রাভার্সাল ব্লক করা থাকে।

---

## এক্সপোর্ট / ইমপোর্ট

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## CLI রেফারেন্স

| কমান্ড | উদ্দেশ্য |
|---|---|
| `veles init [name]` | একটি নতুন প্রকল্প তৈরি করুন |
| `veles run "<prompt>"` | একক-টার্ন এজেন্ট রান |
| `veles tui` | ইন্টারঅ্যাকটিভ TUI REPL |
| `veles add <file\|url>` | একটি সোর্স ইনজেস্ট করুন → উইকি পৃষ্ঠা |
| `veles research "<question>"` | গভীর বহুমাত্রিক গবেষণা |
| `veles curate` | সেশনগুলোকে উইকিতে একত্রীকরণ করুন |
| `veles sessions {list,show,delete,search}` | সেশন ব্যবস্থাপনা |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | স্কিল ব্যবস্থাপনা |
| `veles tool {list,show,promote}` | টুল ব্যবস্থাপনা |
| `veles module {list,add,remove}` | প্লাগইন ব্যবস্থাপনা |
| `veles route {show,set,reset,refresh}` | মডেল রাউটিং |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | দীর্ঘমেয়াদী লক্ষ্য |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | নির্ধারিত জব |
| `veles dream` | ব্যাকগ্রাউন্ড মেমরি-একত্রীকরণ চক্র |
| `veles project {list,add,remove,switch}` | মাল্টি-প্রজেক্ট রেজিস্ট্রি |
| `veles subproject {init,list,switch,remove,suggest}` | চাইল্ড প্রকল্প |
| `veles trust {list,set,revoke,clear}` | ট্রাস্ট অনুমোদন |
| `veles autopilot {enable,disable,status}` | অস্থায়ী ট্রাস্ট বাইপাস |
| `veles secret {set,get,list,delete}` | OS-কীচেইন সিক্রেট |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | HTTP/WS ডেমন |
| `veles channel {run,list-sessions,reset-session}` | বাহ্যিক চ্যানেল গেটওয়ে |
| `veles mcp {list,test}` | বাহ্যিক MCP সার্ভার |
| `veles models <provider>` | প্রোভাইডার মডেল তালিকাভুক্ত করুন |
| `veles doctor` | স্বাস্থ্য পরীক্ষা |
| `veles export / import` | প্রকল্প ব্যাকআপ ও স্থানান্তর |

প্রতিটি কমান্ডে `--help` আছে।

---

## ডকুমেন্টেশন

সম্পূর্ণ ডকুমেন্টেশন — Diátaxis-সংগঠিত (টিউটোরিয়াল · হাউ-টু গাইড · রেফারেন্স · ব্যাখ্যা):

- **বাংলা:** [`docs/bn/index.md`](docs/bn/index.md)

অন্যান্য ভাষা: যেকোনো ডকুমেন্টেশন পৃষ্ঠার শীর্ষে থাকা 🌐 সুইচার ব্যবহার করুন।

---

## অবদান

অবদান খুবই স্বাগত — Veles **সম্প্রসারণের জন্য নির্মিত**। কোর ছোট থাকে (এজেন্ট লুপ + প্রকল্প মেমরি + প্রোভাইডার প্রোটোকল); বাকি প্রায় সবকিছুই একটি প্লাগেবল এক্সটেনশন পয়েন্ট, তাই একটি সক্ষমতা যোগ করা খুব কমই কোর স্পর্শ করা বোঝায়:

- **প্রোভাইডার অ্যাডাপ্টার** (`src/veles/adapters/`) — একটি নতুন মডেল ব্যাকএন্ড যুক্ত করুন।
- **স্কিল** — `extends:` ইনহেরিট্যান্স সহ পুনঃব্যবহারযোগ্য প্রম্পট-ব্লক ও টুল, প্রকল্প থেকে user-global-এ প্রমোটযোগ্য।
- **টুল** — টাইপড Python যা এজেন্ট লেখে ও পুনঃব্যবহার করে, `<project>/.veles/tools/`-এর অধীনে।
- **লেআউট প্যাক** — `~/.veles/layouts/<name>/`-এ একটি একক `layout.toml` একটি সম্পূর্ণ কনটেন্ট লেআউট সংজ্ঞায়িত করে।
- **মডিউল হুক** — `pre_turn` / `post_turn` হুকের মাধ্যমে পর্যবেক্ষণযোগ্যতা, লগিং এবং নীতি (`src/veles/core/modules.py`)।
- **চ্যানেল ও MCP সার্ভার** — নতুন গেটওয়ে এবং বাহ্যিক টুল সোর্স।
- **লোকেল** — `src/veles/locales/`-এ অনুবাদ।

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

কোডবেসটি ইচ্ছাকৃতভাবে বিভক্ত — একক দায়িত্ব, কোনো god-file নেই। একটি PR খোলার আগে কনভেনশনের জন্য [`CONTRIBUTING.md`](CONTRIBUTING.md) এবং [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) পড়ুন। ভালো প্রথম অবদান: প্রোভাইডার অ্যাডাপ্টার, ওয়ার্কফ্লো স্কিল, মডিউল হুক এবং লোকেল ফাইল।

---

## লাইসেন্স

Apache 2.0 প্যাটেন্ট গ্রান্ট সহ — দেখুন [`LICENSE`](LICENSE) এবং [`NOTICE`](NOTICE)।
