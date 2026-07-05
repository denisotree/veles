## LLM Wiki: migration & log-patch behaviour

This layout declares no restricted zones: you may read, move, and write ANY
file under the project root. On a request to organize or migrate the
project (e.g. "read all files here and migrate them into the wiki"),
process the whole directory — not just what's already under `wiki/`.

For each file you migrate, classify it by CONTENT (never by filename or
extension): is it an **article/fact** (standing knowledge) or a
**log-type record** (a dated/periodic remark — a task update, diary
entry, meeting note, status comment)?

### Article or fact

1. Read it, distill it into a wiki page under `wiki/<category>/`
   (kebab-case slug) — the same distillation `ingest` does.
2. Relocate the raw original into `sources/<category>/` with `move_file` —
   the immutable first-source copy, kept by convention.
3. `wiki_append_log` one line describing the migration.

### Log-type record

Treat it as a **patch to existing knowledge**, not a new article:

1. `wiki_search` / `wiki_read_page` for an existing page on the record's
   topic.
2. If found: **semantically weave** the record's substance into the page
   body — integrate it as a fact (e.g. "Already sent books B1, B2, B3 for
   restoration"), don't dump the raw log text. `wiki_write_page` with the
   merged body (overwrite).
3. If no page exists: create one from the record with `wiki_write_page`.
4. Either way, relocate the raw record into `sources/<category>/` with
   `move_file`.
5. `wiki_append_log` one line naming the page touched and what changed.

### Conventions carried over

- `sources/` holds raw first-sources, by convention — don't edit a file
  already under `sources/`; it's evidence, not a working copy.
- Kebab-case slugs, `[[wikilinks]]` between related pages, one
  `wiki_append_log` line per write.
- Don't fabricate content. If a file can't be read or confidently
  classified, report it and move to the next one instead of guessing.
