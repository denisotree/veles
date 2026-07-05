---
title: Delegate a prompt to the multi-agent manager
topics: [manager, orchestration, worker, delegate, decompose, multi-agent]
related: ["cmd:run", "flag:run:--manager"]
---

Pass `--manager` to `veles run` to decompose the prompt via the hierarchical
multi-agent manager (explorer→writer workers) instead of running it as a
single-agent turn. Off by default; enable per-invocation with the flag, or
globally with env `VELES_MANAGER_MODE=1` (`=0` acts as a kill switch).

The manager never writes the final answer itself — it decomposes the task,
spawns specialised workers, and synthesises their verbatim outputs.

Example: `veles run --manager "audit the wiki for stale pages and propose fixes"`.
