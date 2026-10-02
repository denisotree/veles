# How to extend Veles with a module

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/extend-veles-with-modules.md)

A module adds to Veles through **contribution points**: its `register(api)` entrypoint
calls `api.contribute(point, name, obj)`, and Veles' core reads what was contributed
instead of importing the module's code. The built-in wiki engine works exactly this
way — it is a module like any other.

```python
# my_engine.py — the entrypoint named in module.toml
from veles.core.contributions import Engine


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
| `self_doc` | `fn(project, content) -> path or None` | takes the self-documentation page (else `.veles/memory/self-doc.md`) |
| `scaffold` | `fn(root, manifest)` | runs when a layout pack is applied to a project |
| `background_op` | `BackgroundOp(kind, toolset, run)` | a daemon job kind; `run(job, *, spawn_agent, project)` |
| `memory` | factory (via `api.add_memory_provider`) | an external memory provider |

Objects that take an `engine` gate themselves on it; the others check
`veles.core.layout.engines.engine_enabled(project, "<name>")` themselves when they
should only apply with their engine on.

## Declare what a registry module provides

In a registry, `provides` in `extension.toml` lists every contribution as
`<point>:<name>` (and hooks as `hook:<name>`). `veles registry validate --run-code`
loads the module and checks the list against what `register()` actually added.

```toml
[extension]
name = "my-engine"
kind = "module"
provides = ["engine:my-engine", "prompt:my-engine"]
```
