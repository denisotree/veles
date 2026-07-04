---
title: Configure per-task model routing
topics: [route, routing, ensemble, provider, model, task]
related: ["cmd:route"]
---

Use `veles route {show,set,reset,refresh}` to inspect and edit which
provider+model handles each task type in the ensemble (`[routing.tasks]` in
`config.toml`).

`veles route show` prints the resolved routing table; `veles route set
<task> <provider>:<model>` pins a task to a spec; `veles route reset` reverts
to defaults; `veles route refresh` re-parses natural-language routing hints
from `AGENTS.md` (explicit config entries always win).

Example: `veles route set compressor anthropic:claude-haiku-4.5`.
