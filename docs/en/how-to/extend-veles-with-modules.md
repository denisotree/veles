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

The entrypoint loads as a package rooted at the module directory, so the module's own
files import relatively (`from .wiki import Wiki`).

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

Objects that take an `engine` gate themselves on it; the others check
`veles.sdk.contributions.engine_enabled(project, "<name>")` themselves when they
should only apply with their engine on. Builtin verbs and slash commands keep their
names — a module can't take `veles run` or `/help`.

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
requires_extensions = []   # full refs of extensions this one needs, e.g. "public:official/wiki"
```
