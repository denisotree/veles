---
title: Add a source to the wiki
topics: [add, source, ingest, wiki, page, file, url]
related: ["cmd:add"]
---

Run `veles add <path-or-url>` to read a source and write a wiki page from it
(this replaced the old `ingest` verb). The source can be a local file, a
directory, or an `http(s)://` URL.

Use `--recursive` with a directory (optionally `--glob PATTERN`) to ingest
every matching file underneath it, one wiki page per file.

Example: `veles add ./docs --recursive --glob '*.md'`.
