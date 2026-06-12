# Multi-agent orchestration

> 🌐 **Languages:** **English** · [Русский](../../ru/explanation/multi-agent-orchestration.md)

For complex work, Veles can split a task across a **manager** and specialised
**worker** sub-agents instead of doing everything in one context. This page
explains the model; to turn it on, see
[manager mode](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt).

## The shape

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- The **manager** plans the decomposition and coordinates — but it does **not**
  write the final deliverable itself.
- **Workers** have role-specific system prompts: `explorer` gathers, `writer`
  produces the answer, `advisor` reviews. The set is extensible.
- At the end, the manager writes a short report into memory.

## No telephone game

A key rule: intermediate artefacts reach the synthesiser **verbatim**, not as the
manager's paraphrase. An explorer's findings are handed to the writer directly, so
detail isn't lost through a chain of summaries. This is what makes decomposition
add quality rather than dilute it.

## Why "the manager never writes"

If the coordinator also wrote the answer, it would be tempted to shortcut the
workers and lose the benefit of specialisation. Keeping synthesis in a dedicated
`writer` (fed verbatim inputs) enforces the division of labour. Veles makes this a
runtime guarantee.

## When it helps — and when it doesn't

Decomposition pays off for broad or multi-faceted tasks (audit this codebase,
research this question from several angles). For a quick, single-context request it
just adds overhead — which is why manager mode is **explicit opt-in**, off by
default (`veles run --manager` or `VELES_MANAGER_MODE=1`).
