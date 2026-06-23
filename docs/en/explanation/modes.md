# Run modes

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/explanation/modes.md) · [繁體中文](../../zh-TW/explanation/modes.md) · [日本語](../../ja/explanation/modes.md) · [한국어](../../ko/explanation/modes.md) · [Español](../../es/explanation/modes.md) · [Français](../../fr/explanation/modes.md) · [Italiano](../../it/explanation/modes.md) · [Português (BR)](../../pt-BR/explanation/modes.md) · [Português (PT)](../../pt-PT/explanation/modes.md) · [Русский](../../ru/explanation/modes.md) · [العربية](../../ar/explanation/modes.md) · [हिन्दी](../../hi/explanation/modes.md) · [বাংলা](../../bn/explanation/modes.md) · [Tiếng Việt](../../vi/explanation/modes.md)

In the TUI, each prompt is handled by a **run mode** — a strategy that decides how
much autonomy and which tools the turn gets. Cycle modes with `Shift+Tab`; the
order is `auto → planning → writing → goal`.

## The four modes

### `writing` — direct chat
The straightforward mode: your prompt goes to the agent with the full toolset
available, and it responds. Use it for ordinary work where you want the agent to
act.

### `planning` — read-only research + a plan
Mutations are blocked (no `write_file`, no `run_shell`). The agent uses read/search
tools to gather context, then produces a structured plan artefact. Use it to think
before touching anything — or pass `--plan` to `veles run` for the same effect on
the CLI.

### `auto` — smart routing (default)
A quick classification decides whether your prompt is a direct request or calls for
planning, then dispatches to `writing` or `planning` accordingly. It's the smartest
fallback when you haven't expressed intent, which is why it's the default first
stop in the cycle.

### `goal` — long-horizon objective
Drives a finite-state machine for a multi-step objective: it interviews you to
clarify, confirms a plan, executes steps (with advisor checks), and verifies the
done-condition — all under explicit budgets. The CLI equivalent is the
[`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints)
command family.

## Why modes exist

Different requests want different amounts of caution. A quick question shouldn't
require ceremony; a risky change benefits from a read-only planning pass first; a
big objective needs budgets and checkpoints. Modes make that choice explicit and
switchable per turn, instead of baking one behaviour into the whole session.

When you switch mid-session, the agent is told the new rules so its behaviour
changes immediately.
