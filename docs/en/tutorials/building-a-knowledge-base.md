# Building a knowledge base

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · [日本語](../../ja/tutorials/building-a-knowledge-base.md) · [한국어](../../ko/tutorials/building-a-knowledge-base.md) · [Español](../../es/tutorials/building-a-knowledge-base.md) · [Français](../../fr/tutorials/building-a-knowledge-base.md) · [Italiano](../../it/tutorials/building-a-knowledge-base.md) · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · [Português (PT)](../../pt-PT/tutorials/building-a-knowledge-base.md) · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · [العربية](../../ar/tutorials/building-a-knowledge-base.md) · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · [বাংলা](../../bn/tutorials/building-a-knowledge-base.md) · [Tiếng Việt](../../vi/tutorials/building-a-knowledge-base.md)

In this tutorial you turn a Veles project into a living knowledge base: ingest a
few sources, let Veles write wiki pages, ask questions, and consolidate what you
learned. This is the default **LLM-Wiki** workflow. About 15 minutes.

You should have finished [Getting started](getting-started.md) first.

## The idea

A Veles project has two content zones:

- `sources/` — raw material you give it, kept as-is by convention (not
  hard-enforced — the agent can technically write anywhere in the project).
- `wiki/` — the agent's own, LLM-generated knowledge, and the zone it's
  expected to write content into.

You feed in sources; Veles distils them into linked wiki pages; you query the
wiki in natural language. See [layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)
for the why.

## 1. Ingest a source

`veles add` reads a file or URL and writes a wiki page summarising it:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

Each `add` produces a page under `wiki/` and links it into the wiki graph.

## 2. Watch the wiki grow

Look at what was written:

```bash
ls wiki/concepts wiki/entities
```

Pages cross-reference each other. The on-demand `wiki/INDEX.md` catalog keeps a
map the agent loads when it needs it (not a monolithic context dump).

## 3. Ask questions

Now query your knowledge base in natural language:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles searches the wiki, reads the relevant pages, and answers — grounded in what
you ingested rather than its training data alone.

For interactive back-and-forth, do the same in the TUI (just run `veles`).

## 4. Consolidate sessions

As you work, conversations accumulate. Run the curator to compact them into
durable wiki pages and extract lessons:

```bash
veles curate
```

This writes `wiki/sessions/` pages and updates the project's insights and rules.
Veles also does this automatically over time — see
[project memory & the learning loop](../explanation/project-memory-and-learning-loop.md).

## 5. Keep the wiki healthy

Over time pages go stale or orphan. The `lint` operation finds them:

```bash
veles run "lint"
```

(`ingest`, `query`, and `lint` are skills bundled with the LLM-Wiki layout; you
invoke them with `veles run "<operation>"` or let the agent call them.)

## What you built

A self-organising knowledge base: sources in, linked wiki pages out, queryable in
natural language, that gets tidier as Veles consolidates. From here:

- **[Manage skills, tools, and modules](../how-to/manage-skills-and-tools.md)** —
  teach Veles reusable workflows.
- **[Run as a daemon](../how-to/run-as-daemon.md)** + **[connect Telegram](../how-to/connect-telegram.md)** —
  talk to your knowledge base from your phone.
- **[Multiple projects & subprojects](../how-to/multi-project-and-subprojects.md)** —
  scale to many knowledge bases.
