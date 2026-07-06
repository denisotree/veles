## LLM Wiki: content-aware ingestion & migration

This layout declares no restricted zones: you may read, move, and write ANY
file under the project root. On a request to **organize, migrate, or ingest**
content (e.g. "read this file into the wiki", "migrate this folder into the
wiki", or a single `veles add <source>`), route the content by what it is
ABOUT — do not mirror files to pages one-for-one. For a whole-directory
request, process every file, not just what's already under `wiki/`.

### The core rule: pages are topics, not files

A wiki page is a **topic** — a standing subject the content is about (a
concept, an event, a person, an organization, a work). **Page identity is the
topic, never the filename or a date.** A file called `2025-02-27.md` about a
Harry Potter concert becomes a page like `concepts/harry-potter-in-concert`
and `entities/anya-cellist` — NOT a page called `2025-02-27`.

Classify every source by CONTENT (never by filename or extension). A single
file can be about **several distinct topics** at once (one diary day → an
event + two people). Extract each topic and handle it on its own.

### Pipeline for each source

1. **Read** it (`read_file`, or `fetch_url` for a URL, `pdf_read` for a PDF).
2. **Extract the topics** it covers — zero, one, or many.
3. **For each topic, find-or-create-or-patch:**
   - `wiki_search` and `wiki_list_pages` to find an existing page on that topic
     **by meaning**, not by slug.
   - **No page yet → CREATE.** Pick a category (`concepts` for ideas/events,
     `entities` for people/orgs/works, or a project category — add one with
     `wiki_add_category`/the `structure_design` skill if none fits). Choose a
     short, **topical** kebab-case slug. `wiki_write_page(category, slug,
     title, content)`.
   - **Page exists → PATCH.** `wiki_read_page`, then **semantically weave** the
     new knowledge into the body — integrate it as fact (e.g. "Already sent
     books B1, B2, B3 for restoration"), don't dump the raw text. `wiki_write_page`
     with the merged body (overwrite).
4. **Dispose of the raw source.** For a **file** source, relocate the original
   into the top-level `sources/` tree with `move_file` — the immutable
   first-source copy, kept by convention. For a **URL** there is no local raw
   to move; the fetched content is the source (optionally `wiki_ingest` it).
5. `wiki_append_log` one line per page you created or patched.

A plain article or fact is just the one-topic case of this pipeline. A
log-type record (a dated/periodic remark — a task update, diary entry, meeting
note, status comment) is the same pipeline, and its topics almost always
**patch** existing pages rather than create new ones — weave the record's
substance into the page it belongs to; create a page only if none exists.

### Break big migrations into delegated per-topic work

For a large source or a whole-directory migration, prefer to `delegate` one
focused worker per topic (or per file) rather than doing everything in one long
context — give each worker only the tools it needs (`read_file`, `wiki_search`,
`wiki_read_page`, `wiki_write_page`, `move_file`) and the target topic +
convention as `context`. You stay the coordinator: decide the decomposition,
read each report, integrate. Process a directory **one file at a time** so each
file's `wiki_search` sees the pages the previous files already wrote (that is
what lets you patch instead of duplicate).

### Valueless sources

If a source has no topical content — it's empty, pure boilerplate, noise, or an
exact duplicate of what's already in the wiki — write **no** page. Move the raw
file into `sources/_archive/` with `move_file` and `wiki_append_log` "no
topical content". Archive, don't delete: deletion is not a default ingest
action.

### Conventions carried over

- The top-level `sources/` directory holds raw first-sources, by convention —
  don't edit a file already under `sources/`; it's evidence, not a working
  copy. (This is the project-root `sources/` tree, NOT the `wiki/sources/`
  category — raw originals go to top-level `sources/`, never into `wiki/`.)
- Kebab-case **topical** slugs, `[[wikilinks]]` between related pages, one
  `wiki_append_log` line per write.
- Don't fabricate content. If a file can't be read or confidently classified,
  report it and move to the next one instead of guessing.
