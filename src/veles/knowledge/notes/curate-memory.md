---
title: Curate session memory into durable project memory
topics: [curate, memory, session, compaction, insights, learning]
related: ["cmd:curate"]
---

Run `veles curate` to distill unprocessed sessions into durable memory: one
wiki page per session (when the active layout has the wiki engine) plus SQL
insights always.

Use `--limit N` to cap how many sessions are curated in one run (default 20).
This is the core learning-loop step — run it periodically, or rely on the
continuous curator triggers that fire automatically during `veles run`.

Example: `veles curate --limit 5`.
