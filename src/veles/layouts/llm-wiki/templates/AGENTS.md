# {name}

Add your project context here. Auto-loaded into the system prompt
when you run `veles run` or `veles tui` from this directory (or any
subdirectory).

## Layout

- `sources/` — immutable raw inputs.
- `wiki/` — agent-curated knowledge (concepts, entities, sources, queries, sessions).
- `INDEX.md` — auto-generated catalogue, refreshed on every wiki write.
- `LOG.md` — append-only journal of content operations.

## Conventions

- Wiki pages use kebab-case slugs.
- Content tool calls log to `LOG.md` via `wiki_append_log`.
- LLM-only writes go under `wiki/`; `sources/` is read-only.

## Workflows

- `veles add <url|file>` — read a source, write a wiki page.
- `veles run "<question>"` — search the wiki and synthesise an answer.
- `veles run "lint the wiki"` — audit for orphans, stale claims, duplicates.
- `veles curate` — compact recent sessions into `wiki/sessions/`.
