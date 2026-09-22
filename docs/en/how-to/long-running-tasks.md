# How to run long-running tasks: goals, jobs, dreaming, research

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/how-to/long-running-tasks.md) · [繁體中文](../../zh-TW/how-to/long-running-tasks.md) · [日本語](../../ja/how-to/long-running-tasks.md) · [한국어](../../ko/how-to/long-running-tasks.md) · [Español](../../es/how-to/long-running-tasks.md) · [Français](../../fr/how-to/long-running-tasks.md) · [Italiano](../../it/how-to/long-running-tasks.md) · [Português (BR)](../../pt-BR/how-to/long-running-tasks.md) · [Português (PT)](../../pt-PT/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · [العربية](../../ar/how-to/long-running-tasks.md) · [हिन्दी](../../hi/how-to/long-running-tasks.md) · [বাংলা](../../bn/how-to/long-running-tasks.md) · [Tiếng Việt](../../vi/how-to/long-running-tasks.md)

Beyond single prompts, Veles can pursue multi-step **goals** with budgets, run
**scheduled jobs**, **dream** to consolidate memory, **research** the web in
parallel, and decompose work across a **manager** and sub-agents.

## Goals — objectives with budgets and checkpoints

A goal is a long-horizon objective with explicit limits and a progress log.
`veles goal start` runs it in the foreground — plan, execute a step, check it
against the done condition, repeat — until the condition is met or a budget
runs out:

```bash
veles goal start "Draft a competitor analysis report" \
  --done-when "report.md exists and cites >=3 sources" \
  --max-steps 30 --max-cost-usd 5 --max-wall-time-s 3600

veles goal list
veles goal show <id>
veles goal pause <id> ; veles goal resume <id>
veles goal cancel <id> --reason "scope changed"
```

`--done-when` is required: it is what the check phase tests. Tool approvals
prompt in the terminal as they do for `veles run`; run unattended (cron) only
with autopilot on. An interrupted or paused goal continues where it stopped with
`veles goal resume <id>`. Exit code: `0` done, `3` cancelled (budget or
infeasible), `4` stopped (stalled, paused, turn cap).

In the TUI, the **goal** run mode (cycle with `Shift+Tab`) drives the same FSM
interactively: it interviews you, confirms a plan, executes, and checks.

## Jobs — scheduled agent runs

Schedule a prompt to run on a cron expression, an interval, or once at a time:

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # run on the next tick
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

`--schedule` accepts a cron expression, `<N><s|m|h|d>` (e.g. `30m`), or an ISO
timestamp. Jobs run when the daemon is up, or run them all once synchronously:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

Deliver a job's output to a channel with `--deliver-to telegram:<chat_id>`.

## Dreaming — background memory consolidation

`dream` extracts insights, deduplicates skills, suggests promotions, and lints the
wiki — keeping memory fresh without you waiting:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

A running daemon dreams automatically when idle.

## Research — parallel web investigation

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles decomposes the question, explores angles in parallel, and synthesises a
cited report.

## Manager mode — decompose any prompt

Turn on multi-agent decomposition for a single run (a manager spawns explorer /
writer / advisor sub-agents and never writes the final answer itself):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

See [multi-agent orchestration](../explanation/multi-agent-orchestration.md).
