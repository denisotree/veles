# CLI reference

> 🌐 **Languages:** [English](../../en/reference/cli.md) · [Русский](../../ru/reference/cli.md) · **বাংলা**

প্রতিটি Veles কমান্ড, subcommand, ও flag। সর্বদা-সর্বশেষ এবং কর্তৃত্বপূর্ণ signature-এর জন্য
`veles <command> --help` চালান — এই পৃষ্ঠাটি `src/veles/cli/_parsers/`-এর argument parser-গুলোর
প্রতিফলন।

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — `~/.veles/config.toml` না থাকলেও first-run setup wizard বাদ দেয়
  (এটি একটি TTY ও `VELES_NO_WIZARD=1`-এর উপরও নির্ভরশীল)।
- কোনো argument ছাড়া `veles` interactive [TUI](tui.md) চালু করে।

বেশিরভাগ agent কমান্ড নিচে তালিকাভুক্ত [shared agent-loop flags](#shared-agent-loop-flags)
ও [provider names](#provider-names) গ্রহণ করে।

---

## Project lifecycle

### `veles init [name]`
বর্তমান ডিরেক্টরিতে একটি নতুন Veles প্রজেক্ট তৈরি করে (একটি `.veles/` state ডিরেক্টরি
+ `AGENTS.md` + বেছে নেওয়া layout pack-এর কন্টেন্ট scaffold)।

| Flag | Default | Purpose |
|---|---|---|
| `name` (positional) | cwd basename | প্রজেক্টের নাম |
| `--layout <name>` | `llm-wiki` | কন্টেন্ট scaffold-এর জন্য layout pack (`llm-wiki`, `notes`, `bare`, বা `~/.veles/layouts/`-এর কোনো custom pack) |
| `--force` | off | `.veles/` ইতিমধ্যে থাকলেও পুনরায় তৈরি করে |

### `veles schema {validate,edit,fix}`
`AGENTS.md` (project context ফাইল) validate বা সম্পাদনা করে।

- `validate` — আবশ্যক H2 section-গুলো আছে কিনা পরীক্ষা করে।
- `edit` — `$EDITOR`-এ (ডিফল্ট `vi`) `AGENTS.md` খোলে, বের হওয়ার সময় validate করে।
- `fix` — একটি LLM wizard-এর মাধ্যমে interactive ভাবে অনুপস্থিত section যোগ করে।

### `veles self-doc [refresh|show]`
project self-documentation (`wiki/self-doc/overview.md`) তৈরি ও প্রদর্শন করে।
শুধু `veles self-doc` বর্তমান পৃষ্ঠা দেখায়; `refresh` এটি পুনরায় তৈরি করে।

### `veles doctor`
user-global state ও সক্রিয় প্রজেক্টের উপর health check চালায়। সক্রিয় প্রজেক্ট
থাকুক বা না থাকুক — উভয় ক্ষেত্রেই কাজ করে।

| Flag | Default | Purpose |
|---|---|---|
| `--json` | off | একটি JSON report দেয় |
| `--strict` | off | যেকোনো warning-এ non-zero exit করে (CI gating) |

### `veles export {full,template} <path>`
প্রজেক্টকে একটি `.tar.gz` bundle-এ প্যাক করে। দেখুন [Back up and share](../how-to/backup-and-share.md)।

- `full <path>` — পুরো প্রজেক্ট (`.veles/` + `AGENTS.md`), runtime ephemera বাদে।
- `template <path>` — sanitised subset (schema + skills + modules + non-session
  wiki page); `memory.db`, `sources/`, `sessions/`, `trust` grant বাদ দেয়, এবং
  text থেকে PII redact করে।

### `veles import <path>`
`veles export` দিয়ে তৈরি একটি bundle পুনরুদ্ধার করে।

| Flag | Default | Purpose |
|---|---|---|
| `path` (positional) | — | Bundle path (`.tar.gz`) |
| `--into <dir>` | cwd | Target ডিরেক্টরি |
| `--force` | off | target-এ থাকা existing `.veles/` overwrite করে |

---

## Agent চালানো

### `veles run "<prompt>"`
একটি একক prompt-কে memory persistence ও curator/learning trigger সহ end-to-end চালায়।
সমস্ত [shared agent-loop flags](#shared-agent-loop-flags) এবং সাথে:

| Flag | Default | Purpose |
|---|---|---|
| `--resume <session_id>` | নতুন session | একটি existing session চালিয়ে যায় |
| `--manager` | off | multi-agent manager-এর মাধ্যমে decompose করে (`VELES_MANAGER_MODE=1`-ও) |
| `--plan` | off | Planning mode: read/search/draft অনুমোদিত, mutation ব্লক করা |
| `--no-agents-md` | off | system prompt-এ `AGENTS.md` inject করে না |
| `--no-index` | off | `wiki/INDEX.md` inject করে না |
| `--no-compress` | off | sliding-window context compression নিষ্ক্রিয় করে |
| `--no-curator` | off | এই run-এর জন্য curator trigger নিষ্ক্রিয় করে |
| `--no-insights` | off | run-পরবর্তী insight extraction নিষ্ক্রিয় করে |
| `--no-proposer` | off | subproject proposer auto-trigger নিষ্ক্রিয় করে |
| `--no-route-refresh` | off | `AGENTS.md` থেকে NL routing refresh নিষ্ক্রিয় করে |
| `--no-suggest-promote` | off | auto-promote suggester নিষ্ক্রিয় করে |
| `--compressor-model <id>` | routed | compression model override করে |
| `--compress-threshold-tokens <n>` | `50000` | যে history size compression trigger করে |

### `veles tui`
interactive REPL খোলে। দেখুন [TUI reference](tui.md)। shared
agent-loop flag, `--resume`, উপরের `--no-*` injection/compression flag, এবং সাথে:

| Flag | Default | Purpose |
|---|---|---|
| `--theme <name>` | config বা `everforest` | Color theme (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
একটি source (একটি লোকাল ফাইল বা `http(s)://` URL) পড়ে এবং সেটিকে একটি wiki
page-এ synthesise করে। shared agent-loop flag গ্রহণ করে।

### `veles curate`
একটি curator pass চালায়: অপ্রক্রিয়াকৃত session-গুলোকে `wiki/sessions/` page-এ compact করে।

| Flag | Default | Purpose |
|---|---|---|
| `--limit <n>` | একটি ছোট ডিফল্ট | এই run-এ প্রক্রিয়া করার সর্বোচ্চ session সংখ্যা |

সাথে shared agent-loop flag।

### `veles research "<question>"`
Deep research: subquestion-এ decompose → ওয়েবে সমান্তরালে অন্বেষণ →
একটি cited report synthesise করে।

| Flag | Default | Purpose |
|---|---|---|
| `--max-subquestions <n>` | `4` | সমান্তরাল research angle |

সাথে shared agent-loop flag।

### `veles dream`
একটি background memory-consolidation cycle চালায় (insight → skill dedup → promote
suggestion → wiki lint, ঐচ্ছিকভাবে LLM consolidation)।

| Flag | Default | Purpose |
|---|---|---|
| `--include-consolidation` | off | ব্যয়বহুল LLM consolidation চালায় (একটি API key লাগে) |
| `--dry-run` | off | সব step চালায় কিন্তু `wiki/state` write বাদ দেয় |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | পৃথক step বাদ দেয় |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | consolidation model override করে |
| `--provider <name>` | `openrouter` | consolidation sub-agent-এর provider |
| `--project-root <path>` | discover | Project override |

---

## Knowledge: skills, tools, modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcommand | Purpose |
|---|---|
| `list` | সক্রিয় প্রজেক্টের skill তালিকা করে (telemetry সহ) |
| `show <name>` | একটি skill-এর `SKILL.md` প্রিন্ট করে |
| `add <source> [--name N] [--scope project\|user] [-y]` | একটি git URL বা লোকাল path থেকে ইনস্টল করে |
| `remove <name> [--scope project\|user] [-y]` | একটি ইনস্টল করা skill মুছে ফেলে |
| `promote <name> [--keep-telemetry]` | একটি project skill user scope-এ কপি করে (`~/.veles/skills/`) |
| `demote <name> [-y]` | একটি user skill সক্রিয় প্রজেক্টে কপি করে |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | প্রায়-ডুপ্লিকেট skill খুঁজে বের করে |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | auto-promote bar পূরণকারী skill তালিকা করে |

### `veles tool {list,show,promote}`

| Subcommand | Purpose |
|---|---|
| `list` | এই প্রজেক্টের `memory.db`-এ ক্যাটালগ করা tool তালিকা করে |
| `show <name>` | একটি tool-এর manifest + telemetry প্রিন্ট করে |
| `promote <name> [-y]` | একটি project tool `~/.veles/tools/`-এ সরায় (cross-project) |

### `veles module {list,show,add,remove}`

| Subcommand | Purpose |
|---|---|
| `list` | ইনস্টল করা module তালিকা করে |
| `show <name>` | একটি module-এর manifest প্রিন্ট করে |
| `add <source> [--name N] [-y]` | একটি git URL বা লোকাল path থেকে একটি module ইনস্টল করে |
| `remove <name> [-y]` | একটি ইনস্টল করা module মুছে ফেলে |

### `veles browse {modules,skills} [query]`
curated registry গুলো ব্রাউজ করে।

| Flag | Default | Purpose |
|---|---|---|
| `query` (positional) | `""` | Substring filter |
| `--source <url>` | canonical | registry source override করে |
| `--json` | off | JSON দেয় |

---

## Sessions ও memory

### `veles sessions {list,show,delete,search}`

| Subcommand | Purpose |
|---|---|
| `list [--limit n]` | সাম্প্রতিক session তালিকা করে (ডিফল্ট 20) |
| `show <session_id>` | একটি session-এর সম্পূর্ণ turn history প্রিন্ট করে |
| `delete <session_id>` | একটি session ও তার turn মুছে ফেলে |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | turn কন্টেন্টের উপর full-text (FTS5) search |

---

## Multi-project

### `veles project {list,add,remove,switch}`

| Subcommand | Purpose |
|---|---|
| `list` | নিবন্ধিত প্রজেক্ট তালিকা করে, সর্বশেষটি প্রথমে |
| `add <path> [--slug S]` | একটি existing project ডিরেক্টরি নিবন্ধন করে |
| `remove <slug>` | একটি প্রজেক্ট unregister করে (ফাইল অপরিবর্তিত থাকে) |
| `switch <slug>` | প্রজেক্টের absolute path প্রিন্ট করে (`cd $(veles project switch <slug>)` ব্যবহার করুন) |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcommand | Purpose |
|---|---|
| `init <subdir> [--name N] [--description D]` | একটি subproject তৈরি + নিবন্ধন করে |
| `list` | সক্রিয় প্রজেক্টের subproject তালিকা করে |
| `switch <slug>` | একটি subproject-এর absolute path প্রিন্ট করে |
| `remove <slug>` | একটি subproject unregister করে |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | thematic cluster শনাক্ত করে subproject প্রস্তাব করে |

---

## Routing ও models

### `veles route {show,set,reset,refresh}`
Per-task ensemble routing — কোন `provider:model` প্রতিটি task type সামলায়
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`)। দেখুন [per-task routing](../how-to/per-task-routing.md)।

| Subcommand | Purpose |
|---|---|
| `show` | সক্রিয় প্রজেক্টের resolved routing table প্রিন্ট করে |
| `set <task> <provider:model>` | একটি task-কে একটি spec-এ pin করে |
| `reset [task]` | একটি task (বা সব) ডিফল্টে reset করে |
| `refresh [--force]` | `AGENTS.md` থেকে natural-language routing hint পুনরায় parse করে |

### `veles models <provider>`
একটি provider-এর model তালিকা করে। Cloud provider (openrouter/openai/gemini) ২৪ ঘণ্টা
cache হয়; লোকাল provider সবসময় লাইভ।

| Flag | Default | Purpose |
|---|---|---|
| `provider` (positional) | — | [provider names](#provider-names)-এর একটি |
| `--refresh` | off | disk cache বাইপাস করে (শুধু cloud) |
| `--json` | off | `{provider, source, models}` JSON হিসেবে দেয় |

---

## দীর্ঘ-চলমান task

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
budget ও checkpoint সহ দীর্ঘ-মেয়াদি objective।

| Subcommand | Purpose |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | goal তালিকা করে |
| `show <id> [--json]` | একটি goal দেখায় |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | একটি goal তৈরি করে |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | progress যোগ করে |
| `pause <id>` / `resume <id>` | Pause / resume |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Finish / cancel |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
নির্ধারিত (scheduled) agent job।

| Subcommand | Purpose |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | একটি job তৈরি করে (schedule = cron, `<N><s\|m\|h\|d>`, বা ISO timestamp) |
| `list [--json]` / `show <id>` | job inspect করে |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Lifecycle |
| `history <id> [--limit n]` | সাম্প্রতিক run |
| `tick` | সব due job একবার synchronous ভাবে চালায় (কোনো daemon লাগে না; agent-loop flag নেয়) |

---

## Security ও access control

### `veles trust {list,set,revoke,clear}`
সংবেদনশীল tool-এর জন্য সংরক্ষিত grant (`run_shell`, `write_file`, `fetch_url`, …)।
দেখুন [security](../how-to/security-and-permissions.md)।

| Subcommand | Purpose |
|---|---|
| `list` | grant দেখায় (user + project scope) |
| `set <tool> [--scope project\|user]` | একটি tool grant করে |
| `revoke <tool> [--scope project\|user\|both]` | একটি grant সরায় |
| `clear [--scope project\|user\|all]` | একটি scope-এর grant মুছে দেয় |

### `veles autopilot {enable,disable,status}`
একটি সময়-সীমাবদ্ধ window যেখানে trust-ladder prompt স্বয়ংক্রিয়ভাবে allow হয়।

| Subcommand | Purpose |
|---|---|
| `enable --until <DUR>` | একটি window খোলে (`+30m`, `+2h`, `+1d`, বা ISO `2026-05-12T18:00:00Z`) |
| `disable` | এখনই window বন্ধ করে |
| `status` | autopilot সক্রিয় কিনা জানায় |

### `veles secret {set,get,list,delete}`
OS-keychain-backed secret (API key, bot token)।

| Subcommand | Purpose |
|---|---|
| `set <name> [value]` | সংরক্ষণ করে (interactive / stdin-এর জন্য value বাদ দিন) |
| `get <name> [--reveal] [--no-env-fallback]` | খোঁজে (ডিফল্টভাবে env fallback) |
| `list` | কোন canonical secret কনফিগার করা আছে দেখায় |
| `delete <name>` | একটি secret সরায় |

---

## Daemon ও channels

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
HTTP+WS daemon চালায়/নিয়ন্ত্রণ করে। শুধু `veles daemon` **daemon picker**
TUI খোলে (project → daemons → channels)। দেখুন [run as a daemon](../how-to/run-as-daemon.md)।

| Subcommand | Purpose |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | একটি daemon শুরু করে (ডিফল্টভাবে detach করে) |
| `stop [--name N]` / `status [--name N]` | Stop / inspect |
| `list` | সব প্রজেক্ট জুড়ে daemon তালিকা করে |
| `restart [target] [--name N]` | একই host/port-এ Stop + respawn করে |
| `delete <target> [-y]` | Stop + registry থেকে সরায় |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | একটি named daemon session ঘোষণা করে |
| `session list [--all]` / `session delete <name>` | named session পরিচালনা করে |
| `token add <name>` / `token list` / `token remove <name>` | Bearer-token CRUD |

`start` shared agent-loop flag-ও গ্রহণ করে; daemon-এর ক্ষেত্রে `--model` /
`--provider` ডিফল্টভাবে project config থেকে আসে এবং daemon-এর জীবদ্দশায় স্থির থাকে।

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
external chat gateway (Telegram, …) যা একটি daemon-এর সাথে কথা বলে। দেখুন
[connect Telegram](../how-to/connect-telegram.md)।

| Subcommand | Purpose |
|---|---|
| `list` | নিবন্ধিত channel platform + session count তালিকা করে |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | foreground-এ একটি gateway শুরু করে |
| `list-sessions [--channel C]` | `chat_id → session_id` mapping দেখায় |
| `reset-session <chat_id> [--channel C]` | একটি mapping ভুলে যায় (পরের বার্তা নতুন করে শুরু হয়) |
| `add [--channel C] [--session S]` | একটি daemon-এ একটি channel attach করে (wizard; creds → keychain) |
| `remove <channel> [--session S]` | একটি channel binding সরায় |

---

## MCP (external tool servers)

### `veles mcp {list,test}`
`[mcp.servers.*]`-এর অধীনে কনফিগার করা external MCP server inspect করে। দেখুন
[external MCP servers](../how-to/external-mcp-servers.md)।

| Subcommand | Purpose |
|---|---|
| `list [--connect-timeout f]` | কনফিগার করা server, connection status, tool count দেখায় |
| `test <server>` | একটি server-এ connect করে তার tool তালিকা করে |

---

## Shared agent-loop flags

`run`, `add`, `tui`, `curate`, `research`, `job tick`, এবং `daemon
start` দ্বারা গৃহীত:

| Flag | Default | Purpose |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: persisted) | Model ID |
| `--provider <name>` | `openrouter` | Provider (নিচে দেখুন) |
| `--max-tokens-total <n>` | `100000` | সঞ্চিত token budget; `0` নিষ্ক্রিয় করে |
| `--max-iterations <n>` | `30` | প্রতি turn-এ সর্বোচ্চ tool-calling iteration |
| `--stream` | off | token-by-token response stream করে |
| `--verbose` / `-v` | off | প্রতি turn-এর progress stderr-এ দেয় |
| `--project-root <path>` | cwd থেকে discover | অন্য কোথাও একটি প্রজেক্টে কাজ করে |

## Provider names

`openrouter` (ডিফল্ট) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

লোকাল provider (`ollama`, `llamacpp`, `openai-compat`)-এর কোনো API key লাগে না। দেখুন
[providers reference](providers.md) ও [configure providers](../how-to/configure-providers.md)।
