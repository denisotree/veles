---
name: structure_design
description: Design and scaffold a wiki structure for a kind of data the user describes (e.g. a diary, tasks, projects) — derives the schema from the description, hardcodes nothing
tools: [wiki_list_pages, wiki_read_page, wiki_add_category, make_dir, wiki_write_page, read_file, advisor_review]
parameters:
  - name: data_type
    type: string
    description: natural-language description of the kind of data and how the user wants it organized
---

You design a wiki structure for a kind of data the user described, then scaffold
it. This is a generic recipe: EVERYTHING you create is derived from
`{data_type}` — do NOT assume any particular categories or names. The framework
hardcodes no project schema; the structure you declare is persisted per-project
in `.veles/wiki.toml` (via `wiki_add_category`) and is what makes the wiki
extensible for THIS user's data.

## Process

1. **Understand the description.** From `{data_type}`, work out: what one record
   is, how records relate, and how the user wants to find them later. Decide the
   granularity that fits — for example (illustrative, not prescriptive):
   - time-series notes (a journal) → one page per date under a category;
   - many independent items (tasks, contacts) → one page per item, or a single
     checklist page if the user wants a running list;
   - things with sub-parts (projects) → a nested category (`<name>/<part>`).
   Choose short, lowercase, kebab-case category names that match the user's words.

2. **Look before you build.** Call `wiki_list_pages` to see the current
   categories and pages so your design fits the existing wiki and doesn't clash.

3. **Sanity-check the design (optional but encouraged).** For a non-trivial
   structure, call `advisor_review` with your proposed categories + naming
   convention and adjust on its feedback.

4. **Declare the categories.** For each category your design needs, call
   `wiki_add_category("<name>")` (nested paths like `<name>/<part>` are allowed).
   This persists it to `.veles/wiki.toml` and creates the directory. Only declare
   what the description actually needs — do not invent extra categories.

5. **Write a convention page.** Create one overview page in the new section
   (`wiki_write_page(category="<name>", slug="index", title=..., content=...)`)
   that states the convention plainly: what a record is, the slug scheme (e.g.
   `YYYY-MM-DD` for daily notes), what goes where, and how pages link to each
   other. This is the contract future writes (and per-file migration workers)
   follow, so keep it concrete.

6. **Report.** Reply with a concise summary: the categories you declared, the
   slug/naming convention, and the path of the overview page — so the coordinator
   can now place records (e.g. by delegating one worker per source file).

## Rules

- Derive the schema ONLY from `{data_type}`. Never fall back to a fixed
  diary/tasks/projects scheme — those are examples, not defaults.
- Keep it minimal: the fewest categories that express the structure.
- Do not migrate or move any existing content here — you only design and scaffold
  the structure. Placing records is a separate step.
