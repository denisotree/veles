# How to route tasks to different models

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

Veles isn't pinned to one model. Each internal **task** can use a different
`provider:model` — a cheap model for context compression, a strong one for the
main agent, a vision model for images. This is the *ensemble routing* system.

## Task types

| Task | Used for |
|---|---|
| `default` | The main agent loop |
| `curator` | Session → wiki consolidation |
| `compressor` | Sliding-window context compression |
| `insights` | Post-run insight extraction |
| `skills` | Skill execution |
| `advisor` | The `advisor_review` self-check |
| `vision` | `image_describe` (when a vision adapter is wired) |
| `embedding` | `veles skill dedup` similarity |

## See the current routing

```bash
veles route show
```

This prints the resolved `provider:model` for every task and a `source` label
saying which layer decided it.

## Pin a task to a model

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

These write `[routing.tasks]` in `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Reset

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Natural-language hints in AGENTS.md

You can express routing in prose in `AGENTS.md` (e.g. "use a cheap model for
compression"). Veles parses these into an auto-generated `routing.nl.toml`:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Explicit `[routing.tasks]` entries always win over NL hints.

## Resolution order

For each task, the first layer that yields a spec wins:

1. project `[routing.tasks][task]`
2. project `[routing.tasks].default`
3. project NL hint (`routing.nl.toml`)
4. project `[provider]` base
5. user `[routing.tasks][task]` / `.default`
6. user `[user] default_provider` + `default_model`

If none of these resolves, there is **no hardcoded fallback** — the task is left
unset and its caller degrades (skips the feature) or errors clearly, rather than
silently reaching for a cloud model.

(`embedding` skips the catch-alls — a chat model is not an embedding model — so
only an explicit `[routing.tasks].embedding` answers it.)
