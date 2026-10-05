# How to extend Veles with a module

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/extend-veles-with-modules.md)

A module adds to Veles through **contribution points**: its `register(api)` entrypoint
calls `api.contribute(point, name, obj)`, and Veles' core reads what was contributed
instead of importing the module's code. The wiki engine (in the public registry) works
exactly this way — it is a module like any other.

```python
# __init__.py — the entrypoint named in module.toml
from veles.sdk.contributions import Engine

from .blocks import my_prompt_blocks  # a module may span several files


def register(api) -> None:
    api.contribute("engine", "my-engine", Engine("my-engine"))
    api.contribute("prompt", "my-engine", my_prompt_blocks)
```

`name` is unique within a point, Veles' own built-in modules included. A module that
contributes to an unknown point, passes an object the point doesn't take, or repeats a
name another module (built-in or not) already used is refused at load time and the rest
of Veles keeps working. Recall reserves `insights`, `turns`, `about` and `extra`; a
`BackgroundOp` or `DreamStep` is contributed under its own `kind`/`name`. A contribution
that raises when called is skipped with a warning.

## Import Veles through `veles.sdk`

`veles.sdk` is the public surface a module builds on; Veles' internals can then change
without breaking modules. A registry module **must** import Veles only from it —
`veles registry validate` refuses anything else (tests are exempt).

| Module | What it has |
|---|---|
| `veles.sdk` | `Project`, `load_project`, `current_project`, `current_origin`, text/slug/time helpers |
| `veles.sdk.contributions` | the point types below, `CommandHost`, `contributions`, `active`, `engine_enabled` |
| `veles.sdk.tools` | the `@tool` decorator, `RiskClass`, `TOOLSETS`, path and write guards, `fetch_url`, `read_file` |
| `veles.sdk.memory` | `RecallHit`, memory-provider protocols, `append_memory_log`, `write_proposal`, `escape_query` |
| `veles.sdk.layout` | `find_layout`, `LayoutManifest`, `load_context_file`, subprojects |
| `veles.sdk.jobs` | `submit_oneshot_job`, `spawn` (worker agents), the delegation-depth guard |
| `veles.sdk.channels` | the channel contract: `PlatformSpec`, `ChannelContext`, `ChannelCaps`, `ChannelGateway`, `CredField`, `RunBackend`, `RunBackendError`, `SessionMap` |
| `veles.sdk.channel_checks` | checks a channel module's tests run on its spec: `check_builds_from_config`, `check_config_keys`, `check_delivers` |
| `veles.sdk.media` | the speech-to-text and vision adapters a channel uses for voice and images |

The entrypoint loads as a package rooted at the module directory, so the module's own
files import relatively (`from .wiki import Wiki`).

## What a module can carry

One module can bundle everything a feature needs, so it installs — and is reused — as
one piece:

- **tools** — a `ToolSet` contribution (see below);
- **skills** — `skills/<name>/SKILL.md` in the module directory. They mount for every
  project that loads the module, below the project's and the user's own skills (a skill
  of yours with the same name wins) and above the layout's. They are read-only: they
  belong to the module's approved tree, so editing one keeps the whole module unloaded
  until it is approved again;
- **content engines, CLI verbs, `/` commands, recall, prompt and dream steps, hooks,
  memory providers, channel platforms** — the contribution points below;
- **strings** — `locales/<lang>.toml` in the module directory, flat keys without a
  table header. Veles merges them under the module's name, so `hello = "Hi"` in the
  `telegram` module is `t("telegram.hello")`. A key Veles itself defines wins over
  the module's.

```text
my-suite/
  module.toml
  __init__.py          # register(api): tool sets, commands, hooks…
  tools.py
  skills/
    triage/SKILL.md     # mounted as the skill `triage`
```

### Combined modules

A module can build on others: list the modules, layouts and skills it needs in
`requires_extensions` of its `extension.toml`. Installing it installs the whole chain
under one confirmation, dependencies first, in the module's own scope (the project, or
the user with `--user`); if any part fails, nothing from that install is left behind.

```toml
# suite — reuses the `base` module, which itself brings the skill `helper`
[extension]
name = "suite"
kind = "module"
requires_extensions = ["public:official/base"]

# base
[extension]
name = "base"
kind = "module"
requires_extensions = ["public:official/helper"]
```

`veles registry install suite` then installs `helper`, `base` and `suite`.

## Contribution points

| Point | Object | What core does with it |
|---|---|---|
| `engine` | `Engine(name)` | a layout pack with `[layout.engines] <name> = true` turns it on for a project |
| `tool` | `ToolSet(load, tools, engine=None)` | `load()` registers the `@tool` functions; with `engine` set, only where that engine is on |
| `recall` | `fn(project, query, *, limit) -> list[RecallHit]` | adds hits to memory recall |
| `prompt` | `fn(project, *, include_index) -> list[str]` | adds blocks to the stable (cached) system prompt |
| `dream_step` | `DreamStep(name, run, skip_flag)` | `run(project, result, *, dry_run)` inside the dream cycle |
| `curator_target` | `CuratorTarget(engine, prepare, instructions, persist_tools)` | where the curator's agent persists a session |
| `subproject_source` | `PageSource(pages, engine=None)` | pages for subproject clustering and the self-doc page count |
| `page_store` | `PageStore(write, read, engine=None)` | keeps pages: `/save` (category `queries`) and the self-documentation page (`self-doc/overview`); without one they go to memory |
| `cli_command` | `CliCommand(help, add_arguments, run, run_flags=False)` | a `veles <name>` verb; `run(args, project, host)`, where `host.run_agent(...)` runs one agent turn the way `veles run` does |
| `slash_command` | `SlashCommand(run, summary, usage, engine=None)` | a `/<name>` REPL command; `run(project, arg) -> SlashReply(text, submit_prompt, error)` |
| `scaffold` | `fn(root, manifest)` | runs when a layout pack is applied to a project |
| `background_op` | `BackgroundOp(kind, toolset, run)` | a daemon job kind; `run(job, *, spawn_agent, project)` |
| `memory` | factory (via `api.add_memory_provider`) | an external memory provider |
| `platform` | `PlatformSpec(build, caps, cred_fields, config_keys)` | a messaging platform the daemon hosts as a channel (see below) |

Objects that take an `engine` gate themselves on it; the others check
`veles.sdk.contributions.engine_enabled(project, "<name>")` themselves when they
should only apply with their engine on. Builtin verbs and slash commands keep their
names — a module can't take `veles run` or `/help`.

## A channel platform

A channel module contributes a `PlatformSpec` under the platform's name; the daemon
builds one gateway per `[channels.<name>]` block through `build(ctx)`:

```python
from veles.sdk.channels import ChannelCaps, ChannelContext, CredField, PlatformSpec


def _build(ctx: ChannelContext):
    # ctx.config: the channel block; ctx.secrets: the resolved secret fields;
    # ctx.backend: submit runs, stream events, answer prompts;
    # ctx.session_map: chat id → session; ctx.project
    return MyGateway(token=ctx.secrets["token"], backend=ctx.backend, sessions=ctx.session_map)


SPEC = PlatformSpec(
    build=_build,
    caps=ChannelCaps(asks_questions=True),  # the agent may ask the chat and wait
    cred_fields=(CredField("token", "Bot token", secret=True, required=True, env="MY_TOKEN"),),
    config_keys=frozenset({"room"}),  # other keys its block may hold
)


def register(api) -> None:
    api.contribute("platform", "mychat", SPEC)
```

The gateway has `start()`, `stop()` and `deliver(chat_id, text, thread_id=None)` — the
last one is how scheduled jobs reach a chat (`deliver_to = "mychat:<chat_id>"`).
Secret fields live in the OS keychain: the first one under the slot `<platform>`, any
other under `<platform>.<key>`; `veles channel add` asks for them. A key in the block
that is neither a cred field nor in `config_keys` is reported as a typo. A gateway's
loggers write to the daemon log. The module's own tests check the spec with
`veles.sdk.channel_checks`, and list it in `extension.toml` as `provides =
["platform:mychat"]`.

## Declare what a registry module provides

In a registry, `provides` in `extension.toml` lists every contribution as
`<point>:<name>` (and hooks as `hook:<name>`). `veles registry validate --run-code`
loads the module and checks the list against what `register()` actually added. A verb
listed as `cli_command:<name>` is also how Veles names the install when someone types
that verb without the module.

```toml
[extension]
name = "my-engine"
kind = "module"
provides = ["engine:my-engine", "prompt:my-engine"]
requires_extensions = []   # full refs of the modules/layouts/skills this one needs, e.g. "public:official/wiki"
```
