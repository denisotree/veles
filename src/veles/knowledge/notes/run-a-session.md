---
title: Run an interactive agent session
topics: [run, session, prompt, interactive, agent, repl]
related: ["cmd:run"]
---

Start a one-shot agent run with `veles run "your prompt"`. It executes in the
current project, loading that project's `AGENTS.md` context and memory.

For an interactive REPL instead, run bare `veles` (no subcommand).

Example: `veles run "summarise today's changes and write a wiki page"`.
