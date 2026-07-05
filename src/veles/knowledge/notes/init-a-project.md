---
title: Initialize a new Veles project
topics: [init, project, scaffold, layout, setup, new]
related: ["cmd:init", "flag:init:--layout", "flag:init:--force"]
---

Run `veles init` in a directory to scaffold a new Veles project: `.veles/`
state, `AGENTS.md`, and the default `llm-wiki` layout's wiki tree.

Pass `--layout notes` or `--layout bare` for a lighter builtin scaffold pack
instead of the LLM Wiki default (or point at a custom pack under
`~/.veles/layouts/<name>/layout.toml`). Pass `--force` to recreate `.veles/`
even if it already exists.

Example: `veles init --layout notes my-project`.
