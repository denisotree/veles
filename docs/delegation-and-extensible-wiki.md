# Delegation + an extensible wiki: migrating content into Veles

This guide shows the base working pattern Veles uses for non-trivial tasks —
**decompose → delegate to a small scoped worker → integrate** — and how the wiki
layout extends itself per-project, using a content migration (e.g. an Obsidian
vault) as the worked example.

Two invariants make this work:

- **Schema is data, not code.** The framework hardcodes no project-specific
  structure. The generic wiki categories (`concepts`, `entities`, `sources`,
  `queries`, `sessions`, `self-doc`) ship with the `llm-wiki` pack; anything
  specific to *your* content (a diary, tasks, projects, meetings, …) is declared
  in your project's `.veles/wiki.toml` and created by the agent at runtime.
- **Small, fully-scoped subtasks are doable by light models.** A capable
  coordinator decomposes the work and delegates each small piece to a fresh
  worker with a *narrow* toolset and *isolated* context; the coordinator then
  accepts the result or delegates a correction.

## The building blocks

- **`delegate(subtask, tools=[...], context="...")`** — hand one small, fully
  described subtask to a fresh sub-agent. It shares no history with you, so put
  everything it needs in `subtask` + `context`. `tools` is the exact set it may
  use (drawn from the tools available in this project); omit it for a read-only
  worker — grant `write_file` / `edit_file` / `move_file` / `wiki_*` only when the
  subtask needs to change things. Any files the worker writes persist; you read
  its report and move on or correct it. Depth is capped against runaway.
- **`wiki_add_category(name)`** — declare a new wiki category for this project
  (persisted to `.veles/wiki.toml`) and create its directory. Nested paths like
  `projects/work` are allowed. After this, `wiki_write_page(category="<name>", …)`
  works.
- **`structure_design` skill** — given a natural-language description of a kind of
  data, it designs the categories + naming convention, declares them with
  `wiki_add_category`, scaffolds the dirs, and writes a convention page. It
  derives the schema entirely from your description — nothing is baked in.
- **`move_file` / `delete_file` / `make_dir`** — first-class file operations in
  the interactive toolset, writable-zone-guarded (they refuse read-only zones
  like `sources/` and can't escape the project). `delete_file` asks for an in-app
  yes/no confirmation.

## Walkthrough: migrate a vault into the wiki

Run `veles repl` inside a project (`veles init` first; `veles layout sync` if you
added categories to an existing project and want the dirs materialised). Then, in
plain language:

1. **Design the structure for your iterative data.** e.g. *"I keep a daily
   journal, a list of projects with sub-areas, and a task list — design the wiki
   structure for these."* The agent runs `structure_design`, which declares
   categories like `diary` (one page per date), `projects` / `projects/<area>`,
   and `tasks` (a checklist page), writes a convention page, and reports the
   scheme. Nothing here is hardcoded — it comes from your description.

2. **Migrate content, one file per worker.** e.g. *"Migrate every note under
   `-- Daily --/` into `wiki/diary/`, one file at a time."* The coordinator lists
   the files and, per file, calls:

   ```
   delegate(
     "Turn this daily note into a wiki page and link it.",
     tools=["read_file", "wiki_write_page", "wiki_search", "move_file",
            "memory_save_insight"],
     context="source: -- Daily --/2026-07-02.md\n"
             "target: wiki/diary/<YYYY-MM-DD>.md per the convention page\n"
             "link related pages with [[slug]]; record one insight",
   )
   ```

   Each worker reads that one file, writes the page, adds `[[wikilinks]]`,
   optionally records an insight tied to the page, and reports back. The
   coordinator accepts or re-delegates. Sources aren't deleted unless you ask.

3. **Verify.** Regular articles land in the generic categories; your
   diary/tasks/projects land in the categories you declared. `dream` lint/reindex
   keeps links and the index consistent.

## Why this scales to weak models

The heavy reasoning is in the *decomposition* (the coordinator) and the *scope*
of each subtask. A worker only ever sees one file, the target convention, and a
handful of tools — a small, closed problem a light model can handle reliably.
This is the default way to tackle any non-trivial task in Veles, not just
migration.
