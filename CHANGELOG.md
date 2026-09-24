# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.44.0] — 2026-09-24

A hygiene release: dead code out, names and types that say what they mean,
and CI locks so the structure of the last three releases holds.

### Removed

- `veles goal list --status blocked`: no goal was ever put in that state.
- Unused internals: the display-tier table (Telegram truncation is unchanged),
  the plan-artifact status helpers, the inheritance-chain queries on the skill
  and tool catalogues, and a dozen test-only helpers.

### Changed

- A failed `veles import` raises `BundleImportError` instead of a class that
  shadowed Python's built-in `ImportError`.

### Internal

- New CI locks: `tests/test_layering.py` (no layer imports one above it, lazy
  imports included) and `tests/test_no_private_cross_imports.py` (no package
  imports another's private names); both baselines may only shrink.
- ruff enforces pathlib, loop-variable, argument-count (≤ 8), silent-except
  and redundant-assignment rules; strict mypy covers 37 modules, up from 26.
- Delivery-target parsing lives in `core/delivery_target.py`; the post-turn
  learning hooks and curator limits are public names.
- Mode names, run/job/worker/runtime-session states and model catalogue facts
  are typed; the daemon state's runner and hook slots are no longer `Any`.

## [0.43.0] — 2026-09-23

A structure release: the big modules are split along real seams, and the
layers stop reaching into each other. Two user-visible defects are fixed.

### Fixed

- Telegram: when Telegram refused to edit the "…" placeholder, the answer was
  dropped. It is now sent as a new message. A refused edit also no longer
  counts as the "on it" acknowledgement.
- A background ingest or research job that resumed into a chat whose session
  was gone ran under the dead session id, and the chat stayed pointed at it.
  The job now follows the new session and re-points the chat.

### Changed

- REPL: `/help` is generated from the command registry, so it lists every
  command with its aliases and the hotkeys. `/errors`, `/sessions` and
  `/resume` are ordinary registry commands, and both REPL loops complete the
  same command set.
- Timestamps shown to the user are in local time everywhere; two places used
  UTC.
- Telegram `/start` and `/reset` go through the same command table as the
  other commands.
- `import veles.cli` is much faster: each command module loads only when its
  verb runs.

### Internal

- New `veles/runtime/` package for what the CLI and the daemon share: system
  prompt, tool and skill registry, run loop helpers, post-turn learning. The
  daemon, the runtime and the modules no longer import `veles.cli`.
- The daemon's HTTP server, runner and in-process backend share one run-handle
  API. Channel startup, jobs routes and background runners have their own
  modules.
- `core/memory` is split into schema, session store and re-exports; the
  frontmatter parser and the skill-to-tool factory have their own modules.
- The agent turn loop is split into phases, with characterization tests
  pinning every way a turn can end. `agent.py` and `tool_dispatch.py` are
  checked by strict mypy.
- The Telegram gateway calls its API, media and delivery helpers directly; the
  package exports only `TelegramGateway`.
- Wizards share the host/port prompt, the channel flow, the provider key lookup
  and the model picker.

## [0.42.0] — 2026-09-23

A cleanup release: shared code instead of copies, plus the defects the audit
behind it turned up.

### Fixed

- Flags given before the verb were lost: `veles --no-compress run …` and
  `veles --model X daemon start` ran without them.
- With `VELES_USER_HOME` set, the sandbox refused writes to your user skills,
  and the sanitize config and project registry were read from the real home.
- While the daemon ran a background research job, every other chat turn was
  auto-approved for sensitive tools. The pre-approval now covers the research
  job only.
- A goal could be reported "missing" if it was read while being saved. Goal and
  plan files are now written atomically.
- A chat reached first by a reminder or a delivered job got a second session on
  its next reply, and `veles channel reset-session` could be undone by the
  running daemon.
- On a named daemon (`[daemon.<name>] model`), workers, sub-agents and
  background ingest/research ran on the `[engine]` model.
- `veles daemon <id> restart` now stops a hung daemon and logs the new one's
  start-up to the daemon log.
- `veles channel` and `veles daemon session` honour `--project-root`.
- A non-numeric port in the project wizard no longer crashes it.
- `POST /v1/dream/run` with a non-object JSON body no longer returns 500.
- Dream and dual-write memory writes waited for a busy database instead of
  failing with "database is locked".
- Telegram `/insights` and `/rules` escape titles and bodies, so a `<` in a fact
  no longer breaks the reply.

### Changed

- Every store opens its SQLite connection the same way (WAL, 5 s busy timeout,
  foreign keys), and every state file is written atomically.
- `veles` starts faster: the OpenAI SDK is no longer imported on every
  invocation.

## [0.41.0] — 2026-09-23

### Added — goals in a Telegram chat

`/goal <task>` runs a goal in the chat:

1. The agent asks what it needs to know and shows the plan it will follow.
2. You reply `yes`.
3. It works through the plan on its own and sends a line after each step,
   until the goal is done or a budget runs out.

Approval prompts still arrive as buttons. Other commands:

- `/goal` shows the goal's progress.
- `/goal cancel` stops it after the current step, even while it is running.
- `/goal resume` continues a goal that stopped.

`POST /v1/runs` accepts `"mode"`, and `DELETE /v1/sessions/{id}/goal` cancels a
chat's goal.

### Added — the agent can ask you in a Telegram chat

When the agent needs a detail only you can give, it asks in the chat. Tap a
suggested answer or type your own. If there is no answer within five minutes,
it goes ahead on its best assumption, as it always did before. Runs started over
HTTP or by a scheduled job are not kept waiting.

### Added — `[goal]` in a project's config.toml

`max_steps`, `max_cost_usd` and `max_wall_time_s` set a new goal's budget in
the REPL, in Telegram and in `veles goal start`. Flags given to
`veles goal start` still override them. The built-in defaults stay 30 steps,
$5 and one hour.

### Changed — a chat keeps its mode and goal across daemon restarts

A restarted daemon used to forget a chat's mode and the goal it was running.
They are now saved to `.veles/chat_modes.json`, so `/goal` and
`/goal resume` still find the goal after a restart.

### Fixed — goals everywhere

- A goal set up through the interview (REPL `/goal`, and now Telegram) kept a
  placeholder objective, "(in interview; awaiting clarification)", with no done
  condition. The check step judged progress against that, and `veles goal list`
  showed it. The goal now takes the summary you agreed to as its objective.
- Cancelling a goal while a step was running, from another terminal or a chat,
  crashed the run with "cannot append to goal in status 'cancelled'". The goal
  now stops cleanly.
- The interview no longer tells you to type `/mode writing`, which would have
  taken you out of the goal.

## [0.40.0] — 2026-09-23

### Fixed — the daemon answers chat messages again

Since 0.36.0, every message to a Telegram bot and every `POST /v1/runs` with
text failed with "failed to build agent: memory.aio.submit() called from inside
an event loop". Updating to 0.40.0 fixes it. Background ingest and research
resumes were affected the same way, and so were `/insights` and `/rules` in the
`veles` REPL, which failed with the same error.

### Fixed — Telegram `/mode` works

Choosing a mode used to be saved and then ignored. Every message still ran as
the plain agent. Now the chat's next message runs in the chosen mode:

- `default` — the agent answers directly, as before. Chats you never switched
  stay here.
- `auto` — decides for each message whether to plan first.
- `planning` — plans only and changes nothing.
- `writing` — acts with its tools.

`/mode` ticks the current mode. The choice lasts until the daemon restarts. A
mode's status line, for example *auto → plan*, appears above the answer.

### Fixed — reminders and scheduled messages are part of the chat

Reminders, scheduled jobs and finished background tasks were saved to a
conversation the chat never reads. When you replied, the agent did not know it
had sent anything. This is fixed, and a message sent to a chat through
`POST /v1/runs` with `deliver_to` is now saved to that chat's conversation too.
Notices meant for "the last active chat" can be delivered again. Named daemons
now use their own chat list for this.

### Changed

- `PATCH /v1/sessions/{id}` accepts `default`, `auto`, `planning`, `writing` or
  `goal` and returns `{"session_id", "mode"}`. `GET /v1/sessions/{id}` returns
  `mode` instead of `overrides`.

### Removed

- Six modules and one function that nothing in Veles used: a provider failover
  pool, an API-mode detector, a version helper, a model-name helper, an old
  channel protocol and an old tab completer.

### Known issue

- Goals don't run from Telegram yet. `/goal` explains how to run one on the
  host with `veles goal start`.

## [0.39.0] — 2026-09-22

Bugs found by reading the code for them, each confirmed before it was fixed.
`veles goal` was also run for real against a model, which found two more.

### Changed — `veles goal start` runs the goal

Before, `veles goal start` saved the goal, printed "started goal …" and stopped.
Nothing ever picked the goal up. Now it runs the goal in the foreground: plan,
do a step, check it against the done condition, repeat. It stops when the
condition holds or a budget runs out.

- `--done-when` is now required, because the check step tests it.
- `veles goal resume <id>` continues a goal that was paused, interrupted with
  Ctrl+C, or stopped for making no progress.
- Exit codes: `0` done, `3` cancelled (budget spent or the goal can't be done),
  `4` stopped (no progress, paused, or turn limit reached).
- If the reviewer model that checks each step isn't configured, the goal now
  stops and says so. Before, it re-planned a finished goal over and over.
- Removed `veles goal checkpoint`, `veles goal done`, `--forbid` and
  `--approve`. The running goal now records its own progress and status. Nothing
  ever enforced `--forbid` or `--approve`. Tool approvals work as they do in
  `veles run`.

### Fixed — `veles secret set` for provider keys

`veles secret set OPENROUTER_API_KEY` stored the key where the providers never
looked. A key saved by the setup wizard worked, but `veles secret list` showed
it as unset. `set`, `get`, `delete` and `list` now use the same entries the
providers read. `--project <name>` stores a key for one project. `veles doctor`
checks keys where the runtime reads them. If a key is stuck in the old place and
the provider has no working key, doctor names it; run `veles secret set` again to
fix it. The Tavily and Brave search keys and the daemon token can now come from
the keychain, not only from environment variables.

### Fixed — `veles init` no longer ignores your CLAUDE.md

Veles reads only AGENTS.md. `veles init` used to leave an existing CLAUDE.md or
GEMINI.md alone, so the agent never saw your rules. It now copies them into
AGENTS.md word for word and keeps each original as `.bak`. CLAUDE.md then
becomes a link to AGENTS.md, so Claude Code and Veles read the same file.

### Fixed — Telegram

- A message that starts with a path, like `/var/log/app.log why does it crash?`,
  now reaches the agent. It used to get "Unknown command".
- `/dream` now runs memory consolidation and replies with the result. Before, it
  sent the words to the agent as an ordinary message.
- `/goal` now tells you to run `veles goal start` on the host. It used to promise
  progress updates that never came.
- A scheduled job's message to a chat is now saved in that chat's session, so the
  agent knows about it when you reply. Reminders already worked this way.

### Fixed — skill promotions offered as subprojects

A suggestion to promote a skill showed up in the agent's context as a
"candidate subproject", with a command that would have created a subproject named
after the skill. Skill promotions now have their own section with
`veles skill promote <name>`.

### Known issue

- Telegram `/mode` has no effect yet. Chats always run in the default mode.

## [0.38.0] — 2026-09-22

Three things the interface showed you were never actually connected. Found by
going through every function that only the tests ever called, one at a time.

### Fixed — sessions have titles

The session picker, `veles sessions list` and `/resume` all had a title column,
and nothing ever filled it: every session read "(untitled)". A session is now
titled from your first message. Sessions from before this release keep no title.

### Fixed — `/errors` shows failures from earlier runs again

`/errors` showed only the current REPL session, so a failure in a previous run,
a `veles run` or the daemon disappeared once you restarted. It now also lists
errors from the last 24 hours of other runs, marked as such. The old chat UI did
this; it was lost when that UI was replaced.

### Fixed — the daemon picker showed a named daemon's old model and port

A named daemon starts from its `[daemon.<name>]` block in config.toml, but the
picker showed what was recorded when the session was created. After editing
the config, the picker kept showing the old model — and the old port, which its
own start/stop/log actions then used. It now shows what the daemon actually
started with.

### Removed

- `/save` with no argument. It was meant to list suggested insights to keep,
  but nothing ever produced a suggestion, so it only ever said "needs a slug".
  `/save <slug>` is unchanged; insights are still extracted automatically.
- About twenty internal helpers whose work had moved elsewhere. No behaviour
  change.

## [0.37.0] — 2026-09-22

How long to wait for a model, and how much to let it write, were both guessed
from its name. The guess is structurally weak — a name describes a family, while
the response time is set by the backend serving it, and one relayed model id runs
at 33 tokens/sec on one backend and 0.8 on another. This release takes the
answers from the provider's own catalogue where the catalogue knows them, and
lets your project override the rest.

### Fixed — a model was declared unfit when it had simply been cut off

`deepseek-v4` was not recognised as a model that thinks, so it ran with a
4096-token budget while a competitor ran with 32000. It returned five empty
answers out of twelve, and the comparison concluded the model was broken. It
was not: thinking had consumed the whole budget before the visible answer began,
which looks identical from outside.

Re-run with the corrected budget, pinned to a single backend: **three correct
answers out of three, none empty.** The earlier conclusion is withdrawn.

The recognition list was substrings — `glm-5`, `deepseek-r`, and ten more
families. Measured against OpenRouter's catalogue: of 442 models, 311 can think
and the list recognised 92 of them. The catalogue is now asked first.

### Added — `request_timeout_s` and `max_retries`

```toml
[engine]
request_timeout_s = 180
max_retries = 1
```

Neither could be set before. A model whose name suggested slow reasoning got a
450-second timeout, and the SDK retried twice on top of that — up to 1350
seconds on a single turn, inside a task budgeted at 900. The request-body
passthrough could not reach either, because both are client parameters.

Read by the OpenRouter adapter; the Anthropic, OpenAI and Gemini clients ignore
them. A value that is not a positive number stops the run and names the file.

### Fixed — the context window was capped at 200k for models that have far more

The window was a lookup table, and anything missing from it fell back to
200 000 tokens. That is safe for an unknown model and wrong for a known one:
`deepseek-v4-flash` has a 1 048 576-token window, `glm-5.3-flash` 1 310 720,
`kimi-k3` 1 048 576. The guard that drops the oldest turns was firing at 180 000
— about five times earlier than it had to, without saying so.

The real figure now comes from the catalogue, in both directions: a window the
table over-estimated comes down too.

### Fixed — the MCP server ignored per-model budgets entirely

One of the three places that build an OpenRouter client passed no budget at all,
so anything reached through the MCP server ran on a flat 120-second timeout
regardless of the model. All three now resolve it in one place.

### Note

Everything above degrades to the previous behaviour when the catalogue cannot be
reached: the lookup is cached for a day, needs no API key, gives up after three
seconds, and falls back to the name-based tables. A project with no `[engine]`
section sends byte-for-byte the same requests it did before.

The catalogue is only consulted for OpenRouter-shaped ids (`vendor/model`). A
run on a local backend such as ollama, or on a direct Anthropic, OpenAI or
Gemini key, never contacts openrouter.ai.

## [0.36.0] — 2026-09-21

Memory had never been measured. No project has ever had an embeddings table on
disk, so the cost of searching by meaning was unknown — and it turned out to be
not slow but impossible: at a hundred thousand facts a single vector query took
**ten seconds**. This release measures memory, fixes what the measurement found,
and gives memory a place to live other than the local file when one machine is
no longer the right answer.

### Changed — vector search got about 26× faster

Vectors were stored as JSON text. A search reads every one of them, so every
query rebuilt the entire corpus into Python lists before comparing anything.
They are now packed binary:

| facts | before | after |
|---|---|---|
| 10 000 | 1088 ms, 452 MB | **36 ms, 187 MB** |
| 100 000 | 10 210 ms, 4082 MB | **393 ms, 915 MB** |

Full-text search was never the problem — 7 ms at a hundred thousand facts.

The conversion runs once, on first open, in batches with progress in the log.
It resumes if interrupted, and it reclaims the freed space, because a storage
migration that leaves your database twice as large is not one anyone asked for.

### Changed — recall no longer waits for its slowest source

Memory is assembled from several sources: the wiki, past conversations,
insights, the framework's own knowledge, and any external provider you have
configured. They ran one after another, so a turn paid the sum of all of them
and one slow source held up everything.

They now run together under a single deadline and return whatever finished,
naming what was dropped. `[memory.recall] deadline_sec` sets it (default 2
seconds). External providers run concurrently with each other too, so one slow
remote source no longer starves the rest.

### Added — memory can live in an external engine

`[memory.store] backend = "remote"` sends insight search to an external memory
engine (any configured provider — Honcho, Mem0, Supermemory, your own), while
conversations and telemetry stay on your machine. That split is the shape of
the data, not a compromise: insights grow without bound and want a real index
behind them, conversation state is per-machine and no remote engine has a notion
of it.

Writing out is new. Providers can now accept insights as well as serve them, and
writes are **dual**: the local row is written first and stays the source of
truth, the external copy is best-effort and never fails your turn. A write that
did not land is marked and retried by `veles dream`, so "best effort" does not
quietly mean "sometimes never". Retracted facts are never pushed out.

### Added — `veles doctor` warns before memory searches get slow

Local vector search costs about 3.9 ms per thousand facts. Doctor now projects
the per-turn cost from your row count and tells you which of two thresholds you
are past, because they are different problems:

- **~48 000 insights** — about 190 ms, past the 200 ms budget recall is
  designed around. Turns are measurably slower. That is a warning.
- **~505 000 insights** at the default 2-second deadline — recall starts
  dropping whatever misses it, which shows up as memory quietly going missing
  rather than as a slow answer. That is an error, and doctor reads your own
  `[memory.recall] deadline_sec` rather than assuming the default.

No approximate-nearest-neighbour index was added, deliberately: a personal
project does not reach either number, and the case that does needs a remote
engine rather than a local index, since a million facts is about 3 GB of
resident memory per project.

No approximate-nearest-neighbour index was added, deliberately: a personal
project does not reach 48 000, and the case that does needs a remote engine
rather than a local index, since a million facts is about 3 GB of resident
memory per project.

### Fixed

- **Insights were being aged when they had not been used.** Retrieval marks an
  insight as referenced, and that mark decides both how recently-relevant it
  looks and which copy survives deduplication. It was applied to every match,
  including matches that lost ranking and never reached the model — and, once
  sources could be dropped at a deadline, to entire sources that were never
  consulted. Only insights that actually reach the prompt are marked now.
- **A project configured for a remote engine still read from the local file.**
  The recall path unwrapped the configured backend back into local storage, so
  the engine was built, ignored, and never asked.
- **`veles tool promote` did not save the change it announced.** The scope flip
  was written without a commit and rolled back on the way out.
- **Two connection leaks**: one per project-tree scan, one per runtime build.

### Migration

`memory.db` upgrades to schema v8 on first open, and the embeddings table is
rebuilt into the new format. Automatic; on the empty embeddings table every
current project has, it does nothing at all.


## [0.35.0] — 2026-09-21

Memory has never deleted an insight — but it has been hiding them, silently and
without a reason, and the only way to notice was that the agent stopped
applying something. This release makes that removal visible and reversible, and
separates where a fact came from the weight it carries when memory is searched.

### Added — a fact that leaves recall says why

Duplicate insights are collapsed during `veles dream`: one survivor per cluster,
the rest hidden. They were hidden by a structural link with nothing recorded
about the decision — you could not tell "merged as a duplicate" from
"superseded by something newer", and you could not undo it.

Each hidden row now carries the time and the reason, `/insights` prints it
beside the title (in Telegram too, where the marker did not exist at all), and
clearing two columns brings the fact back into recall. Nothing is deleted:
**the only way a fact leaves recall is by being hidden, and hiding is
reversible.**

### Added — where a fact came from, separately from how much it weighs

`confidence` was doing two jobs: recording provenance and setting rank. An
insight now also carries `origin` (`stated` — you said it, `derived` — the agent
concluded it, `heuristic` — a trigger guessed it) and `support_count`, the
number of observations behind it. Dedup adds each collapsed duplicate's support
to the survivor, so a fact observed five times keeps the number instead of
losing it in the merge.

**Ranking is deliberately unchanged.** Deriving weight from origin would
silently re-rank every insight you already have, so these two fields are
provenance you can read, and nothing more, until there is enough data to
compare before and after. Older rows get an origin only where their category
already states it; the rest stay unset rather than guessed.

### Fixed

- **A related insight no longer disappears from recall.** Recall hid every
  insight that appeared as the source of a link in `insight_refs` — a table
  meant for relations in general. The moment a second kind of relation was
  stored there, every linked insight would have vanished from memory. The
  supersession marker moved onto its own column; existing links were migrated
  exactly, since dedup was the table's only writer.
- **A stored fact can no longer cut the memory block short.** Everything
  between `<memory-context>` and `</memory-context>` is recalled text. An
  insight containing the closing tag ended the block early, and everything after
  it was read by the model as ordinary prompt text, outside any boundary. The
  tags are now escaped inside recalled content — escaped, not stripped, so a
  page that legitimately documents them stays readable.

### Migration

`memory.db` upgrades from schema v4 to v7 on first open. Additive and automatic;
nothing is rewritten except the supersession links, which move to their new
column and are dated by when the fact was last in use rather than by the moment
you upgraded.


## [0.34.0] — 2026-09-18

Nothing in `memory.db` or `.veles/*.jsonl` had ever been deleted. That is fine
until it isn't, and the day it isn't is not the day you want to start thinking
about it. This release gives you a policy to turn on — and, because two separate
defects this week turned out to be code that was written, tested, and never
connected to anything, it adds checks that fail when that happens again.

### Added — an optional ceiling on conversation history

**Your history is not touched unless you ask.** `[memory] turn_retention_days`
defaults to `0`, which keeps everything exactly as before. Set it to a number of
days and `veles dream` starts deleting raw conversation turns older than that.
The **insights** and rules extracted from them are kept forever either way — the
transcript is raw material, the insights are what it was read for.

Two conditions must both hold before anything is removed: the session is older
than the window, **and** the curator has already processed it. A session the
curator has not reached is never pruned, whatever its age, because deleting it
would destroy the transcript before anything had been learned from it.

What you give up by enabling it: `veles sessions search` only finds text inside
the window. `veles sessions list` still shows older runs — session rows are kept,
only the message bodies go.

### Changed

- **Rotated `traces.jsonl.*` and `events.jsonl.*` are pruned** — the newest 10
  are kept instead of every one ever written. At measured volume the first
  rotation is years away, so this closes a slow leak rather than an active one.

### Fixed

- **A Russian phrase in an English docstring** (`core/verify.py`), found by
  auditing every tracked file.
- **`configuration.md` is current in all 14 translations again.** It had been
  behind since a section was added in August and never synced; three more
  sections have accumulated since.

### Internal

Three checks that fail on a class of defect rather than on a symptom:

- a function reachable only from tests — the shape of the tool-telemetry code
  that sat uncalled for five months before 0.33.0 wired it up;
- a translated doc falling behind the English one, which is how the
  documentation gap above went unnoticed for a month;
- Russian in a comment or docstring (string literals are data — stopword lists,
  keyboard layouts, test fixtures — and are left alone).

Each ships with the existing violations as a baseline that may shrink and never
grow, and each was verified by reintroducing the defect it exists to catch.

## [0.33.0] — 2026-09-18

Two runs of the same input can disagree, and you cannot tell whether the model
changed its mind or the relay quietly sent you to a different machine. This
release is about closing the gaps where Veles knew something and did not say it:
which backend answered, which tools the agent can actually see, what its tools
have been doing, and whether an empty answer means "nothing to add" or "cut off
mid-sentence". Local models get the same treatment — llama.cpp can now be asked
whether it speaks tool calls instead of being assumed not to.

### Added

- **Pin which backend serves your model.** A relay like OpenRouter fans one
  model out across dozens of backends at different quantizations, so two runs of
  the same input can differ for reasons that have nothing to do with the input —
  and the difference gets blamed on the input. `[engine.request.<provider>]` in
  the project config is forwarded into the request body verbatim, so any knob the
  provider accepts works without waiting for Veles to learn about it. The section
  is keyed by provider name, so one config survives a backend switch. Declaring
  nothing changes nothing.
- **Traces now say which backend actually answered.** Alongside `request_extra`
  (what was asked for), each record carries `upstream_provider` (who replied),
  `reasoning_tokens` (how much of the completion budget went to thinking), and a
  real `est_cost_usd` instead of a hardcoded zero. One `jq` line over
  `traces.jsonl` tells you whether a whole run stayed on one backend — so a pin
  that quietly did nothing shows up as a fact rather than as unexplained
  variance.

### Fixed

- **`veles tool list` was telling you the agent had no tools while it was using
  them.** It reported a database table that builtins are never written to — and
  that self-authored tools were not being written to either, because the runtime
  had never passed the catalogue a connection. It is the first command you run to
  check whether the agent can see its tools, so it lied in exactly the state you
  were checking. It now reports what the agent is actually handed, with layout
  gating applied the same way, and names any tool file skipped for want of
  approval.
- **Tool telemetry was never recorded.** The code that writes it had no caller:
  every `uses` / `ok%` column read empty, and so did the detector that offers to
  turn three repetitions of the same tool sequence into a skill — it had nothing
  to detect. Every tool call is now recorded.
- **An empty answer is no longer retried when retrying cannot work.** If the
  response was cut off by the token cap, asking again with the same cap hits the
  same wall — and for a thinking model each attempt costs another full round of
  reasoning. That case is now reported as truncated, with the numbers needed to
  raise the cap. The other case, where the model simply finished without saying
  anything, gets up to three nudges instead of one.
- **`AGENTS.md is missing recommended sections` no longer prints on every run.**
  A file can only reach that state by being edited on purpose, so the reminder
  taught nothing and trained you to ignore stderr. `veles doctor` reports it once
  when you ask.
- **A typo in `[engine.request]` stops the run instead of being ignored.**
  Config is written by hand. A misspelt provider name used to mean the pin never
  reached the wire while the run carried on unpinned — silently invalidating the
  measurement it was written for.
- **Local models on llama.cpp can use tools without an env flag.** Only Ollama
  could be asked whether a model speaks tool calls; llama.cpp and
  OpenAI-compatible endpoints were assumed not to, and `VELES_LOCAL_TOOLS=1` was
  the only way in. Since tools are how an agent reaches a file or a URL at all,
  that made a grounded local answer impossible by default. llama.cpp is now
  asked directly — it reports what the loaded model's chat template supports.

## [0.32.0] — 2026-09-02

Goal mode had never actually been run. It was covered by unit tests with fake
agents, but nothing had ever driven the whole interview → plan → execute → check
cycle against a real model on a real task — and the first time anyone did, it
could not get past the interview. This release is what that run turned up,
plus the same treatment applied to a second run on a different model family and
a live knowledge base.

### Fixed

- **Goal mode now finishes.** Its interview phase was handed every tool in the
  box, including file writes and shell, while being asked to do nothing but ask
  you one clarifying question. Models did the obvious thing: they went and did
  the whole task instead of asking, never signalled that the interview was
  over, and the goal never advanced. The interview now gets no tools at all.
  Narrowing the set was tried first and wasn't enough — a prompt asking for
  restraint doesn't outvote an available tool.
- **A goal step now records what it did, not what it was asked to do.** The
  checkpoint used to save a copy of the step's own wording, and that was the
  only thing the reviewer saw when deciding whether to continue, re-plan, or
  call the goal finished. It had no way to tell a completed step from a failed
  one. Checkpoints now carry the outcome, which tools ran, and how the step
  ended.
- **"Your arguments weren't valid JSON" no longer sends models in circles.**
  When a long tool call gets cut off by the response limit, the leftover looks
  like malformed JSON, and the advice to re-send it was advice to fail exactly
  the same way — as one model did, three times, before giving up. A cut-off
  payload is now recognised as cut off, and the fix offered is to split it.
- **Research works without a terminal.** Following a link from your own web
  search was treated as a possible data-exfiltration attempt and required a
  confirmation nobody could give in a daemon, a channel, or a scripted run —
  so research simply couldn't run there. Search results and fetched page
  content are now told apart: a page can still not lure the agent to a new host,
  but a result you searched for is fair to open.
- **Planning mode can search again.** It refused web search as if it were a
  file write, so the plan phase had to plan blind — even though the planning
  toolset ships search on purpose.
- **Relative paths mean the same thing everywhere.** `write_file("notes.md")`
  resolved against whatever directory the process happened to start in, so the
  daemon, scheduled jobs and channels wrote outside the project and got
  refused. Shell commands already ran in the project; the file tools now agree.
- **A slow model no longer loses the whole run.** A timeout partway through a
  streamed response escaped as an untyped error with no retry and nothing
  saying "timeout" — two and a half hours of research, discarded because a
  reply took longer than two minutes.
- **Using a built-in skill stops modifying Veles' own files.** Usage counters
  were written back into the skill's source file, which for shipped skills
  lives inside the installed package — dirtying a checkout, or writing into
  site-packages. Telemetry now lives in the project database.

### Added

- **Response budgets adapt to the model.** A reasoning model spends its budget
  thinking before it writes anything, and 4096 tokens could be gone before a
  single visible character — the reply came back empty, which reads as the
  model failing rather than being cut off. Timeouts and token limits are now
  per-model. The economics differ too: a strong reasoning model thinks long and
  lands it in one pass, while a weaker one burns more tokens overall by
  iterating on a mediocre answer, so one flat budget penalised the model that
  was cheaper per finished task.
- **Wiki links are checked when you write a page.** Writing a page now reports
  which of its `[[links]]` point at nothing, and the linter flags broken links
  across the wiki. This exists because an agent wrote fifteen pages, logged that
  it had audited the cross-links and found none broken, and was wrong about a
  hundred of them — nothing in Veles could contradict it, because outbound
  links had never been checked at all.
- **Repeated reads stop piling up.** Reading the same file twice left both
  copies in the conversation, the stale one competing with the fresh one.
  Earlier identical reads are now collapsed, in a resumed session too.
- **Cache effectiveness is visible.** Token events now record how much of each
  prompt was served from cache, so it can be measured instead of assumed.

## [0.31.0] — 2026-08-18

Calling the daemon over HTTP used to be a one-way trip: you could start a run,
but the answer only ever appeared on the WebSocket stream, so a script that
didn't want to hold a socket open had no way to read the result it had just
asked for. That's fixed, and the daemon can now deliver the answer to a chat
for you.

### Added

- **Read a run's answer without a WebSocket.** `GET /v1/runs/{id}` now includes
  the finished text. The listing endpoint deliberately doesn't — it would grow
  by every answer the daemon has ever produced.
- **Let the daemon deliver the answer for you.** Pass `deliver_to` when you
  start a run — `telegram:<chat_id>`, or `origin` to reuse the chat the request
  came from — and the finished answer is sent there. A target that isn't valid
  is refused immediately rather than failing quietly later, and asking for
  delivery on a daemon with no channel running tells you so. Delivery never
  changes the run's own outcome: if the chat can't be reached the run still
  succeeds and reports why the send failed.
- **The daemon's HTTP API is documented** — how to submit a prompt, the three
  ways to get the answer back, and what the optional fields do. See
  [run as a daemon](docs/en/how-to/run-as-daemon.md).

### Fixed

- **A scheduled job with a bad delivery target is now rejected when you create
  it.** It used to be stored as-is and only fail much later, on the tick that
  tried to send — where nobody was watching. The check now covers every way a
  job gets written, including the agent's own `job_add`, which validated
  nothing at all (its sibling `task_add` always did).

## [0.30.0] — 2026-08-18

Four things Veles was getting wrong without telling you: flags it quietly
ignored, memory that came back empty, a tool that vanished from the toolset, and
an exit code that lumped every failure together. Mostly relevant if you drive
`veles run` from a script — but the memory fix applies to anyone who types a
whole paragraph into the chat.

### Added

- **`veles run` now says *why* it stopped through its exit code.** `0` finished,
  `1` the provider failed, `2` something is misconfigured (no model, no API key,
  unknown session), `3` it ran out of turns, `4` it ran out of token budget, `5`
  the model returned nothing, `6` it was interrupted. Previously anything that
  wasn't a clean finish came back as `1`, so a calling script couldn't tell "retry
  this" from "raise the budget" from "fix your config and stop retrying".
- **`veles doctor` reports whether semantic recall is actually working.** It
  tells you which embedding backend is in use, and warns — with the fix — when
  insight recall has silently fallen back to keyword-only matching.
- **A guide to calling `veles run` from another program**, covering the pieces
  you would otherwise discover in production: which stream carries what, why
  `stdin` must be redirected, that Veles has no wall-clock timeout of its own,
  and how to make knowledge accumulate between separate runs. See
  [embedding `veles run`](docs/en/how-to/embed-veles-run.md).

### Fixed

- **Flags written before the command name were silently ignored.** `veles
  --verbose run "…"` ran without `--verbose`; the same for `--model`,
  `--stream`, `--max-tokens-total` and `--project-root`. Worst of all,
  `veles --provider anthropic run "…"` ran on OpenRouter *and* overrode the
  provider configured for the project — passing a value you never typed off as a
  deliberate choice. Both positions work correctly now.
- **A long question came back with no memory at all.** Search required every
  single word of your question to appear in one stored note, so anything longer
  than a few words — a paragraph, a pasted log line, a stack trace — matched
  nothing, and no memory was attached to the answer. Nothing indicated this had
  happened. Longer questions are now matched on the words that carry meaning and
  ranked by relevance; short keyword lookups behave exactly as before. The same
  fix applies to wiki search, which had the identical problem.
- **Recall of past insights was silently keyword-only if you had an API key but
  no local embedding model.** Embeddings for your own notes are computed
  on-device on purpose — your project's text is never sent to a cloud embedding
  service — so an API key alone never enabled them, and the setup notice stayed
  quiet because it counted a cloud backend as "configured". You now get the
  notice, and `veles doctor` says so plainly.
- **A tool file you hadn't approved disappeared without a word.** Approval is
  keyed to the file's contents, so *editing* an approved tool un-approves it —
  and the agent then simply never saw that tool, no error, no refusal. It could
  work around the gap and answer confidently with the tool's data source never
  consulted. The skipped file is now reported on stderr.

### Changed

- **The embedding setup notice explains the actual requirement.** It used to
  offer "set an API key" as one of three equal options for better recall. For
  recall of your own insights that has never worked; the notice now says a local
  model is what enables it, and that an API key improves the other rankings
  (file relevance, skill patterns) instead.

## [0.29.0] — 2026-08-03

### Added

- **Photos you send to the bot are actually looked at.** An image arriving in a
  chat is now described before the agent starts answering, using the model your
  project already uses — a multimodal model needs no setup at all. Previously
  every photo came back with "no vision adapter is configured", because Veles
  shipped no such adapter for the setting to point at.
- **A new `[vision]` section for how images are read.** `mode = "model"` (the
  default) describes them with the vision model; `"ocr"` runs Tesseract only —
  local, free, no model call, good for scans of text; `"ocr+model"` does both,
  verbatim text first; `"off"` skips reading entirely and just keeps the file.
  Set `[vision] model = "<provider>:<model>"` when your main model is text-only
  — any vision-capable provider works, including a local one
  (`ollama:llava`, `llamacpp:…`, `openai-compat:…`). Changes take effect on the
  next photo, no daemon restart. See
  [configuration](docs/en/reference/configuration.md).
- **The image itself stays available.** Alongside the description, the file is
  kept, so a follow-up question about the same picture is answered from the
  image rather than from the first description.

### Changed

- **Forwarded posts and albums are gathered into one request together with your
  comment.** Telegram marks a message as forwarded (or as part of an album), and
  Veles now uses that: once such a message arrives, the bot waits longer (12 s by
  default, up to 12 messages) so the rest of the forwards *and* the comment you
  type after them arrive first, and answers once. Ordinary typed messages keep
  the short 3 s window. Both are configurable —
  `[channels.telegram] debounce_seconds` and `forward_debounce_seconds`.
  (Trade-off: a lone forwarded post with no comment now waits out the wider
  window before the bot replies; lower `forward_debounce_seconds` if that feels
  slow.)
- **The window for a burst of typed messages went from 1.5 s to 3 s** — 1.5 s
  only caught messages sent almost simultaneously.

### Fixed

- **A forwarded photo, document or voice message no longer reads as your own.**
  The "Forwarded from …" attribution was rendered for forwarded *text* only, so
  the agent could answer as if you had taken the photo yourself.
- **Image descriptions no longer fail with an authentication error when routed
  through OpenRouter.** The vision call ignored the stored credentials and fell
  back to whatever `OPENAI_API_KEY` happened to be set, so it authenticated
  against the wrong service.

## [0.28.1] — 2026-07-23

### Fixed

- **Telegram: a burst of messages sent in quick succession is now handled as one
  request.** When you sent several messages back-to-back — a comment plus a few
  forwarded messages, or a multi-message paste — the bot used to fire a
  premature reply on the first one (often a confused "which task do you mean?")
  before the rest had arrived, and treat the remainder as separate turns.
  Everything that lands within a short window now coalesces into a single turn.
  (Trade-off: a lone message now waits ~1.5 s before the agent starts, so a
  burst has a chance to be gathered.)

## [0.28.0] — 2026-07-23

### Changed

- **Much lower cost on long and repeated conversations — prompt caching now
  actually kicks in.** Veles marks the stable part of each prompt for caching,
  but through OpenRouter a conversation's requests could scatter across
  different backends, so the cache rarely hit. Veles now passes a per-session
  routing key so every request in a conversation sticks to the same provider —
  measured at **~90 % cheaper input** on the repeated part of a session (e.g.
  large context re-sent every step in an agentic loop). It uses OpenRouter's own
  provider selection with a sticky hint — no provider is hard-pinned, so
  availability and fallback are unchanged. (Caching also depends on the model's
  minimum-prefix rule — e.g. Claude Sonnet caches from ~1 k tokens, Haiku from
  ~4 k.)
- **More accurate context-window management.** Veles now counts tokens with a
  real tokenizer instead of a bytes-based estimate, so it summarises older turns
  closer to the true limit instead of prematurely — fewer unnecessary
  summarization passes, and non-English (e.g. Cyrillic) sessions are no longer
  over-counted ~2×.

## [0.27.0] — 2026-07-23

### Changed

- **Lower latency and token cost on repeat, resumed, and tool-heavy runs.**
  Three hot paths that used to redo work every time are now cached: the
  relevance ranking of your project's files (embedded once per file, reused
  until the file changes), the summary of older conversation turns (reused when
  you resume a session instead of being regenerated), and — the big one — the
  tool results in an agentic loop, which used to be re-sent uncached on every
  step and are now covered by the rolling prompt cache. Long, resumed, and
  tool-driven sessions do noticeably less redundant work. The tool-result
  caching self-heals: if a provider ever rejects it, the turn silently proceeds
  without it (and you can force it off with `VELES_CACHE_TOOL_TAIL=0`).
- **Better memory recall.** Saved insights now carry a confidence signal — facts
  you explicitly asked to remember rank fully, ones the agent merely inferred
  from an error-recovery moment carry less weight, and the lowest-trust ones are
  kept out of the prompt entirely. When recall has more matches than fit, it now
  says so ("showing N of M — refine the query for the rest") instead of silently
  trimming the list.

### Removed

- Dropped an unused vector-search backend that was, in practice, slower than the
  default — nearest-neighbour memory search is now simpler and no slower.

## [0.26.0] — 2026-07-22

### Added

- **Richer, cleaner replies in Telegram.** Answers now use more of Telegram's
  formatting: crossed-out text (`~~like this~~`), hidden spoilers (`||like
  this||` — tap to reveal), and long quotes that collapse into an expandable
  block instead of flooding the chat. Tables line up in neat columns instead of
  drifting out of alignment.
- **A one-tap Copy button for commands.** When a reply is a single short code
  block — the classic "run this:" answer — it comes with a 📋 Copy button so you
  can grab the command without selecting text by hand.
- **Answers in group chats reply to your message.** In a group, the bot's answer
  is now attached as a reply to the message that asked, so with several people
  talking it's always clear what it's answering. One-on-one chats stay as they
  were.
- **A quiet 👀 instead of a "queued" message.** When you send a follow-up while
  the bot is still busy, it now reacts with 👀 on your message rather than
  posting a separate "queued" line — less clutter in a busy chat. (It still
  falls back to a text note where a reaction isn't possible.)

### Changed

- **Links in replies no longer blow up into big preview cards.** Agent answers
  are mostly text; incidental links used to render large link-preview cards that
  crowded the chat. Previews are now off by default on answers.

## [0.25.0] — 2026-07-20

### Added

- **The bot tells you it's on it — in context, not a bare "...".** When your
  message needs real work (searching your knowledge base, writing a page, or
  building a tool), the reply is now a short "on it — searching the knowledge
  base…" the moment the agent actually starts that work, and the finished
  answer arrives as its own message right after. A question it can answer
  outright still comes back immediately, with no placeholder in between.
- **One message at a time per chat, and you're told when you're queued.** If you
  send a follow-up while the bot is still working on the previous message, it
  now replies "queued — I'll get to it right after this one" and runs your
  messages strictly in order instead of overlapping them. Different chats still
  run in parallel.

### Fixed

- **Long answers are no longer cut off.** A reply longer than one Telegram
  message used to be truncated with an ellipsis, silently dropping the tail.
  It's now split into several messages, each self-contained (formatting like
  bold/italic is closed and reopened across the split), so you get the whole
  thing.
- **The bot no longer forgets the conversation you're in.** The link between a
  chat and its session was saved only when a turn finished cleanly, so a turn
  that errored or was interrupted could leave the chat unlinked — and the next
  message started a fresh, empty session that had lost the thread. The link is
  now established before the turn can fail and preserved even on error, so the
  chat keeps its history instead of restarting cold.

## [0.24.0] — 2026-07-15

### Added

- **Proactive reminders that actually reach you.** While the agent is idle it
  now scans your recent conversation for *definite dated events* — the ones you
  clearly said would happen at a specific time — and quietly schedules a
  reminder for each. When the time comes the daemon delivers it to your last
  active chat on its own, without you asking. It is deliberately conservative:
  only things that will definitely happen, nothing speculative. Repeated scans
  never create duplicate reminders, and if an event's time changes the reminder
  moves with it.
- **Reminders reply into a real conversation.** A delivered reminder is recorded
  in the chat's session (opening one if the chat has none yet), so when you
  reply — "snooze an hour", "what was that about?" — the agent already knows
  which reminder it just sent and continues coherently instead of starting cold.
- **A delivery log you (and the agent) can trust.** Every reminder/notice
  delivery attempt — sent, deferred because no channel was active yet, or failed
  because the channel was down — is recorded. Ask the agent "did my reminder go
  out?" and it answers from that log instead of guessing.

### Fixed

- **Reminders no longer silently go missing.** Scheduled notices used a delivery
  path that could quietly drop a message when there was no originating chat to
  reply to, so reminders arrived unpredictably — sometimes yes, sometimes not.
  Delivery now resolves your last active channel dynamically and, if it can't
  deliver yet (a channel isn't up, or none is active at that instant), it keeps
  the reminder pending and retries on the next sweep rather than dropping it.
- **The agent no longer promises to "send it shortly" and then goes quiet.** A
  turn used to end the moment the model replied without taking an action — so a
  message like "collecting that now, I'll send it over" was treated as the final
  answer and the follow-up never came until you sent another message. The agent
  is now told plainly that a turn is one-shot: it must finish the work and give
  you the result in the same message, or schedule a real reminder — not promise
  deferred work in prose. As a safety net, a turn that would end with an empty
  message is nudged once to actually answer instead of leaving a blank reply.

## [0.23.1] — 2026-07-14

### Fixed

- **A looping daemon could grow its log file without bound and defeat
  rotation.** The daemon log had two independent writers — the rotating
  handler (which caps size and keeps a fixed number of backups) and a raw
  redirect of the process's stdout/stderr into the same file, which never
  rotated. When a daemon got stuck in a loop and spewed raw output
  (tracebacks, library retries, stray prints), that second writer grew the
  file endlessly; after the handler rotated, the raw stream kept writing to
  the renamed file, and once it aged past the backup limit the still-open
  file lingered on disk with no name, quietly eating space. Huge log files
  became slow to open and dragged on performance. Now the daemon funnels its
  stdout/stderr through the rotating handler, making it the single writer, so
  the total on-disk log size stays capped by `[daemon.logging] max_bytes` ×
  `backup_count`. An interactive `veles daemon start --foreground` in a
  terminal still prints to the console, and `VELES_LOG_NO_FUNNEL=1` disables
  the funnel for debugging.

## [0.23.0] — 2026-07-13

### Added

- **Critical-operation confirmations now appear as inline keyboards in
  Telegram.** When a security gate demands explicit consent mid-turn —
  the always-confirm policy or the prompt-injection exfiltration guard
  (e.g. the agent fetching a URL that appeared in untrusted content) —
  the chat now shows a "⚠️ Critical operation" message with **Allow** /
  **Cancel** buttons, the same interactive flow trust and approval
  prompts already had. No answer within 5 minutes still means deny, so
  the fail-closed behaviour of 0.22.2 remains the floor; the daemon log
  keeps recording every auto-denied confirmation that happens outside a
  channel turn.

## [0.22.2] — 2026-07-13

### Fixed

- **The daemon could freeze mid-turn on a security confirmation.** When a
  critical-ops gate fired inside a daemon turn (e.g. the
  prompt-injection exfiltration guard on `fetch_url`), the daemon
  printed the interactive `Type 'yes'` prompt into its log and then
  blocked the whole event loop waiting for terminal input that could
  never arrive — the channel chat hung on "…" forever. The detached
  daemon inherited the launcher's terminal as stdin, which made it look
  interactive. Now the spawned daemon's stdin is detached, and the
  daemon installs a fail-closed confirmer: such operations are
  auto-denied with a WARNING in the daemon log, and the agent reports in
  the chat what was blocked and why. To approve a blocked operation, run
  it interactively from the REPL/CLI.

## [0.22.1] — 2026-07-13

### Fixed

- **Second project's daemon crashed on `address already in use` when both
  projects had `[daemon] port` in their config.** The project wizard
  writes its default port (8765) into every project it creates, so
  wizard-made projects all "pin" the same port without the user ever
  choosing one — and 0.22.0 honoured a pinned port verbatim. Now, when
  the configured port is busy and its occupant identifies itself as the
  Veles daemon of a *different* project, the start rolls to the next
  free port with a warning naming the occupant. A busy port held by
  anything else (a foreign service, a dying predecessor) or by this
  project's own daemon still keeps the pin and fails loudly, and an
  explicit `--port` is always used verbatim.

## [0.22.0] — 2026-07-13

### Added

- **Per-project daemons.** `veles daemon start` in a second project no
  longer refuses with "daemon already running" — every project gets its
  own daemon. The single-instance lock is now per project
  (`~/.veles/daemon-<slug>.pid` instead of one machine-global pid file),
  and when no port is configured the daemon binds the first free port
  from 8765 upward instead of always contending for 8765. A port pinned
  via `[daemon] port` in the project config is still used verbatim.
  `veles daemon stop`/`status` now address the daemon of the project you
  are in (and say so when run outside a project); daemons of other
  projects are managed via `veles daemon list`/`restart`/`delete`, as
  before.

### Fixed

- **Telegram polling no longer floods the daemon log when the machine is
  offline.** `getUpdates` failures now retry with exponential backoff
  (2s doubling to a 60s ceiling, reset on success) and log one WARNING
  per outage — on the first failure, when the error text changes, and as
  an occasional heartbeat — plus an INFO line with the failure count once
  polling recovers. Previously a fixed 2-second retry logged one
  identical WARNING per attempt for the entire outage.
- **`getUpdates failed:` log lines with an empty reason.** The HTTP
  session had no explicit timeouts, so a hung DNS lookup could stall a
  poll for minutes and die as a bare `TimeoutError` whose message is
  empty. The session now sets connect/read timeouts, and the log
  formatter falls back to the exception's repr when its message is
  empty.
- **Reminder and job runner warnings appear in the daemon log without a
  timestamp or level prefix.** The daemon's file logging now covers the
  whole `veles.core` subtree, so `reminder … delivery failed` lines carry
  the standard `[WARNING] veles.core.reminder_runner:` prefix instead of
  arriving as bare stderr text.

## [0.21.2] — 2026-07-10

### Fixed

- **Scheduled reminders can no longer be silently undeliverable.** A live
  "remind me tomorrow at 11:00" produced a task with `deliver_to="chat"`
  (not a valid delivery target) scheduled for a date in the *previous
  year* — the model had no clock in its context and computed "tomorrow"
  from training priors. The reminder then failed delivery on every
  60-second sweep, forever, and the user never saw it. Four fixes:
  - `task_add`/`task_snooze` validate an explicit `deliver_to` against the
    delivery-target grammar at write time and reject it loudly, so the
    model corrects itself in the same turn; the `origin` keyword now
    resolves to the concrete originating chat immediately.
  - Due/snooze times in the past are rejected with an error that echoes
    the current UTC time, so the model recomputes the intended date.
  - The reminder sweep distinguishes permanent failures (malformed target
    — disabled with one ERROR log) from transient ones (channel not up —
    still retried).
  - The agent's system prompt now carries a volatile `<runtime-context>`
    clock block (weekday + UTC date/time) after the prompt-cache
    breakpoint, anchoring every relative-date computation.

### Docs

- README (all 15 languages) and the reference docs (all 14 locales)
  brought back in line with the shipped CLI: real REPL editor keybinding
  (`Ctrl+X Ctrl+E`), `--max-iterations` default `1000`, `veles organize` /
  `veles layout sync` / `veles add --recursive/--glob` documented, removed
  `wiki/sources`, `VELES_HOME`, and `VELES_CONFIG_FILENAME` leftovers.

## [0.21.1] — 2026-07-09

### Fixed

- **`veles daemon start` can no longer claim success for a daemon that died
  at birth.** The detach parent used to trust the pid file alone: a child
  that appeared, got reported as "daemon started (pid …)", then crashed one
  second later inside `run_app` (port still held by a dying predecessor)
  left a registry entry pointing at a corpse and no trace of the crash. The
  parent now waits until the child serves `/v1/health` and the reported pid
  matches the child it spawned — a mere TCP listener on the port (the dying
  predecessor) does not pass. A child that dies while coming up, or a port
  served by another process, is a loud error with the daemon-log tail.
- **A detached daemon's crash is visible.** The child's stdout/stderr are
  appended to `~/.veles/logs/daemon-<slug>.log` instead of `/dev/null`
  (every spawn site: detach, named restart, picker start, wizard
  autostart), and `run_app` failures additionally log a structured
  traceback — "address already in use" now shows up both in the terminal
  and in the log.
- **Config validation no longer flags the channel keys the wizard itself
  writes.** `daemon start` validates the security config sections before
  anything imports a channel module, so the platform registry was empty
  and the validator degraded to base keys — falsely warning that the
  legitimate `whitelist` key (the security control itself) was "likely a
  typo". The validator now bootstraps the builtin platform registry.

## [0.21.0] — 2026-07-09

First release published since 0.9.0 — the 0.20.0 section below was cut but its
tag was never pushed, so this release also delivers everything listed there.

### Added

- **Agent-driven ingestion and research (M204–M207).** `wiki_add` is now an
  agent-callable tool built on a shared batch-ingest kernel; in the daemon it
  runs as a structured background job with notify/resume, so a channel chat can
  kick off a long ingest and get pinged when it lands. Job tools moved from
  core into the `agentops` module, and a new agent-callable `research` tool
  runs deep research inline or in the background.
- **Fenced tool calls now self-correct.** When a local model emits a malformed
  ```veles-tool``` block, the parse errors are fed back to the model as a
  corrective message (capped per turn) instead of being dropped silently — the
  model re-emits the call instead of the turn dying.
- **Stronger loop-safety.** A per-call stall guard catches a model repeating
  the same tool call without progress and a token-budget nudge warns the model
  before the budget runs out; the iteration cap is now a runaway backstop
  rather than the everyday stop.
- **`veles daemon start` walks a Textual wizard (M208).** An interactive start
  with no channel configured opens the same modal wizard style as the project
  setup: confirm/adjust host and port (persisted to the project config), then
  the registry-driven channel flow — instead of a bare stdin `[y/N]` prompt.
  Falls back to stdin prompts on degraded terminals.

### Changed

- The project wizard no longer offers the wiki-seed step (bulk-copy into
  `sources/seed`) — content enters through `veles add`'s topic routing instead.

### Fixed

- **Local-model reliability wave.** The fenced-tool parser now recovers
  multi-object blocks, unclosed final blocks, and flat-shape arguments; raw
  tool-call JSON is scrubbed from the visible chat stream; index-less parallel
  tool-call deltas from OpenAI-compatible backends no longer break dispatch;
  and the REPL passes the resolved model to local providers so ollama models
  with native tool-calling are auto-detected instead of being forced through
  the fenced path.
- **The post-turn learning loop no longer eats the session.** Curation success
  is judged by the persist tools that actually ran (thinking models with empty
  final text no longer re-curate forever, duplicating wiki pages); the curator
  runs on its own token budget silently instead of dying on the user's budget
  mid-pass and printing raw `<budget exhausted>` into the chat; the
  poison-pill guard survives dream-state saves; and the curator queue can no
  longer be blocked by a single failing session.
- **The REPL stays responsive end-to-end.** Post-turn memory upkeep
  (insight extraction + curation) runs on a background worker instead of the
  event-loop thread — the chat no longer freezes for seconds between the
  streamed answer and the done marker (a muted "memory upkeep" chip shows
  while it finishes). Streaming output also moved off the event loop, any
  turn is cancellable with Esc, and a step-limited turn reports itself as
  incomplete instead of "done".
- **REPL correctness details.** `/clear` (and the new `/new` alias) resets the
  token/context/cache counters; `-c`/`--resume` replays the full previous
  conversation instead of a 4-message, 600-char stub; the HUD shows real token
  counts on tool-call-only turns; `veles.*` log records go to `.veles/repl.log`
  instead of the chat; Ctrl+<letter> works under the kitty protocol on a
  Cyrillic layout.
- The context compressor estimates tokens by UTF-8 bytes, so Cyrillic-heavy
  sessions compress when they should; `ask_user` coerces stringified options so
  the picker never renders a choice character-by-character; wiki-migration
  prompts got graceful `read_file` error handling and finish-the-job guidance.

## [0.20.0] — 2026-07-07

Supersedes the internal-only 0.10.0 bump; this is the first release cut since 0.9.0.

### Added

- **Project memory is alive in the default REPL (M191).** Every turn injects
  relevant recall and runs the learning loop (insight extraction + curation)
  after the turn — the "never forgets" promise now holds in the main interface,
  not only in batch `veles curate`.
- **Embedding-backed semantic recall (M192).** Insights are recalled by meaning
  through an on-device embedding backend (Ollama), with **no cloud egress** of
  your content; it self-initialises on first use and degrades cleanly to
  keyword search when no local embedder is present.
- **Content-aware ingestion (M203).** `veles add` extracts the distinct topics
  a source is *about* and routes each to a topical wiki page via
  find-or-create-or-patch — no more 1:1 file→page dumps named by filename or
  date. One file can yield several topic pages, and a related source patches the
  existing page instead of duplicating it. `veles add <dir> --recursive` walks a
  whole folder.
- **Human-approval gate for self-authored tools (M199).** Tools the agent writes
  to `.veles/tools/` must be reviewed with `veles tool approve` before they run;
  the approval store lives outside the agent's write sandbox, so a dropped file
  cannot self-approve.
- **Fail-loud config validation (M201).** `veles doctor` and `veles daemon
  start` flag unknown keys in the security-relevant config sections
  (channels / daemon / mcp) instead of silently ignoring a typo.
- **Layout-declared behaviour prompts (M188–M190)** with opt-in writable zones
  (M189); the default llm-wiki layout uses them for migration + log-patch
  behaviour.

### Changed

- **The bare `veles` chat is now the inline prompt_toolkit REPL (M187).** The
  full-screen Textual chat was retired so native terminal selection/copy work;
  the first-run + project setup wizards and the `veles daemon` control panel
  remain interactive Textual TUIs.
- Internal hardening: `veles.core` decoupled from the cli/daemon/channels layers
  with a CI invariant (M194); the REPL was decomposed from a single 2600-line
  module into focused mixins (M195).

### Security

- **Untrusted-content egress gate (M198).** A tool call that would send data to
  a destination named in untrusted content read during the run is gated (hard
  confirm; fail-closed when unattended), and runs *before* the autopilot policy
  so an autopilot window cannot bypass it.
- **Autopilot network egress is journaled (M200)** to the project log.
- **`veles add` hardened against prompt-injection in ingested files.** The
  ingest agent has no network-egress tool; a URL source is fetched by the CLI
  (wrapped as untrusted) and handed to the agent inline, so injected
  instructions inside a source document have no exfiltration channel.
- **Delegated workers cannot exceed their parent's tools** — `delegate`
  intersects the requested toolset with the running agent's scoped tools.

### Fixed

- **Memory recall no longer goes silent (M193).** A broken full-text index
  surfaces via `veles doctor` (repairable with `veles doctor --fix`) instead of
  silently returning nothing; un-distilled recent turns survive until the first
  curation.
- **Semantic recall is no longer dormant** on the first REPL turn or in a
  single-shot `veles run` (the embedding backend self-initialises on first use).
- **`veles daemon` no longer hangs when piped / non-interactive** — it falls
  back to printing the daemon list.
- **`--provider <name>` is honored even when it equals the default provider.**
  Previously `--provider openrouter` (openrouter being the built-in default) was
  indistinguishable from "not passed", so a user whose config `default_provider`
  was a different backend (e.g. `ollama`) could not CLI-override back to
  openrouter — sub-agents and the curator fell through to the config default and
  errored. The flag is now tracked explicitly.
- **Documentation honesty (M196 + docs sweep).** The CLI reference and all 14
  README translations were corrected: accurate first-run wizard steps, complete
  command tables (`tool approve`, `organize`, `browse`, `schema`, `self-doc`,
  `layout`, full channel subcommands), and no phantom environment variables.

## [0.9.0] — 2026-07-04

### Added

- **Veles now answers "how do I do X in Veles" from its own documentation
  (M186).** A framework-global knowledge source lets the agent answer usage
  questions accurately — even on weak or local models — instead of guessing
  from priors. It pairs a live capability skeleton derived straight from the
  CLI (commands, flags, builtin skills and tools, so it can never go stale)
  with curated how-to notes shipped in the package. Relevant docs surface
  automatically in recall when you ask a how-to question, and stay out of
  ordinary coding turns (the retrieval gate keys on curated topics, not
  incidental prose). A new `veles_help` tool provides on-demand deep lookups,
  and a freshness test keeps the notes honest — a note can never reference a
  command, flag, skill, or tool that no longer exists. This is layout-
  independent: it works in every project layout, separate from and
  complementary to the per-project `self-doc` state snapshot.

## [0.8.3] — 2026-06-30

### Fixed

- **Goal mode no longer gets stuck before it can act (M185).** At the CONFIRM
  step the agent only accepted `yes/да/ok/ага` as confirmation, so a natural
  "Продолжи" / "Вперёд" / "continue" reply was read as *edits* and bounced back
  to the interview — the goal could never reach its execute phase. The
  confirmation parser now understands common bilingual "proceed" replies, and
  the "how to confirm" hint is shown the moment the agent asks for confirmation
  (previously it was only emitted on a turn that never happens in the TUI).
- **Planning mode now tells you how to leave it (M185).** When a change was
  blocked in planning mode, the agent invented a non-existent `veles mode
  standard` command. The planning prompt and the block message now point to the
  real action — `/mode writing` (or Shift+Tab) — and the model is told not to
  invent commands.
- **Copy behaviour in the TUI (M185).** A plain drag-select no longer copies on
  its own. Copying the selection is bound to **⌘C** (macOS) and **Ctrl+Shift+C**
  (Linux/Windows) and confirms with "copied to clipboard". Whether ⌘C reaches
  the app depends on the terminal (default iTerm2/Terminal.app keep ⌘C for their
  own Copy); Ctrl+Shift+C works almost everywhere, and `VELES_TUI_MOUSE=0`
  restores native terminal selection + native ⌘C.

## [0.8.2] — 2026-06-30

### Fixed

- **Daemon/channel runs never curated — wiki pages stayed empty (M184).** A
  wiki-llm Telegram diary bot accumulated sessions in `memory.db` but produced
  zero curated wiki pages. The continuous-curator eligibility gate keyed off the
  raw `args.provider`, but `daemon start` defaults `provider=None` (the provider
  flows from project/user config), so the gate returned `False` on every
  post-turn hook and the curator body never ran. `daemon start` now writes the
  resolved provider back into `args.provider` before building the post-turn hook
  (which every channel reuses), and the gate now keys off `has_api_key(provider)`
  instead of `PROVIDER_API_KEY_ENVS` membership — which also makes the curator
  eligible on local providers (`ollama`/`llamacpp`/`openai-compat`) while
  cli-delegate providers stay ineligible. (On a local provider, emitting pages
  also needs `VELES_LOCAL_TOOLS=1` with a tool-capable model, since the curator
  persists via tool calls.)
- **TUI: text selection / copy in the output, and keyboard focus stays on the
  input (M183b).** Two follow-ups to the M182 mouse-on default:
  - The final (sealed) assistant reply could not be selected or copied. It was
    a `Static` carrying a `rich.markdown.Markdown` renderable — which renders
    nicely but whose text Textual's selection cannot extract. Sealed replies are
    now rendered with a Textual `Markdown` *widget*, which composes selectable
    child widgets, so drag-select works on the formatted output. `Ctrl+C` now
    copies the active mouse selection (via the native clipboard — pbcopy/xclip,
    no OSC52 needed) when there is one, falling back to the last-reply copy /
    double-tap-exit otherwise.
  - Keyboard focus no longer switches to the output pane. `ChatLog` is now
    non-focusable (`can_focus = False`), so a mouse click on the output can't
    steal focus from the input line; the Composer is the only focusable widget.
    On iTerm2/macOS, `Option+drag` then `⌘C` also works (native terminal
    select+copy); plain drag uses `Ctrl+C`.

## [0.8.1] — 2026-06-29

### Internal

- **Release workflow is now idempotent on a re-run / re-pushed tag.** The
  `github-release` job ran `gh release create` unconditionally, so re-pushing a
  tag (or re-running the job) failed with "a release with the same tag name
  already exists"; it now updates the existing release in place (`gh release
  edit` + `gh release upload --clobber`). The PyPI publish step gained
  `skip-existing: true` so an already-published version no longer fails the
  re-run.

## [0.8.0] — 2026-06-29

### Changed

- **TUI scrolls with the mouse wheel / trackpad (M182).** Mouse-reporting is now on by default,
  so the wheel / trackpad scrolls the chat directly (scrolling back to the bottom re-arms
  auto-follow). Native drag-select is preserved via the terminal's standard modifier-bypass —
  **Shift+drag** on most terminals, **Option(⌥)+drag** on iTerm2/macOS — then **⌘C** copies;
  **⌘V / Ctrl+V** paste is unchanged. Where a terminal's modifier-bypass is weak (e.g. macOS
  Terminal.app), the in-app Textual selection → OSC52 fallback (`super+c` / `ctrl+shift+c`)
  remains. Set `VELES_TUI_MOUSE=0` to keep mouse-reporting off for pure unmodified terminal
  select (no wheel scrolling).

### Fixed

- **Calling a tool that isn't in the active mode no longer dead-ends in a cryptic
  error (M183).** When the model called a tool absent from the current mode's
  toolset (e.g. `create_plan`, which is planning-only, while in writing/direct
  mode), dispatch let `registry.dispatch` raise `KeyError` and fed the model a
  bare `<error: KeyError: unknown tool 'X'>` — which it couldn't recover from and
  tended to "explain" with a fabricated rationale. `_dispatch` now short-circuits
  on an unknown tool with a recovery-oriented refusal: it distinguishes a tool
  that exists but is gated to another mode from one that doesn't exist at all,
  lists the tools available now, and tells the model to switch modes or proceed
  without it. A `decision="deny", rule="unknown_tool"` event is recorded for
  audit. The tool's handler is never invoked.

### Removed

- **TUI read mode and keyboard scrolling (M182, supersedes M176/M179).** Removed the **Ctrl+O**
  focus toggle and the **PageUp / PageDown / Ctrl+Home / Ctrl+End** scroll bindings; chat
  scrollback is now the mouse wheel / trackpad. **Esc** still returns focus to the input after a
  mouse click lands on the chat pane.

## [0.7.2] — 2026-06-27

### Fixed

- **`veles init` heals a directory copied from another project (M181).** Root cause of the
  "agent answered about the wrong (deleted) project" report: `cp -R old new && cd new && veles
  init` carried `old`'s `.veles/` — its stale default AGENTS.md titled `# old` and its
  `memory.db` — and init silently kept both, so the system prompt named the wrong project and
  recall surfaced the wrong history. Now init **regenerates** an AGENTS.md that is still the
  unmodified scaffold default whose title ≠ the new project name (a customised AGENTS.md is
  always preserved), and **warns** when it completes a `.veles/` that carries a prior project's
  `memory.db` (pointing at `veles curate` / removing the file for a clean slate).

### Added

- **`veles doctor` catches stale/cloned project state (M181).** Two new checks for the same
  class of confusion (catch files that pre-date the init fix or were copied in after init):
  `agents_md_identity` warns when AGENTS.md is still the unmodified scaffold default but its
  `# ` title names a *different* project; `registry_paths` warns about project-registry entries
  whose directory no longer exists, with a `veles project remove <slug>` fix hint.

## [0.7.1] — 2026-06-27

### Added

- **TUI read mode (M179).** Switch keyboard focus from the input field into the output pane
  and navigate it with the arrow keys. **Ctrl+O** toggles focus between the input and the
  output (the primary, Mac-friendly entry — Mac laptops have no PageUp/Home keys); the focused
  pane shows an accent left edge and auto-follow pauses. Once in the output, **↑/↓** move
  through it; **Esc** returns to the input. PageUp / Ctrl+End still work where those keys
  exist (Ctrl+End also jumps to the bottom and resumes auto-scroll).

### Changed

- **`/wiki` is hidden on non-wiki layouts (M180).** The slash command is now registered only
  when the active layout enables the wiki engine, so it no longer appears in `/help` or
  completion on `bare`/`notes` projects; `/help` and the `/save` hint adapt to the layout.

### Fixed

- **Removed wiki artifacts from core (M180).** `veles schema fix`'s fallback AGENTS.md template
  no longer references the removed `veles ingest`/`query`/`lint` commands or assume the wiki
  directory layout; `subproject_proposer.detect_clusters` is gated on the wiki engine (so
  `veles subproject suggest` no longer tries to build a Wiki on a non-wiki project); the
  TUI `/save` wiki import moved inside its engine-gated branch.

## [0.7.0] — 2026-06-26

### Added

- **`veles organize` — layout-driven project tidy-up (M175).** Reorganizes a project's
  content the way its active layout dictates (cluster wiki pages into
  `concepts`/`entities`/`sources`, repair `[[wikilinks]]` and INDEX, dedup; sort a `notes/`
  tree; a `bare` project has no organize step). **Propose-then-apply:** the default run writes
  a reorganization plan to `.veles/memory/proposals/organize-<ts>.md` and changes nothing;
  `--apply` executes it. Ships as a built-in module (`modules/organize/`), not core. Reorg
  primitives are path-guarded: `move_file` and `wiki_rename_page` (move + back-reference
  repair). Batch onboarding: `veles add <dir> --recursive [--glob PATTERN]` ingests a whole
  directory.
- **TUI chat scrollback (M176).** Scroll the chat to re-read earlier output with
  `PageUp`/`PageDown` and `Ctrl+Home`/`Ctrl+End`. Streaming no longer yanks the view to the
  bottom while you're scrolled up (follow-mode resumes on `End` or a new turn). Opt into
  mouse-wheel scrolling with `VELES_TUI_MOUSE=1` (trades native drag-select for in-app
  selection + OSC52 copy).
- **Cache-hit indicator (M178).** The TUI status bar shows a green `cache <N>` chip with the
  last turn's cache-read tokens, so prompt caching is visible.

### Changed

- **Prompt caching now caches the conversation, not just the system prompt (M178).** A rolling
  `cache_control` breakpoint is placed on the most-recent user message, so each turn reads the
  prior conversation from cache instead of re-sending it at full price (the dominant cost in
  agentic loops). Local backends (ollama/llama.cpp/openai-compat) no longer leak the cache
  sentinel into their prompts and cache off the clean prefix automatically.
- **Context-window meter shows live occupancy (M177).** The `ctx` status chip (and `/context`)
  now render the current request's prompt size against the model's real context window
  (per-model registry: Haiku 200k, Sonnet/Opus 4.6+ and Fable 1M) — it no longer conflated
  cumulative run usage with a hardcoded 200k and could show >100%.

### Fixed

- **Context overflow without compression (M177).** The TUI agent now carries a model-derived
  `hard_ceiling_tokens`, so the emergency-truncation guard runs (parity with the daemon path);
  a long session can't send an over-window request.
- **Non-wiki layouts no longer get wiki machinery (M174).** `veles doctor` stops warning about
  missing `INDEX.md`/`LOG.md`, the subproject proposer no-ops, and TUI `/save` falls back to a
  memory insight — on `bare`/`notes` layouts where the wiki engine is off.

## [0.6.5] — 2026-06-22

### Changed

- **Unified channel-setup wizards (M172).** Connecting a chat channel (Telegram) now
  follows the same flow everywhere — `veles channel add`, the `veles daemon` control
  panel (key `c`), and the project setup wizard inside `veles daemon start`: first pick a
  channel *type* from the platform registry, then fill that channel's fields (token,
  whitelist). The project wizards previously hardcoded a Telegram-specific prompt;
  they're now registry-driven, so adding a channel platform needs zero wizard code.
- **`veles daemon start` connects a channel on existing projects too (M173).** In a fresh
  directory the setup wizard already offers a channel; on an already-initialised project
  with none configured, `daemon start` now asks once and runs the same channel wizard
  before the daemon comes up (interactive only; skipped with `--no-wizard`).

### Fixed

- **`veles daemon start` honours the configured port (M173).** The unnamed daemon ignored
  the `[daemon] host`/`port` written by the setup wizard and always bound `127.0.0.1:8765`.
  It now applies the cascade explicit `--host`/`--port` > config > the default.

### Internal

- Removed the dead `ApprovalScreen` / `TrustScreen` modal overlays
  (`tui/screens/approval_screen.py`) and their tests. The inline `ComposerPrompt`
  (above the Composer) has been the only approval/trust surface since M115; the
  modals were never instantiated. No user-facing change.
- Refreshed the README demo GIFs: the TUI launches with bare `veles`, and the daemon
  flow is shown by two new clips (`veles daemon start` wizard + the `veles daemon`
  control panel), replacing the old `/daemon`-in-TUI clip.

## [0.6.4] — 2026-06-20

### Fixed

- **TUI approval prompt: controls no longer scroll off-screen.** When a sensitive
  tool's approval/trust prompt carried a long body (e.g. a big `run_shell` command or
  file-content arguments), the body grew unbounded and pushed the option list and the
  key hint below the visible area, making it impossible to approve or deny. The body is
  now confined to a bounded, scrollable region so the controls stay visible at all times;
  the full text remains reachable by scrolling.

## [0.6.3] — 2026-06-20

### Changed

- **The agent can now edit `AGENTS.md`.** Veles generates the project's `AGENTS.md`
  context file for every layout, but its own `write_file` / `edit_file` tools refused
  to touch it under content layouts (e.g. the default LLM-wiki, whose writable zones
  are `wiki/` + `sources/`). `AGENTS.md` now sits in the always-writable set alongside
  `.veles/`, so the agent maintains it like any other file it generates. Matched by
  exact name, so lookalikes (`AGENTS.md.bak`) and arbitrary root files (`README.md`)
  stay protected; shell writes (`run_shell`) are unchanged.

## [0.6.2] — 2026-06-19

### Changed

- **Verify → escalate now also covers manager-orchestrated runs.** Previously the
  advisor judge-and-escalate pass ran only on direct agent turns; when a run was
  decomposed across manager/worker agents (`--manager`), the synthesised answer
  skipped verification. Now the two compose: with verify enabled, the manager's
  final answer is judged and, on a confident failure, escalated to the stronger
  model — exactly like a direct run. No new flags (opt-in stays `--verify` /
  `[verify] enabled` / `VELES_VERIFY_MODE=1`).

### Internal

- Audit-remediation pass over the 0.4.0–0.6.1 work: removed dead config left by
  the wiki-to-module move, deduplicated two small helpers into shared homes, and
  added the optional vector-search backends (numpy / sqlite-vec) to the dev/test
  matrix so their tests run instead of skipping. No user-facing behaviour change.

## [0.6.1] — 2026-06-19

### Changed

- **Internal:** the LLM-wiki is now a pluggable content-engine module
  (`veles.modules.wiki`) instead of living in the core. The core no longer
  imports or privileges the wiki — it loads only when a project's layout
  enables the wiki engine. No user-facing behaviour change: wiki tools and the
  `llm-wiki` layout work exactly as before. This keeps the core minimal and
  makes room for other content patterns (e.g. an Obsidian connector) as peer
  modules.

## [0.6.0] — 2026-06-18

### Added

- **Human-readable recurring schedules** — cron is no longer the way you set up
  a recurring job. Use `daily@09:00`, `weekdays@18:00`, `weekend@10:00`,
  `weekly:mon,fri@09:00`, `every:2h`, or `once:2026-07-01 18:00`. In chat the
  bot understands plain language ("каждый будний день в 18:00") and translates
  it for you. Times are in the project's timezone — the host's by default, or
  set `[schedule] timezone = "Europe/Moscow"` in config.toml to override; they
  stay correct across daylight-saving changes. (Raw cron still works but is no
  longer documented.)
- **The bot can schedule recurring work from chat** — `job_add` (plus
  `job_list` / `job_remove`) lets it set up a daily digest or a periodic
  monitoring check itself. Because a recurring job runs autonomously with full
  tools, creating one asks for your confirmation first.
- **`memory_query`** — the agent can read back its own recorded insights,
  rules, telemetry, tasks, and session log with a read-only SQL `SELECT`
  (previously it could only write to memory, never read it).

## [0.5.0] — 2026-06-18

### Added

- **Personal tasks with proactive reminders.** The agent can keep a personal
  todo list with optional reminders: `task_add` (with a due time like `+2h`,
  `+1d`, or an ISO timestamp), plus `task_list`, `task_done`, and `task_snooze`.
  When a reminder is due, a running daemon pushes it to the chat the task came
  from — so "remind me to review the PR at 18:00" in Telegram pings *that* chat
  at 18:00. Tasks are distinct from scheduled jobs (which run prompts): a task
  is "remind me about X at time T". Reminders fire only while a daemon is
  running.

### Fixed

- Co-hosted channel turns (the daemon's own Telegram bot) now run the
  `--verify` → escalate pass too. Previously verification only applied to
  external HTTP clients, so the bot most users run didn't get the
  hallucination fallback.

## [0.4.0] — 2026-06-18

### Added

- Scheduled jobs can now **deliver their output to a channel**. A job created
  with `--deliver-to telegram:<chat-id>` (or `deliver_to` via the API) posts its
  result to that chat when it runs — previously the target was recorded but
  never used, so a job only wrote a file under `.veles/jobs/`. Delivery is
  best-effort: a failing channel is logged on the run but never wedges the
  schedule. This is the foundation for proactive reminders and monitoring
  alerts.
- New **`edit_file`** tool for surgical edits: the agent replaces an exact
  string in an existing file instead of rewriting the whole file. The match
  must be unique unless `replace_all` is set, so it can't silently edit the
  wrong occurrence. Useful for correcting scripts, data models, or queries.
- **Verify → escalate** (`veles run --verify`, the `[verify] enabled` daemon
  config, or `VELES_VERIFY_MODE=1`): after a run, the routed advisor model judges
  the answer against the evidence the agent gathered; on a confident failure it
  re-runs the prompt on that stronger model (which may be a `claude`/`gemini` CLI)
  and returns the corrected answer — a fallback for hallucinations on cheap/local
  models. Works for `veles run` and for daemon/channel turns (e.g. Telegram), where
  escalation preserves the chat's session so history isn't lost. Off by default.

## [0.3.2] — 2026-06-15

### Fixed

- `veles daemon` picker: the interactive `tui` session row is now shown only
  while its REPL is actually alive. A clean exit, and especially a crash /
  SIGKILL (which leaves the reused row stuck at `running` with a now-dead pid),
  used to leave a phantom `tui` entry that displayed a nonexistent pid and could
  not be removed (the row is reused and never deleted). Stopped/orphaned tui rows
  are filtered out of the tree; a live REPL still appears beside the daemons.

## [0.3.1] — 2026-06-15

### Fixed

- TUI: the active project (and module registry) is now re-installed inside
  the per-turn worker thread. `veles tui` runs each turn on a Textual
  `run_worker(thread=True)` executor, which — unlike the daemon's
  `asyncio.to_thread` — does not propagate `ContextVar`s, so the agent loop
  saw `current_project() == None`. Tools that hard-require a project
  (`wiki_search`, `wiki_list_pages`, `wiki_read_page`, `memory_save`) then
  failed every call with "no active Veles project"; path-sandboxed tools
  silently fell back to the cwd. Both vars are now captured on the main
  thread and set on the worker thread for the duration of the turn.

## [0.3.0] — 2026-06-15

### Changed

- **Breaking (niche):** routing no longer has *any* hardcoded cloud default —
  the `embedding` task (used by `veles skill dedup`) now resolves only from an
  explicit `[routing.tasks].embedding`, matching the other tasks. `--mode auto`
  still degrades to TF-IDF when unset; `--mode embedding` errors clearly instead
  of silently using `openai:text-embedding-3-small`.

### Fixed

- Daemon event streams now deliver a run's terminal `completed`/`error` event
  before closing: it was appended asynchronously while the run was marked done
  synchronously, so a subscriber streaming a fast run could miss the completion
  event.
- The release workflow now creates the GitHub Release on a version tag
  (previously it only published to PyPI; the Release page was manual).

## [0.2.0] — 2026-06-14

### Added

- Automatic tool-call detection for local providers: `ollama` / `llamacpp` /
  `openai-compat` enable tool calling when the chosen model advertises it
  (Ollama `/api/show` `capabilities`), with no `VELES_LOCAL_TOOLS` flag.
- `graphify_rebuild` project tool, auto-provisioned into `<project>/.veles/tools/`
  when a `graphify` MCP server is configured — resolves the project's provider
  and rebuilds the knowledge graph on the configured backend.
- File-based project/user tools (`<project>/.veles/tools/`, `~/.veles/tools/`)
  are now loaded into the agent's registry at runtime.

### Changed

- **Breaking:** there is no hardcoded default model. The effective model
  resolves from `--model`, the project `[provider] model`, or the user
  `default_model`; when none is configured, veles raises a clear "no model
  configured" error instead of silently using a cloud model. `veles run`,
  `veles job`, and the daemon now resolve provider+model through the same config
  cascade as the TUI.
- **Breaking:** routing has no cloud fallback for chat tasks. Sub-agent tasks
  (compressor, advisor, insights, vision, curator, dream) resolve from
  `[routing.tasks]`, the `[provider]` base, or user defaults; when unconfigured
  the feature degrades (turns off) instead of silently routing to
  `openrouter:claude-*`. `veles route show` displays `(unconfigured)`. The
  `embedding` task keeps its default (a distinct model type).
- `VELES_LOCAL_TOOLS` is now an explicit on/off override rather than the only
  way to enable local tool calling.

### Fixed

- MCP server configuration: documented that `command` and its arguments are
  separate fields (`command = "npx"`, `args = [...]`), not a single string —
  the previous docs example could not launch a stdio server.

## [0.1.0] — 2026-06-12

Initial public release.

### Added

- Agent loop with structured per-project memory: insights, behavioral rules,
  session digests, and a Curator that distills each session into memory.
- Pluggable content layouts: Karpathy-style LLM wiki (default), flat notes,
  bare; custom layout packs via a single TOML file in `~/.veles/layouts/`.
- Provider adapters: OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llama.cpp,
  any OpenAI-compatible endpoint, plus `claude` / `gemini` CLI subprocess
  delegation.
- Per-task model routing (`veles route`): planning, compression, and insight
  extraction can each use a different model.
- Skills and tools that accumulate: project-level and user-level registries,
  promotion between them, inheritance (`extends:`), near-duplicate detection.
- Multi-project and subproject management in a single agent loop.
- Interactive TUI REPL (`veles tui`) with slash-command inspectors.
- HTTP/WS daemon and a Telegram channel gateway.
- MCP client: external MCP servers as tool sources (`veles mcp`).
- Trust ladder and path sandbox; autopilot with bounded standing approval.
- Hierarchical multi-agent orchestration (manager/worker), explicit opt-in.
- Export/import of full projects and templates.
- i18n: English (default) and Russian locales, user-extensible.

[Unreleased]: https://github.com/denisotree/veles/compare/v0.44.0...HEAD
[0.44.0]: https://github.com/denisotree/veles/compare/v0.43.0...v0.44.0
[0.43.0]: https://github.com/denisotree/veles/compare/v0.42.0...v0.43.0
[0.42.0]: https://github.com/denisotree/veles/compare/v0.41.0...v0.42.0
[0.41.0]: https://github.com/denisotree/veles/compare/v0.40.0...v0.41.0
[0.40.0]: https://github.com/denisotree/veles/compare/v0.39.0...v0.40.0
[0.39.0]: https://github.com/denisotree/veles/compare/v0.38.0...v0.39.0
[0.38.0]: https://github.com/denisotree/veles/compare/v0.37.0...v0.38.0
[0.37.0]: https://github.com/denisotree/veles/compare/v0.36.0...v0.37.0
[0.36.0]: https://github.com/denisotree/veles/compare/v0.35.0...v0.36.0
[0.35.0]: https://github.com/denisotree/veles/compare/v0.34.0...v0.35.0
[0.34.0]: https://github.com/denisotree/veles/compare/v0.33.0...v0.34.0
[0.33.0]: https://github.com/denisotree/veles/compare/v0.32.0...v0.33.0
[0.32.0]: https://github.com/denisotree/veles/compare/v0.31.0...v0.32.0
[0.31.0]: https://github.com/denisotree/veles/compare/v0.30.0...v0.31.0
[0.30.0]: https://github.com/denisotree/veles/compare/v0.29.0...v0.30.0
[0.29.0]: https://github.com/denisotree/veles/compare/v0.28.1...v0.29.0
[0.28.1]: https://github.com/denisotree/veles/compare/v0.28.0...v0.28.1
[0.28.0]: https://github.com/denisotree/veles/compare/v0.27.0...v0.28.0
[0.27.0]: https://github.com/denisotree/veles/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/denisotree/veles/compare/v0.25.0...v0.26.0
[0.25.0]: https://github.com/denisotree/veles/compare/v0.24.0...v0.25.0
[0.24.0]: https://github.com/denisotree/veles/compare/v0.23.1...v0.24.0
[0.23.1]: https://github.com/denisotree/veles/compare/v0.23.0...v0.23.1
[0.23.0]: https://github.com/denisotree/veles/compare/v0.22.2...v0.23.0
[0.22.2]: https://github.com/denisotree/veles/compare/v0.22.1...v0.22.2
[0.22.1]: https://github.com/denisotree/veles/compare/v0.22.0...v0.22.1
[0.22.0]: https://github.com/denisotree/veles/compare/v0.21.2...v0.22.0
[0.21.2]: https://github.com/denisotree/veles/compare/v0.21.1...v0.21.2
[0.21.1]: https://github.com/denisotree/veles/compare/v0.21.0...v0.21.1
[0.21.0]: https://github.com/denisotree/veles/compare/v0.9.0...v0.21.0
[0.9.0]: https://github.com/denisotree/veles/compare/v0.8.3...v0.9.0
[0.8.3]: https://github.com/denisotree/veles/compare/v0.8.2...v0.8.3
[0.8.2]: https://github.com/denisotree/veles/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/denisotree/veles/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/denisotree/veles/compare/v0.7.2...v0.8.0
[0.7.2]: https://github.com/denisotree/veles/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/denisotree/veles/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/denisotree/veles/compare/v0.6.7...v0.7.0
[0.6.5]: https://github.com/denisotree/veles/compare/v0.6.4...v0.6.5
[0.6.4]: https://github.com/denisotree/veles/compare/v0.6.3...v0.6.4
[0.6.3]: https://github.com/denisotree/veles/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/denisotree/veles/compare/v0.3.2...v0.6.2
[0.3.2]: https://github.com/denisotree/veles/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/denisotree/veles/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/denisotree/veles/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/denisotree/veles/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/denisotree/veles/releases/tag/v0.1.0
