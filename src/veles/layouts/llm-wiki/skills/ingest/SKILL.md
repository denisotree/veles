---
name: ingest
description: Read a source and route its topics into the wiki (create or patch topical pages, LLM Wiki layout)
tools: [fetch_url, read_file, wiki_search, wiki_read_page, wiki_list_pages, wiki_write_page, wiki_add_category, wiki_append_log, move_file]
parameters:
  - name: source
    type: string
    description: URL, local file path, or short text to ingest
---

You ingest a source into the project's LLM Wiki. **A wiki page is a topic, not
a file — page identity is the TOPIC, never the filename or a date.** One source
may be about several distinct topics; route each to its own page.

1. If the source looks like a URL, fetch it with `fetch_url`. If it's a local
   path, read it with `read_file`. Otherwise treat it as inline text the user
   pasted.
2. Read the content carefully and **extract the topics** it covers (zero, one,
   or many) — the standing subjects it's about: concepts, events, people,
   organizations, works. Classify by CONTENT, never by filename or extension.
3. **For each topic, find-or-create-or-patch:**
   - `wiki_search` / `wiki_list_pages` for an existing page on that topic **by
     meaning** (not slug).
   - **None found → create:** pick a category (`concepts` for ideas/events,
     `entities` for people/orgs/works, or add one with `wiki_add_category`),
     a short **topical** kebab-case slug, and call `wiki_write_page`. Capture
     the source's claims in your own words with citations back to the source.
   - **Found → patch:** `wiki_read_page`, weave the new knowledge into the body
     as fact (don't dump raw text), and `wiki_write_page` to overwrite.
4. Dispose of the raw source: for a **file**, relocate the original into the
   top-level `sources/` directory with `move_file` (kept as-is by convention,
   NOT `wiki/sources/`); for a **URL** there is nothing to move. If the source
   has no topical content (empty/boilerplate/duplicate), write no page and move
   the raw file to `sources/_archive/` instead.
5. `wiki_append_log` one line per page you created or patched.

If the source can't be fetched or read, report the failure and stop — do not
fabricate a page from nothing.
