---
title: Inspect and manage saved sessions
topics: [sessions, session, history, search, delete, list]
related: ["cmd:sessions"]
---

Use `veles sessions {list,show,delete,search}` to inspect past agent runs.
`veles sessions list` shows recent sessions; `veles sessions show <id>`
prints a session's full turn history.

`veles sessions search "<query>"` runs FTS5 full-text search over turn
content across all sessions; `veles sessions delete <id>` permanently removes
a session and its turns.

Example: `veles sessions search "wiki page"`.
