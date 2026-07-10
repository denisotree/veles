# CLI संदर्भ

> 🌐 **भाषाएँ:** [English](../../en/reference/cli.md) · [简体中文](../../zh-CN/reference/cli.md) · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · [Español](../../es/reference/cli.md) · [Français](../../fr/reference/cli.md) · [Italiano](../../it/reference/cli.md) · [Português (BR)](../../pt-BR/reference/cli.md) · [Português (PT)](../../pt-PT/reference/cli.md) · [Русский](../../ru/reference/cli.md) · [العربية](../../ar/reference/cli.md) · **हिन्दी** · [বাংলা](../../bn/reference/cli.md) · [Tiếng Việt](../../vi/reference/cli.md)

Veles का हर command, subcommand और flag। प्रामाणिक और हमेशा अद्यतन signature के लिए
`veles <command> --help` चलाएँ — यह पेज `src/veles/cli/_parsers/` के argument parsers
का प्रतिबिंब है।

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — पहली बार चलने वाले setup wizard को छोड़ दें, भले ही
  `~/.veles/config.toml` मौजूद न हो (यह TTY और `VELES_NO_WIZARD=1` पर भी निर्भर है)।
- बिना किसी argument के, `veles` interactive [TUI](tui.md) शुरू करता है।

अधिकांश agent commands [साझा agent-loop flags](#shared-agent-loop-flags) और नीचे
सूचीबद्ध [provider names](#provider-names) स्वीकार करते हैं।

---

## प्रोजेक्ट lifecycle

### `veles init [name]`
वर्तमान directory में एक नया Veles प्रोजेक्ट बनाएँ (एक `.veles/` state directory
+ `AGENTS.md` + चुने गए layout pack का content scaffold)।

| Flag | Default | उद्देश्य |
|---|---|---|
| `name` (positional) | cwd basename | प्रोजेक्ट का नाम |
| `--layout <name>` | `llm-wiki` | content scaffold के लिए layout pack (`llm-wiki`, `notes`, `bare`, या `~/.veles/layouts/` से कोई custom pack) |
| `--force` | off | `.veles/` को फिर से बनाएँ भले ही वह पहले से मौजूद हो |

### `veles schema {validate,edit,fix}`
`AGENTS.md` (प्रोजेक्ट context file) को validate या edit करें।

- `validate` — आवश्यक H2 sections की जाँच करें।
- `edit` — `AGENTS.md` को `$EDITOR` (default `vi`) में खोलें, बाहर निकलने पर validate करें।
- `fix` — एक LLM wizard के ज़रिए लुप्त sections को interactively जोड़ें।

### `veles self-doc [refresh|show]`
प्रोजेक्ट self-documentation (`wiki/self-doc/overview.md`) उत्पन्न करें और दिखाएँ।
सादा `veles self-doc` वर्तमान पेज दिखाता है; `refresh` इसे फिर से उत्पन्न करता है।

### `veles doctor`
user-global state और सक्रिय प्रोजेक्ट पर health checks चलाएँ। सक्रिय प्रोजेक्ट के
साथ या बिना — दोनों स्थितियों में काम करता है।

| Flag | Default | उद्देश्य |
|---|---|---|
| `--json` | off | एक JSON report निकालें |
| `--strict` | off | किसी भी warning पर non-zero exit (CI gating) |
| `--fix` | off | जाँच से पहले सुरक्षित मरम्मत का प्रयास करें — फ़िलहाल एक भ्रष्ट memory-recall (FTS) index को फिर से बनाता है |

`doctor` `config.toml` के सुरक्षा-संबंधी sections (`[channels.*]`, `[daemon.*]`,
`[mcp.servers.*]`) को भी validate करता है और अज्ञात keys को एक error के रूप में
रिपोर्ट करता है — `whitelist` के लिए `whitlist` जैसी एक typo चुपचाप एक access
control को अक्षम कर देती है, इसलिए यहाँ यह ज़ोर से विफल होता है।

### `veles export {full,template} <path>`
प्रोजेक्ट को एक `.tar.gz` bundle में पैक करें। देखें [बैकअप और साझा करना](../how-to/backup-and-share.md)।

- `full <path>` — पूरा प्रोजेक्ट (`.veles/` + `AGENTS.md`), runtime ephemera को छोड़कर।
- `template <path>` — स्वच्छ subset (schema + skills + modules + non-session
  wiki पेज); `memory.db`, `sources/`, `sessions/`, `trust` grants को हटा देता है और
  text से PII redact करता है।

### `veles import <path>`
`veles export` द्वारा बनाए गए bundle को restore करें।

| Flag | Default | उद्देश्य |
|---|---|---|
| `path` (positional) | — | Bundle path (`.tar.gz`) |
| `--into <dir>` | cwd | लक्ष्य directory |
| `--force` | off | लक्ष्य पर मौजूदा `.veles/` को overwrite करें |

---

## Agent चलाना

### `veles run "<prompt>"`
memory persistence और curator/learning triggers के साथ एक single prompt को end-to-end
चलाएँ। सभी [साझा agent-loop flags](#shared-agent-loop-flags) के साथ-साथ ये भी स्वीकार करता है:

| Flag | Default | उद्देश्य |
|---|---|---|
| `--resume <session_id>` | नया session | मौजूदा session जारी रखें |
| `--manager` | off | multi-agent manager के ज़रिए decompose करें (`VELES_MANAGER_MODE=1` भी) |
| `--verify` | off | run के बाद routed advisor उत्तर का मूल्यांकन करता है; पक्की विफलता पर, मज़बूत model पर फिर से चलाएँ (`VELES_VERIFY_MODE=1` भी) |
| `--plan` | off | Planning mode: read/search/draft की अनुमति, mutations अवरुद्ध |
| `--no-agents-md` | off | system prompt में `AGENTS.md` inject न करें |
| `--no-index` | off | `wiki/INDEX.md` inject न करें |
| `--no-compress` | off | sliding-window context compression अक्षम करें |
| `--no-curator` | off | इस run के लिए curator triggers अक्षम करें |
| `--no-insights` | off | run के बाद insight extraction अक्षम करें |
| `--no-proposer` | off | subproject proposer auto-trigger अक्षम करें |
| `--no-route-refresh` | off | `AGENTS.md` से NL routing refresh अक्षम करें |
| `--no-suggest-promote` | off | auto-promote suggester अक्षम करें |
| `--compressor-model <id>` | routed | compression model override करें |
| `--compress-threshold-tokens <n>` | `50000` | जो history size compression को trigger करती है |

### `veles tui`
interactive REPL खोलें। देखें [TUI संदर्भ](tui.md)। साझा agent-loop flags, `--resume`,
ऊपर दिए `--no-*` injection/compression flags, और ये स्वीकार करता है:

| Flag | Default | उद्देश्य |
|---|---|---|
| `--theme <name>` | config या `everforest` | Color theme (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
एक source (एक local file या `http(s)://` URL) पढ़ें और उसे एक wiki पेज में संश्लेषित
करें। साझा agent-loop flags स्वीकार करता है।

### `veles curate`
एक curator pass चलाएँ: unprocessed sessions को `wiki/sessions/` पेजों में compact करें।

| Flag | Default | उद्देश्य |
|---|---|---|
| `--limit <n>` | एक छोटा default | इस run में process करने हेतु अधिकतम sessions |

साथ ही साझा agent-loop flags।

### `veles research "<question>"`
गहन शोध: subquestions में decompose करें → web को parallel में explore करें →
उद्धरण-सहित report संश्लेषित करें।

| Flag | Default | उद्देश्य |
|---|---|---|
| `--max-subquestions <n>` | `4` | Parallel research angles |

साथ ही साझा agent-loop flags।

### `veles dream`
एक background memory-consolidation cycle चलाएँ (insights → skill dedup → promote
suggestions → wiki lint, वैकल्पिक रूप से LLM consolidation)।

| Flag | Default | उद्देश्य |
|---|---|---|
| `--include-consolidation` | off | महँगी LLM consolidation चलाएँ (API key चाहिए) |
| `--dry-run` | off | सभी steps चलाएँ लेकिन `wiki/state` writes छोड़ दें |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | अलग-अलग steps छोड़ें |
| `--consolidation-model <id>` | routed (`anthropic/claude-haiku-4.5` पर fallback) | consolidation model override करें |
| `--provider <name>` | routed | consolidation sub-agent के लिए provider (प्रोजेक्ट के routed provider का उपयोग करने हेतु छोड़ दें) |
| `--project-root <path>` | discover | प्रोजेक्ट override |

---

## ज्ञान: skills, tools, modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcommand | उद्देश्य |
|---|---|
| `list` | सक्रिय प्रोजेक्ट में skills सूचीबद्ध करें (telemetry के साथ) |
| `show <name>` | किसी skill की `SKILL.md` प्रिंट करें |
| `add <source> [--name N] [--scope project\|user] [-y]` | git URL या local path से install करें |
| `remove <name> [--scope project\|user] [-y]` | एक installed skill हटाएँ |
| `promote <name> [--keep-telemetry]` | एक project skill को user scope (`~/.veles/skills/`) में कॉपी करें |
| `demote <name> [-y]` | एक user skill को सक्रिय प्रोजेक्ट में कॉपी करें |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | लगभग-डुप्लिकेट skills खोजें |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | auto-promote की सीमा पूरी करने वाली skills सूचीबद्ध करें |

### `veles tool {list,show,promote,approve}`

| Subcommand | उद्देश्य |
|---|---|
| `list` | इस प्रोजेक्ट की `memory.db` में सूचीबद्ध tools दिखाएँ |
| `show <name>` | किसी tool का manifest + telemetry प्रिंट करें |
| `promote <name> [-y]` | एक project tool को `~/.veles/tools/` (cross-project) में ले जाएँ |
| `approve [<name>] [--all] [-y]` | एक self-authored tool file की समीक्षा करें + approve करें ताकि loader उसे चलाए |

self-authored tools (`.veles/tools/*.py`) अपना module-level code तब चलाते हैं जब
loader उन्हें import करता है, इसलिए एक नई या edited file **तब तक load नहीं होती जब
तक आप उसे approve न करें** — `veles tool approve` code दिखाता है और उसका hash
रिकॉर्ड करता है। सादा `veles tool approve` दिखाता है कि क्या लंबित है। यही कारण है
कि agent द्वारा लिखे गए tool को callable बनने से पहले एक review step की ज़रूरत होती है।

### `veles module {list,show,add,remove}`

| Subcommand | उद्देश्य |
|---|---|
| `list` | installed modules सूचीबद्ध करें |
| `show <name>` | किसी module का manifest प्रिंट करें |
| `add <source> [--name N] [-y]` | git URL या local path से एक module install करें |
| `remove <name> [-y]` | एक installed module हटाएँ |

### `veles browse {modules,skills} [query]`
curated registries ब्राउज़ करें।

| Flag | Default | उद्देश्य |
|---|---|---|
| `query` (positional) | `""` | Substring filter |
| `--source <url>` | canonical | registry source override करें |
| `--json` | off | JSON निकालें |

---

## Sessions और memory

### `veles sessions {list,show,delete,search}`

| Subcommand | उद्देश्य |
|---|---|
| `list [--limit n]` | हाल की sessions सूचीबद्ध करें (default 20) |
| `show <session_id>` | किसी session का पूरा turn इतिहास प्रिंट करें |
| `delete <session_id>` | एक session और उसके turns हटाएँ |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | turn content पर full-text (FTS5) खोज |

---

## Multi-project

### `veles project {list,add,remove,switch}`

| Subcommand | उद्देश्य |
|---|---|
| `list` | पंजीकृत प्रोजेक्ट सूचीबद्ध करें, सबसे हाल वाले पहले |
| `add <path> [--slug S]` | एक मौजूदा project directory पंजीकृत करें |
| `remove <slug>` | एक प्रोजेक्ट unregister करें (files अछूती रहती हैं) |
| `switch <slug>` | प्रोजेक्ट का absolute path प्रिंट करें (`cd $(veles project switch <slug>)` का उपयोग करें) |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcommand | उद्देश्य |
|---|---|
| `init <subdir> [--name N] [--description D]` | एक subproject बनाएँ + पंजीकृत करें |
| `list` | सक्रिय प्रोजेक्ट के subprojects सूचीबद्ध करें |
| `switch <slug>` | किसी subproject का absolute path प्रिंट करें |
| `remove <slug>` | एक subproject unregister करें |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | विषयगत clusters का पता लगाएँ और subprojects का प्रस्ताव दें |

---

## Routing और models

### `veles route {show,set,reset,refresh}`
प्रति-task ensemble routing — कौन सा `provider:model` प्रत्येक task type को संभालता है
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`)। देखें [per-task routing](../how-to/per-task-routing.md)।

| Subcommand | उद्देश्य |
|---|---|
| `show` | सक्रिय प्रोजेक्ट के लिए resolved routing table प्रिंट करें |
| `set <task> <provider:model>` | एक task को किसी spec पर pin करें |
| `reset [task]` | एक task (या सभी) को defaults पर reset करें |
| `refresh [--force]` | `AGENTS.md` से natural-language routing hints फिर से parse करें |

### `veles models <provider>`
किसी provider के लिए models सूचीबद्ध करें। Cloud providers (openrouter/openai/gemini)
24h के लिए cached होते हैं; local providers हमेशा live होते हैं।

| Flag | Default | उद्देश्य |
|---|---|---|
| `provider` (positional) | — | [provider names](#provider-names) में से एक |
| `--refresh` | off | disk cache को bypass करें (केवल cloud) |
| `--json` | off | `{provider, source, models}` को JSON के रूप में निकालें |

---

## लंबे समय तक चलने वाले tasks

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
budgets और checkpoints के साथ दीर्घकालिक objectives।

| Subcommand | उद्देश्य |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | goals सूचीबद्ध करें |
| `show <id> [--json]` | एक goal दिखाएँ |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | एक goal बनाएँ |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | प्रगति जोड़ें |
| `pause <id>` / `resume <id>` | रोकें / फिर से शुरू करें |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | समाप्त / रद्द करें |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Scheduled agent jobs।

| Subcommand | उद्देश्य |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | एक job बनाएँ (schedule = cron, `<N><s\|m\|h\|d>`, या ISO timestamp) |
| `list [--json]` / `show <id>` | jobs का निरीक्षण करें |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Lifecycle |
| `history <id> [--limit n]` | हाल के runs |
| `tick` | सभी due jobs को एक बार synchronously चलाएँ (daemon की ज़रूरत नहीं; agent-loop flags लेता है) |

---

## सुरक्षा और access control

### `veles trust {list,set,revoke,clear}`
संवेदनशील tools (`run_shell`, `write_file`, `fetch_url`, …) के लिए स्थायी grants।
देखें [security](../how-to/security-and-permissions.md)।

| Subcommand | उद्देश्य |
|---|---|
| `list` | grants दिखाएँ (user + project scope) |
| `set <tool> [--scope project\|user]` | एक tool grant करें |
| `revoke <tool> [--scope project\|user\|both]` | एक grant हटाएँ |
| `clear [--scope project\|user\|all]` | किसी scope में grants मिटाएँ |

### `veles autopilot {enable,disable,status}`
एक समय-सीमित window जहाँ trust-ladder prompts अपने-आप allow होते हैं।

| Subcommand | उद्देश्य |
|---|---|
| `enable --until <DUR>` | एक window खोलें (`+30m`, `+2h`, `+1d`, या ISO `2026-05-12T18:00:00Z`) |
| `disable` | window अभी बंद करें |
| `status` | बताएँ कि autopilot सक्रिय है या नहीं |

### `veles secret {set,get,list,delete}`
OS-keychain द्वारा समर्थित secrets (API keys, bot tokens)।

| Subcommand | उद्देश्य |
|---|---|
| `set <name> [value]` | संग्रहित करें (interactive / stdin के लिए value छोड़ दें) |
| `get <name> [--reveal] [--no-env-fallback]` | खोजें (default रूप से env fallback) |
| `list` | दिखाएँ कि कौन से canonical secrets configured हैं |
| `delete <name>` | एक secret हटाएँ |

---

## Daemon और channels

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
HTTP+WS daemon चलाएँ/नियंत्रित करें। सादा `veles daemon` **daemon picker** TUI
खोलता है (project → daemons → channels)। देखें [daemon के रूप में चलाना](../how-to/run-as-daemon.md)।

| Subcommand | उद्देश्य |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | एक daemon शुरू करें (default रूप से detach होता है) |
| `stop [--name N]` / `status [--name N]` | रोकें / निरीक्षण करें |
| `list` | सभी प्रोजेक्ट्स के daemons सूचीबद्ध करें |
| `restart [target] [--name N]` | रोकें + उसी host/port पर फिर से चलाएँ |
| `delete <target> [-y]` | रोकें + registry से हटाएँ |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | एक नामित daemon session घोषित करें |
| `session list [--all]` / `session delete <name>` | नामित sessions प्रबंधित करें |
| `token add <name>` / `token list` / `token remove <name>` | Bearer-token CRUD |

`start` साझा agent-loop flags भी स्वीकार करता है; daemon के लिए, `--model` /
`--provider` प्रोजेक्ट config पर default होते हैं और daemon के जीवनकाल भर के लिए fixed रहते हैं।

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
बाहरी chat gateways (Telegram, …) जो किसी daemon से बात करते हैं। देखें
[Telegram जोड़ें](../how-to/connect-telegram.md)।

| Subcommand | उद्देश्य |
|---|---|
| `list` | पंजीकृत channel platforms + session counts सूचीबद्ध करें |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | foreground में एक gateway शुरू करें |
| `list-sessions [--channel C]` | `chat_id → session_id` mappings दिखाएँ |
| `reset-session <chat_id> [--channel C]` | एक mapping भूलें (अगला message नए सिरे से शुरू होगा) |
| `add [--channel C] [--session S]` | किसी daemon से एक channel जोड़ें (wizard; creds → keychain) |
| `remove <channel> [--session S]` | एक channel binding हटाएँ |

---

## MCP (बाहरी tool servers)

### `veles mcp {list,test}`
`[mcp.servers.*]` के अंतर्गत configured बाहरी MCP servers का निरीक्षण करें। देखें
[बाहरी MCP servers](../how-to/external-mcp-servers.md)।

| Subcommand | उद्देश्य |
|---|---|
| `list [--connect-timeout f]` | configured servers, connection status, tool counts दिखाएँ |
| `test <server>` | एक server से connect करें और उसके tools सूचीबद्ध करें |

---

## साझा agent-loop flags

`run`, `add`, `tui`, `curate`, `research`, `job tick`, और `daemon start` द्वारा स्वीकृत:

| Flag | Default | उद्देश्य |
|---|---|---|
| `--model <id>` | प्रोजेक्ट `[engine]` model → user `default_model` से resolved (कोई hardcoded default नहीं) | Model ID |
| `--provider <name>` | `openrouter` | Provider (नीचे देखें) |
| `--max-tokens-total <n>` | `100000` | संचयी token budget; `0` अक्षम करता है |
| `--max-iterations <n>` | `1000` | प्रति turn अधिकतम tool-calling iterations |
| `--stream` | off | प्रतिक्रिया को token-दर-token stream करें |
| `--verbose` / `-v` | off | प्रति-turn प्रगति stderr पर |
| `--project-root <path>` | cwd से discover | कहीं और के प्रोजेक्ट पर काम करें |

## Provider names

`openrouter` (default) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Local providers (`ollama`, `llamacpp`, `openai-compat`) को कोई API key नहीं चाहिए। देखें
[providers संदर्भ](providers.md) और [providers configure करें](../how-to/configure-providers.md)।
