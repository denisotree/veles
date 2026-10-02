---
title: Initialize a new Veles project
topics: [init, project, scaffold, layout, setup, new]
related: ["cmd:init", "flag:init:--layout", "flag:init:--force"]
---

Run `veles init` in a directory to scaffold a new Veles project: `.veles/`
state and `AGENTS.md`. The default layout is `bare`, which adds nothing else;
at a terminal `veles init` asks which layout to use.

Pass `--layout llm-wiki` for the Karpathy-style wiki (`sources/` + `wiki/`) or
`--layout notes` for a flat notes directory — both come from the extension
registry and are offered for install if missing (refusing creates nothing).
A custom pack lives under `~/.veles/layouts/<name>/layout.toml`. Pass `--force`
to recreate `.veles/` even if it already exists.

Example: `veles init --layout llm-wiki my-project`.
