# {name}

Add your project context here. Auto-loaded into the system prompt
when you run `veles run` or `veles tui` from this directory (or any
subdirectory).

## Layout

- `notes/` — free-form markdown notes; the only directory the agent
  writes content into.

## Conventions

- One topic per note, kebab-case filenames (`meeting-2026-06-10.md`).
- Keep notes short; link related notes by relative path.

## Workflows

- `veles run "summarise notes/<file>.md"` — work with a specific note.
- `veles run "write a note about <topic>"` — the agent creates a new
  note under `notes/`.
- `veles curate` — distill recent sessions into project memory.
