# CLI reference

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/reference/cli.md)

Veles का हर command, subcommand, और flag। आधिकारिक, हमेशा-अद्यतन signature के लिए
`veles <command> --help` चलाएँ — यह page `src/veles/cli/_parsers/` में मौजूद
argument parsers को दर्शाता है।

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — पहली-बार चलने वाले setup wizard को skip करें, भले ही
  `~/.veles/config.toml` मौजूद न हो (यह TTY और `VELES_NO_WIZARD=1` पर भी निर्भर है)।
- बिना किसी arguments के, `veles` interactive [TUI](tui.md) लॉन्च करता है।

अधिकांश agent commands [shared agent-loop flags](#shared-agent-loop-flags) और
नीचे सूचीबद्ध [provider names](#provider-names) स्वीकार करते हैं।

---

## Project lifecycle

### `veles init [name]`
मौजूदा directory में एक नया Veles project बनाएँ (एक `.veles/` state directory +
`AGENTS.md` + चुने गए layout pack का content scaffold)।

| Flag | Default | उद्देश्य |
|---|---|---|
| `name` (positional) | cwd basename | Project name |
| `--layout <name>` | `llm-wiki` | Content scaffold के लिए layout pack (`llm-wiki`, `notes`, `bare`, या `~/.veles/layouts/` से एक custom pack) |
| `--force` | off | `.veles/` को दोबारा बनाएँ भले ही यह पहले से मौजूद हो |

### `veles schema {validate,edit,fix}`
`AGENTS.md` (project context file) को validate या edit करें।

- `validate` — आवश्यक H2 sections की जाँच करें।
- `edit` — `$EDITOR` (default `vi`) में `AGENTS.md` खोलें, बाहर निकलने पर validate करें।
- `fix` — एक LLM wizard के ज़रिए लापता sections को interactively जोड़ें।

### `veles self-doc [refresh|show]`
Project self-documentation (`wiki/self-doc/overview.md`) generate करके दिखाएँ।
सादा `veles self-doc` मौजूदा page दिखाता है; `refresh` उसे दोबारा generate करता है।

### `veles doctor`
User-global state और सक्रिय project पर health checks चलाएँ। यह सक्रिय project के
साथ या उसके बिना काम करता है।

| Flag | Default | उद्देश्य |
|---|---|---|
| `--json` | off | एक JSON report दें |
| `--strict` | off | किसी भी warning पर non-zero exit (CI gating) |

### `veles export {full,template} <path>`
Project को एक `.tar.gz` bundle में पैक करें। देखें [Back up and share](../how-to/backup-and-share.md)।

- `full <path>` — पूरा project (`.veles/` + `AGENTS.md`), runtime ephemera को छोड़कर।
- `template <path>` — sanitised subset (schema + skills + modules + non-session
  wiki pages); `memory.db`, `sources/`, `sessions/`, `trust` grants हटा देता है, और
  text का PII-redact करता है।

### `veles import <path>`
`veles export` से बने एक bundle को restore करें।

| Flag | Default | उद्देश्य |
|---|---|---|
| `path` (positional) | — | Bundle path (`.tar.gz`) |
| `--into <dir>` | cwd | Target directory |
| `--force` | off | Target पर मौजूदा `.veles/` को overwrite करें |

---

## Agent चलाना

### `veles run "<prompt>"`
एक single prompt को memory persistence और curator/learning triggers के साथ
शुरू-से-अंत तक चलाएँ। सभी [shared agent-loop flags](#shared-agent-loop-flags) के
साथ-साथ ये भी स्वीकार करता है:

| Flag | Default | उद्देश्य |
|---|---|---|
| `--resume <session_id>` | new session | एक मौजूदा session जारी रखें |
| `--manager` | off | Multi-agent manager के ज़रिए decompose करें (`VELES_MANAGER_MODE=1` भी) |
| `--plan` | off | Planning mode: read/search/draft की अनुमति, mutations ब्लॉक |
| `--no-agents-md` | off | System prompt में `AGENTS.md` inject न करें |
| `--no-index` | off | `wiki/INDEX.md` inject न करें |
| `--no-compress` | off | Sliding-window context compression बंद करें |
| `--no-curator` | off | इस रन के लिए curator triggers बंद करें |
| `--no-insights` | off | रन के बाद insight extraction बंद करें |
| `--no-proposer` | off | Subproject proposer auto-trigger बंद करें |
| `--no-route-refresh` | off | `AGENTS.md` से NL routing refresh बंद करें |
| `--no-suggest-promote` | off | Auto-promote suggester बंद करें |
| `--compressor-model <id>` | routed | Compression मॉडल override करें |
| `--compress-threshold-tokens <n>` | `50000` | History का आकार जो compression को ट्रिगर करता है |

### `veles tui`
Interactive REPL खोलें। देखें [TUI reference](tui.md)। यह shared agent-loop flags,
`--resume`, ऊपर दिए `--no-*` injection/compression flags, और ये स्वीकार करता है:

| Flag | Default | उद्देश्य |
|---|---|---|
| `--theme <name>` | config or `everforest` | Color theme (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
एक source (एक local file या `http(s)://` URL) पढ़कर उसे एक wiki page में
synthesise करें। Shared agent-loop flags स्वीकार करता है।

### `veles curate`
एक curator pass चलाएँ: unprocessed sessions को `wiki/sessions/` pages में compact करें।

| Flag | Default | उद्देश्य |
|---|---|---|
| `--limit <n>` | एक छोटा default | इस रन में प्रोसेस होने वाले max sessions |

साथ ही shared agent-loop flags।

### `veles research "<question>"`
Deep research: subquestions में decompose करें → web को parallel में explore करें →
एक cited report synthesise करें।

| Flag | Default | उद्देश्य |
|---|---|---|
| `--max-subquestions <n>` | `4` | Parallel research angles |

साथ ही shared agent-loop flags।

### `veles dream`
एक background memory-consolidation cycle चलाएँ (insights → skill dedup → promote
suggestions → wiki lint, वैकल्पिक रूप से LLM consolidation)।

| Flag | Default | उद्देश्य |
|---|---|---|
| `--include-consolidation` | off | महँगा LLM consolidation चलाएँ (एक API key चाहिए) |
| `--dry-run` | off | सभी steps चलाएँ पर `wiki/state` writes skip करें |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | अलग-अलग steps skip करें |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | Consolidation मॉडल override करें |
| `--provider <name>` | `openrouter` | Consolidation sub-agent के लिए provider |
| `--project-root <path>` | discover | Project override |

---

## Knowledge: skills, tools, modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcommand | उद्देश्य |
|---|---|
| `list` | सक्रिय project में skills की सूची (telemetry के साथ) |
| `show <name>` | एक skill का `SKILL.md` प्रिंट करें |
| `add <source> [--name N] [--scope project\|user] [-y]` | एक git URL या local path से install करें |
| `remove <name> [--scope project\|user] [-y]` | एक installed skill हटाएँ |
| `promote <name> [--keep-telemetry]` | एक project skill को user scope में copy करें (`~/.veles/skills/`) |
| `demote <name> [-y]` | एक user skill को सक्रिय project में copy करें |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | लगभग-डुप्लिकेट skills खोजें |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | auto-promote मानक पूरा करने वाली skills की सूची |

### `veles tool {list,show,promote}`

| Subcommand | उद्देश्य |
|---|---|
| `list` | इस project के `memory.db` में catalogued tools की सूची |
| `show <name>` | एक tool का manifest + telemetry प्रिंट करें |
| `promote <name> [-y]` | एक project tool को `~/.veles/tools/` में ले जाएँ (cross-project) |

### `veles module {list,show,add,remove}`

| Subcommand | उद्देश्य |
|---|---|
| `list` | Installed modules की सूची |
| `show <name>` | एक module का manifest प्रिंट करें |
| `add <source> [--name N] [-y]` | एक git URL या local path से module install करें |
| `remove <name> [-y]` | एक installed module हटाएँ |

### `veles browse {modules,skills} [query]`
Curated registries browse करें।

| Flag | Default | उद्देश्य |
|---|---|---|
| `query` (positional) | `""` | Substring filter |
| `--source <url>` | canonical | Registry source override करें |
| `--json` | off | JSON दें |

---

## Sessions & memory

### `veles sessions {list,show,delete,search}`

| Subcommand | उद्देश्य |
|---|---|
| `list [--limit n]` | हाल के sessions की सूची (default 20) |
| `show <session_id>` | एक session का पूरा turn history प्रिंट करें |
| `delete <session_id>` | एक session और उसके turns हटाएँ |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | turn content पर full-text (FTS5) search |

---

## Multi-project

### `veles project {list,add,remove,switch}`

| Subcommand | उद्देश्य |
|---|---|
| `list` | पंजीकृत projects की सूची, सबसे हाल वाले पहले |
| `add <path> [--slug S]` | एक मौजूदा project directory register करें |
| `remove <slug>` | एक project unregister करें (files अछूती रहती हैं) |
| `switch <slug>` | project का absolute path प्रिंट करें (`cd $(veles project switch <slug>)` इस्तेमाल करें) |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcommand | उद्देश्य |
|---|---|
| `init <subdir> [--name N] [--description D]` | एक subproject बनाएँ + register करें |
| `list` | सक्रिय project के subprojects की सूची |
| `switch <slug>` | एक subproject का absolute path प्रिंट करें |
| `remove <slug>` | एक subproject unregister करें |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | thematic clusters पहचानें और subprojects प्रस्तावित करें |

---

## Routing & models

### `veles route {show,set,reset,refresh}`
Per-task ensemble routing — कौन-सा `provider:model` हर task type
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`) संभालता है। देखें [per-task routing](../how-to/per-task-routing.md)।

| Subcommand | उद्देश्य |
|---|---|
| `show` | सक्रिय project के लिए resolved routing table प्रिंट करें |
| `set <task> <provider:model>` | एक task को एक spec पर पिन करें |
| `reset [task]` | एक task (या सभी) को defaults पर reset करें |
| `refresh [--force]` | `AGENTS.md` से natural-language routing hints दोबारा पार्स करें |

### `veles models <provider>`
एक provider के लिए models की सूची। Cloud providers (openrouter/openai/gemini) 24
घंटे cache होते हैं; local providers हमेशा live होते हैं।

| Flag | Default | उद्देश्य |
|---|---|---|
| `provider` (positional) | — | [provider names](#provider-names) में से एक |
| `--refresh` | off | Disk cache को bypass करें (केवल cloud) |
| `--json` | off | `{provider, source, models}` को JSON के रूप में दें |

---

## Long-running tasks

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Budgets और checkpoints के साथ long-horizon objectives।

| Subcommand | उद्देश्य |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | goals की सूची |
| `show <id> [--json]` | एक goal दिखाएँ |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | एक goal बनाएँ |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | प्रगति जोड़ें |
| `pause <id>` / `resume <id>` | Pause / resume |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Finish / cancel |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Scheduled agent jobs।

| Subcommand | उद्देश्य |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | एक job बनाएँ (schedule = cron, `<N><s\|m\|h\|d>`, या ISO timestamp) |
| `list [--json]` / `show <id>` | jobs inspect करें |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Lifecycle |
| `history <id> [--limit n]` | हाल के runs |
| `tick` | सभी due jobs को एक बार synchronously चलाएँ (daemon की ज़रूरत नहीं; agent-loop flags लेता है) |

---

## Security & access control

### `veles trust {list,set,revoke,clear}`
संवेदनशील tools (`run_shell`, `write_file`, `fetch_url`, …) के लिए persisted grants।
देखें [security](../how-to/security-and-permissions.md)।

| Subcommand | उद्देश्य |
|---|---|
| `list` | grants दिखाएँ (user + project scope) |
| `set <tool> [--scope project\|user]` | एक tool को grant करें |
| `revoke <tool> [--scope project\|user\|both]` | एक grant हटाएँ |
| `clear [--scope project\|user\|all]` | एक scope में grants मिटाएँ |

### `veles autopilot {enable,disable,status}`
एक time-boxed window जहाँ trust-ladder prompts अपने-आप allow हो जाते हैं।

| Subcommand | उद्देश्य |
|---|---|
| `enable --until <DUR>` | एक window खोलें (`+30m`, `+2h`, `+1d`, या ISO `2026-05-12T18:00:00Z`) |
| `disable` | window अभी बंद करें |
| `status` | बताएँ कि autopilot सक्रिय है या नहीं |

### `veles secret {set,get,list,delete}`
OS-keychain-backed secrets (API keys, bot tokens)।

| Subcommand | उद्देश्य |
|---|---|
| `set <name> [value]` | Store करें (interactive / stdin के लिए value छोड़ें) |
| `get <name> [--reveal] [--no-env-fallback]` | Look up करें (default रूप से env fallback) |
| `list` | दिखाएँ कि कौन-से canonical secrets configured हैं |
| `delete <name>` | एक secret हटाएँ |

---

## Daemon & channels

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
HTTP+WS daemon चलाएँ/नियंत्रित करें। सादा `veles daemon` **daemon picker** TUI
खोलता है (project → daemons → channels)। देखें [run as a daemon](../how-to/run-as-daemon.md)।

| Subcommand | उद्देश्य |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | एक daemon start करें (default रूप से detach होता है) |
| `stop [--name N]` / `status [--name N]` | Stop / inspect |
| `list` | सभी projects के daemons की सूची |
| `restart [target] [--name N]` | Stop + उसी host/port पर respawn |
| `delete <target> [-y]` | Stop + registry से हटाएँ |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | एक named daemon session घोषित करें |
| `session list [--all]` / `session delete <name>` | named sessions संभालें |
| `token add <name>` / `token list` / `token remove <name>` | Bearer-token CRUD |

`start` shared agent-loop flags भी स्वीकार करता है; daemon के लिए, `--model` /
`--provider` default रूप से project config पर जाते हैं और daemon के पूरे जीवनकाल के
लिए fixed रहते हैं।

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
External chat gateways (Telegram, …) जो एक daemon से बात करते हैं। देखें
[connect Telegram](../how-to/connect-telegram.md)।

| Subcommand | उद्देश्य |
|---|---|
| `list` | पंजीकृत channel platforms + session counts की सूची |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | एक gateway foreground में start करें |
| `list-sessions [--channel C]` | `chat_id → session_id` mappings दिखाएँ |
| `reset-session <chat_id> [--channel C]` | एक mapping भूल जाएँ (अगला message नए सिरे से शुरू होगा) |
| `add [--channel C] [--session S]` | एक channel को एक daemon से जोड़ें (wizard; creds → keychain) |
| `remove <channel> [--session S]` | एक channel binding हटाएँ |

---

## MCP (external tool servers)

### `veles mcp {list,test}`
`[mcp.servers.*]` के तहत configured external MCP servers inspect करें। देखें
[external MCP servers](../how-to/external-mcp-servers.md)।

| Subcommand | उद्देश्य |
|---|---|
| `list [--connect-timeout f]` | configured servers, connection status, tool counts दिखाएँ |
| `test <server>` | एक server से connect करें और उसके tools की सूची दें |

---

## Shared agent-loop flags

`run`, `add`, `tui`, `curate`, `research`, `job tick`, और `daemon start` द्वारा
स्वीकृत:

| Flag | Default | उद्देश्य |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: persisted) | Model ID |
| `--provider <name>` | `openrouter` | Provider (नीचे देखें) |
| `--max-tokens-total <n>` | `100000` | Cumulative token budget; `0` बंद कर देता है |
| `--max-iterations <n>` | `30` | प्रति turn max tool-calling iterations |
| `--stream` | off | Response को token-by-token stream करें |
| `--verbose` / `-v` | off | प्रति-turn प्रगति stderr पर |
| `--project-root <path>` | cwd से discover | किसी अन्य जगह के project पर काम करें |

## Provider names

`openrouter` (default) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Local providers (`ollama`, `llamacpp`, `openai-compat`) को किसी API key की ज़रूरत
नहीं है। देखें [providers reference](providers.md) और [configure providers](../how-to/configure-providers.md)।
