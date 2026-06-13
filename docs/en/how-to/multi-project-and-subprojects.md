# How to work with multiple projects and subprojects

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/multi-project-and-subprojects.md)

Veles runs many projects in one agent loop. Each project has its own memory,
skills, and tools. **Subprojects** are nested projects under a parent — useful for
decomposing a large monorepo or knowledge base into scoped memories.

## Projects

Veles discovers the active project by walking up from your cwd to a `.veles/`
directory (like `git`). Manage the registry:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` prints a path, so you can `cd` into a project:

```bash
cd "$(veles project switch web)"
```

Run a command against a project elsewhere without `cd`:

```bash
veles run --project-root /path/to/project "..."
```

## Subprojects

A subproject is a child Veles project inside a parent. Create one:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Let Veles suggest a split

When a project's wiki grows, Veles can detect thematic clusters and propose them
as subprojects:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## When to use which

- **Separate projects** — unrelated knowledge bases / codebases.
- **Subprojects** — parts of one larger thing that benefit from scoped memory but
  share a parent context.

See [architecture](../explanation/architecture.md) for how multi-project context
loads on demand rather than as one monolithic dump.
