---
name: ingest
description: Read a source URL or file and write a wiki page summarising it (LLM Wiki layout)
tools: [fetch_url, read_file, wiki_write_page, wiki_append_log]
parameters:
  - name: source
    type: string
    description: URL, local file path, or short text to ingest
---

You ingest a source into the project's LLM Wiki.

1. If the source looks like a URL, fetch it with `fetch_url`. If it's a local
   path, read it with `read_file`. Otherwise treat it as inline text the user
   pasted.
2. Read the content carefully. Identify what it's about, the key claims, the
   shape (article / tutorial / reference / dataset).
3. Pick a slug: short, kebab-case, descriptive (e.g. `attention-is-all-you-need`).
   Pick a category: usually `concepts` for ideas, `sources` for cited material,
   `notes` for ad-hoc captures. Don't write into `sources/` itself — that zone
   is read-only.
4. Call `wiki_write_page` with the chosen category and slug. The body should
   capture the source's claims in your own words, with citations back to the
   source URL/path. Keep it 200–800 words for a typical article.
5. Append one line to `LOG.md` via `wiki_append_log` summarising what was
   ingested: `ingest <slug> from <source>`.

If the source can't be fetched or read, report the failure and stop — do not
fabricate a page from nothing.
