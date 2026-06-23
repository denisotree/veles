# Project memory & the learning loop

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/explanation/project-memory-and-learning-loop.md) · [繁體中文](../../zh-TW/explanation/project-memory-and-learning-loop.md) · [日本語](../../ja/explanation/project-memory-and-learning-loop.md) · [한국어](../../ko/explanation/project-memory-and-learning-loop.md) · [Español](../../es/explanation/project-memory-and-learning-loop.md) · [Français](../../fr/explanation/project-memory-and-learning-loop.md) · [Italiano](../../it/explanation/project-memory-and-learning-loop.md) · [Português (BR)](../../pt-BR/explanation/project-memory-and-learning-loop.md) · [Português (PT)](../../pt-PT/explanation/project-memory-and-learning-loop.md) · [Русский](../../ru/explanation/project-memory-and-learning-loop.md) · [العربية](../../ar/explanation/project-memory-and-learning-loop.md) · [हिन्दी](../../hi/explanation/project-memory-and-learning-loop.md) · [বাংলা](../../bn/explanation/project-memory-and-learning-loop.md) · [Tiếng Việt](../../vi/explanation/project-memory-and-learning-loop.md)

Veles' defining feature is that it **remembers** and **learns** per project. This
page explains what that memory is and how the learning loop keeps it useful.

## Memory is a structured artefact

Project memory lives in `<project>/.veles/` — `memory.db` (SQLite, the source
of truth) plus a human-readable `.veles/memory/` tree (rendered insight views,
session digests, proposals, a system-ops journal). It is **separate from your
content** and works identically under any layout (wiki, notes, or bare). It is
not a chat transcript dump — it is a set of structured layers:

- **Session log** — every conversation, one row per turn, full-text indexed.
- **Rules** — short imperatives the agent should follow (`format`, `do`, `don't`,
  `preference`), injected into the stable system prompt.
- **Insights** — lessons distilled from sessions. The SQL row is canonical
  (recall, aging, and dedup operate on it); a markdown view is rendered to
  `.veles/memory/insights/` for humans and exports.
- **Project tree map** — a cached, semantically-tagged file map so the agent reads
  the 3–5 relevant files, not the whole tree.
- **Skill & tool registries** — with telemetry (use/success/error counts) that
  ranking and dedup use.

See the table list in [project layout](../reference/project-layout.md#project-memory-velesmemorydb).

## Recall: small context, pulled on demand

`AGENTS.md` is deliberately small. When you ask something, Veles pulls in only
what's relevant: matching past turns (full-text + optional vector reranking),
applicable rules and insights, and the files the project-tree map scores highest.
This keeps each model call focused and cheap instead of dumping everything.

## The learning loop

Experience becomes durable knowledge through three mechanisms:

### Insights — capturing lessons
After a run, an extractor looks for things worth remembering: explicit "remember
X" / "never Y" feedback, and tool-error→recovery patterns (a failure followed by a
fix). It distils these into insights and rules so the same mistake isn't repeated.

### Curator — consolidating sessions
The curator distills older sessions into durable memory: SQL insights and rules
always; additionally a `wiki/sessions/` page when the project's layout enables
the wiki engine. It runs on idle/post-turn timers, or on demand with `veles curate`.

### Dreaming — background maintenance
`veles dream` (and the daemon when idle) extracts insights, deduplicates skills
and insights, suggests promotions, and (under a wiki layout) lints the wiki —
keeping memory fresh without blocking you. Add `--include-consolidation` for a
deeper LLM pass.

## Context compression

Long conversations are kept under the model's context limit by a sliding-window
compressor: when in-memory history crosses a token threshold, the middle is
summarised (by a cheap routed model) and replaced with a pointer to the saved
summary in `.veles/memory/sessions/`. The full history always remains in
`memory.db` — only the in-memory window is compressed, so it's lossless on disk.

## Why this matters

Because memory is structured and the loop runs continuously, a Veles project gets
**more useful the more you use it** — it learns your conventions, avoids repeated
errors, and grounds answers in what it has actually seen.
