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
  <b>हिन्दी</b> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**एक मिनिमल CLI एजेंट फ्रेमवर्क जो हर सेशन के साथ और स्मार्ट होता जाता है।**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles TUI — एक सवाल पूछें, और प्रोजेक्ट की अपनी memory पर आधारित जवाब पाएं" width="800">
</p>

उन चैट टूल्स के विपरीत जो हर बार शून्य से शुरू होते हैं, Veles **संरचित प्रोजेक्ट memory** बनाए रखता है — insights, rules, और curated knowledge जो सेशनों के बीच जमा होते रहते हैं और जितना ज़्यादा आप इसका इस्तेमाल करते हैं, एजेंट उतना ही उपयोगी बनता जाता है। आपका *content* कैसे व्यवस्थित होता है, यह pluggable है: डिफ़ॉल्ट रूप से Karpathy-शैली का LLM wiki, flat notes, या कोड रिपॉज़ के लिए बिल्कुल भी कोई संरचना नहीं। साफ़-सुथरा बनाया गया: कोई god-files नहीं, कोई vendor lock-in नहीं, कोई cloud sync नहीं।

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (bare `veles` == `veles tui`)
```

---

## Veles क्यों?

**संचयी memory** — हर सेशन को Curator द्वारा per-project memory में distill किया जाता है (insights, behavioral rules, और `.veles/` में session digests)। एजेंट प्रासंगिक तथ्यों और पिछले निर्णयों को स्वतः याद रखता है — आपको वही context बार-बार समझाना नहीं पड़ता। Memory *किसी भी* content layout के तहत काम करती है।

**Pluggable content layouts** — `veles init` डिफ़ॉल्ट रूप से एक Karpathy-शैली का LLM wiki तैयार करता है; `--layout notes` एक flat notes डायरेक्टरी देता है; `--layout bare` कोई संरचना नहीं जोड़ता (कोड रिपॉज़ के लिए आदर्श)। कस्टम layout packs `~/.veles/layouts/` में एक ही TOML फ़ाइल होते हैं।

**Provider-स्वतंत्र routing** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp, या आपका `claude`/`gemini` CLI subscription। अलग-अलग task types (planning, compression, insights) अलग-अलग models पर route हो सकते हैं।

**संचयी होने वाली Skills** — पुनः-प्रयोग योग्य prompt-blocks एजेंट के tools बन जाते हैं। किसी skill को project से user-global में promote करें और वह हर जगह उपलब्ध हो जाती है। बिल्ट-इन dedup near-duplicate skills को drift करने से पहले ढूँढ लेता है।

**Local-first + sandboxed** — कोई telemetry नहीं, कोई cloud sync नहीं। एजेंट केवल सक्रिय project डायरेक्टरी को ही देखता है। Trust ladder हर संवेदनशील tool call के लिए पूछता है; CI के लिए पहले से grant करें।

**Modular, monolithic नहीं** — मिनिमल core (memory, agent loop, provider protocol, tool registry)। बाकी सब कुछ — TUI, daemon, Telegram gateway, deep research, job scheduler — एक वैकल्पिक, loadable module है।

---

## Quick Start

**आवश्यकताएँ:** Python 3.13+, macOS / Linux (Windows best-effort)। पहले [uv](https://docs.astral.sh/uv/) इंस्टॉल करें।

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

इसके बजाय interactive TUI खोलें (खाली `veles` यही करता है):

```bash
veles
```

पहली बार चलाने पर, एक setup wizard आपकी पसंदीदा भाषा, provider, और project name पूछेगा।

---

## Providers

| Provider | Env var | टिप्पणियाँ |
|---|---|---|
| **OpenRouter** *(अनुशंसित)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — एक key, सैकड़ों models |
| Anthropic | `ANTHROPIC_API_KEY` | Direct API |
| OpenAI | `OPENAI_API_KEY` | Direct API |
| Gemini | `GEMINI_API_KEY` या `GOOGLE_API_KEY` | Direct API |
| `claude` CLI | — | आपके Claude subscription का उपयोग करता है; कोई API key नहीं चाहिए |
| `gemini` CLI | — | आपके Gemini subscription का उपयोग करता है; कोई API key नहीं चाहिए |
| Ollama | — | Local models, `http://localhost:11434/v1` |
| llamacpp | — | Local models, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | कोई भी OpenAI-compatible endpoint |

प्रति-run override करें:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

environment variables के बजाय API keys को OS keychain में स्टोर करें:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## Core Workflow

### एक content layout चुनें

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

एजेंट की अपनी memory (`.veles/` में insights, rules, session digests) हर layout के तहत एक समान काम करती है। कस्टम packs `~/.veles/layouts/<name>/` में एक `layout.toml` होते हैं।

### एक knowledge base बनाएं (llm-wiki layout)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Veles knowledge base — किसी source को wiki page में ingest करें, फिर एक सवाल पूछें और ऐसा जवाब पाएं जो उसका हवाला देता हो" width="800">
</p>

Curator सेशनों के बाद स्वतः चलता है। Insight extraction "always prefer X" या "never do Y" जैसे वाक्यांशों को पकड़ लेता है और उन्हें स्थायी project insights के रूप में लिखता है।

### Deep research

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

सवाल को समानांतर sub-questions में विघटित करता है, हर एक को explore करता है, और एक संरचित report संश्लेषित करता है।

### लंबे समय तक चलने वाले goals

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### Scheduled jobs

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## Model Routing (Ensembles)

अलग-अलग task types को अलग-अलग models पर route करें — एक बार सेट करें और भूल जाएँ।

**CLI के ज़रिए:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**`AGENTS.md` में प्राकृतिक भाषा के ज़रिए:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## Skills और Modules

**Skills** पुनः-प्रयोग योग्य prompt-blocks (`SKILL.md`) हैं जो स्वतः एजेंट के tools बन जाते हैं।

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**Modules** Python plugins हैं जो एजेंट lifecycle (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) में hook कर सकते हैं और tool dispatches को veto कर सकते हैं।

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
  <img src="docs/assets/tui-tour.gif" alt="Veles TUI — slash inspectors (/status, /context), mode switching, और command palette" width="800">
</p>

Slash commands सब कुछ live दिखाते हैं — `/status`, `/tokens`, `/context`, `/mode`, `/help` — और `Shift+Tab` modes को cycle करता है (auto / planning / writing / goal)।

| Key | क्रिया |
|---|---|
| `Enter` | संदेश भेजें |
| `Shift+Enter` | composer में नई लाइन |
| `Ctrl+I` | tool-activity inspector toggle करें |
| `Ctrl+R` | session picker overlay |
| `Ctrl+G` | वर्तमान draft पर `$EDITOR` खोलें |
| `Tab` | Slash-command autocomplete |
| `Ctrl+D` | बाहर निकलें |

Slash commands: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` और बहुत कुछ।

---

## Daemon + Telegram

Veles को एक स्थायी daemon के रूप में HTTP/WebSocket API के साथ चलाएँ। एक नई project डायरेक्टरी में, `veles daemon start` आपको setup के दौरान मार्गदर्शन देता है — project को initialize करें, daemon को enable करें, और **एक channel connect करें**: पहले एक channel *type* चुनें (आज Telegram एकमात्र platform है, पर picker वह seam है जिस पर नए channels register होते हैं), फिर उस channel के fields भरें (bot token, whitelist)। पहले TUI खोलने की ज़रूरत नहीं है।

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — wizard जो daemon को चालू करता है और एक Telegram channel connect करता है (पहले channel type, फिर उसका token और whitelist)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

खाली `veles daemon` एक live control panel खोलता है — project → daemons → channels का एक tree। हर project में daemons को start, stop, restart, या delete करें, और channels जोड़ें/हटाएँ (वही channel-type-first flow, key `c`), सब कुछ कीबोर्ड से:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — control-panel TUI: start/stop/restart/delete और inline channel management के साथ एक project → daemons → channels tree" width="800">
</p>

वही channel wizard पहले से चल रहे project पर standalone रूप में भी उपलब्ध है (`veles channel add`)।

API endpoints: prompt submit करने के लिए `POST /v1/runs`, response को stream करने के लिए `WS /v1/runs/{id}/events`, sessions की सूची के लिए `GET /v1/sessions`। `GET /v1/health` को छोड़कर सभी को `Authorization: Bearer <token>` चाहिए (`veles daemon token add <name>` से एक बनाएँ)।

हर Telegram user को एक स्थायी session मिलता है। mappings प्रबंधित करने के लिए `veles channel list-sessions` / `reset-session` का उपयोग करें।

---

## Multi-project

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## Trust और Safety

हर संवेदनशील tool call (shell execution, file writes, URL fetches) पूछता है:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

CI या लंबे autonomous runs के लिए पहले से grant करें:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

एजेंट केवल सक्रिय project डायरेक्टरी को ही देखता है — अन्य projects, symlink escapes, और `..` traversal blocked हैं।

---

## Export / Import

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## CLI Reference

| Command | उद्देश्य |
|---|---|
| `veles init [name]` | एक नया project बनाएँ |
| `veles run "<prompt>"` | Single-turn agent run |
| `veles tui` | Interactive TUI REPL |
| `veles add <file\|url>` | एक source को ingest करें → wiki page |
| `veles research "<question>"` | Deep multi-angle research |
| `veles curate` | सेशनों को wiki में consolidate करें |
| `veles sessions {list,show,delete,search}` | Session management |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | Skill management |
| `veles tool {list,show,promote}` | Tool management |
| `veles module {list,add,remove}` | Plugin management |
| `veles route {show,set,reset,refresh}` | Model routing |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Long-horizon goals |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Scheduled jobs |
| `veles dream` | Background memory-consolidation cycle |
| `veles project {list,add,remove,switch}` | Multi-project registry |
| `veles subproject {init,list,switch,remove,suggest}` | Child projects |
| `veles trust {list,set,revoke,clear}` | Trust grants |
| `veles autopilot {enable,disable,status}` | Temporary trust bypass |
| `veles secret {set,get,list,delete}` | OS-keychain secrets |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | HTTP/WS daemon |
| `veles channel {run,list-sessions,reset-session}` | External channel gateway |
| `veles mcp {list,test}` | External MCP servers |
| `veles models <provider>` | provider models की सूची |
| `veles doctor` | Health checks |
| `veles export / import` | Project backup और transfer |

हर command में `--help` होता है।

---

## Documentation

पूर्ण documentation — Diátaxis-संगठित (tutorials · how-to guides · reference · explanation):

- **हिन्दी:** [`docs/hi/index.md`](docs/hi/index.md)

अन्य भाषाएँ: किसी भी दस्तावेज़ पृष्ठ के शीर्ष पर दिए गए 🌐 स्विचर का उपयोग करें।

---

## Contributing

योगदान का बहुत स्वागत है — Veles **विस्तार के लिए बनाया गया है**। Core छोटा रहता है (agent loop + project memory + provider protocol); लगभग बाकी सब कुछ एक pluggable extension point है, इसलिए किसी capability को जोड़ने का मतलब शायद ही कभी core को छूना हो:

- **Provider adapters** (`src/veles/adapters/`) — एक नया model backend wire करें।
- **Skills** — `extends:` inheritance के साथ पुनः-प्रयोग योग्य prompt-blocks और tools, project से user-global में promotable।
- **Tools** — typed Python जिसे एजेंट लिखता और पुनः उपयोग करता है, `<project>/.veles/tools/` के तहत।
- **Layout packs** — `~/.veles/layouts/<name>/` में एक ही `layout.toml` एक पूरा content layout परिभाषित करता है।
- **Module hooks** — `pre_turn` / `post_turn` hooks (`src/veles/core/modules.py`) के ज़रिए observability, logging, और policy।
- **Channels & MCP servers** — नए gateways और external tool sources।
- **Locales** — `src/veles/locales/` में अनुवाद।

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

Codebase को जानबूझकर decompose किया गया है — single responsibility, कोई god-files नहीं। conventions के लिए [`CONTRIBUTING.md`](CONTRIBUTING.md) पढ़ें और PR खोलने से पहले [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) पढ़ें। अच्छे पहले योगदान: provider adapters, workflow skills, module hooks, और locale files।

---

## License

Apache 2.0 with patent grant — देखें [`LICENSE`](LICENSE) और [`NOTICE`](NOTICE)।
