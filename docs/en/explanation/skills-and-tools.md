# Skills & tools as accumulating capability

> 🌐 **Languages:** **English** · [Русский](../../ru/explanation/skills-and-tools.md)

Veles starts with a minimal set of tools and skills and **grows** it as it works.
This page explains the difference between the two and how they accumulate. For the
commands, see [manage skills & tools](../how-to/manage-skills-and-tools.md).

## Tools vs skills

- A **tool** is a single executable action — read a file, run a shell command,
  fetch a URL, search the web, write a wiki page. Tools are what the model calls.
- A **skill** is a formalised *process* — a `SKILL.md` with a prompt body and an
  allowed-tool list that runs as a focused sub-agent. Skills compose tools into a
  repeatable workflow (e.g. the LLM-Wiki `ingest`/`query`/`lint`).

## Minimal startup, on-demand expansion

Veles boots with just enough to be useful, plus a known place to pull more from.
Installing extras (a skill, a tool, a module) asks for approval by default; you can
grant standing autonomy. This keeps a fresh project lean while letting capability
grow where it's needed.

## How capability accumulates

1. **Veles writes its own tools.** When it notices a repeating task, it can author
   a clean, typed, reusable Python tool into `<project>/.veles/tools/` (with an
   advisor code-review pass). The tool joins the registry with telemetry.
2. **Repeating processes become skills.** A pattern detector spots recurring tool
   sequences and proposes formalising them as a skill; skills can `extends:`
   another skill to inherit its body and tools.
3. **Telemetry drives ranking.** Every tool/skill carries use/success/error
   counts. These feed dedup (`veles skill dedup`) and promotion suggestions.

## Two scopes, with promotion

Both tools and skills exist at two levels:

- **Project-local** (`<project>/.veles/`) — visible only here.
- **User-global** (`~/.veles/`) — available across every project.

A capability that proves itself in one project can be **promoted** to user scope so
all projects benefit (`veles skill promote`, `veles tool promote`), or **demoted**
back. This is how Veles carries hard-won workflows between projects.

## Why a registry, not just files

Storing skills/tools as plain files keeps them inspectable and editable; storing
their *telemetry* in `memory.db` lets Veles reason about which ones actually work.
The combination is what turns "a folder of scripts" into accumulating, self-curated
capability.
