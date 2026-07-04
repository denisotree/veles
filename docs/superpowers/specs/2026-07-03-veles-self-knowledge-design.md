# Design: Veles self-knowledge for how-to answers (M186)

**Date:** 2026-07-03
**Status:** approved (brainstorming) — pending spec review
**Milestone:** M186 (ceiling at authoring time: M185)

## Problem

When a user asks *"how do I do X in Veles"*, the agent has no authoritative
source of Veles usage knowledge in context. It answers from the model's
priors — which for a niche framework means hallucination, especially on
weak/local models. Veles should "know about itself better than anyone" and
answer how-to questions accurately from current documentation.

The existing `core/self_doc.py` is **not** this: it generates a *per-project
state snapshot* (session count, this project's skills/tools/routing/insights,
LOG tail). It answers "what does this project have," not "how do I use feature
X of Veles." Nothing ingests VISION.md / docs / CLI usage into a form the
agent can recall, and nothing triggers on how-to questions.

## Goals

- A framework-global source of Veles usage knowledge, injected into context so
  even a weak model answers how-to questions from real docs, not guesses.
- Fresh facts (commands/flags/skills never lie about what exists) + depth
  (why/how/examples) — without a rot-prone manual burden.
- Engine-independent: works in any layout (`llm-wiki`, `notes`, `bare`), since
  it is about Veles-the-framework, not the project's user content.

## Non-goals

- Not replacing `self_doc` (per-project state) — the two are complementary.
- Not a general RAG over all of VISION.md/docs verbatim — that is Russian,
  huge, and lands poorly on weak models (no short digested entries).
- No brittle "meta-question detector." Relevance ranking + a threshold does the
  gating naturally (a non-Veles query scores ~0 and surfaces nothing).

## Decisions (from brainstorming)

1. **Source = hybrid**: a *live skeleton* generated from code (never stale) +
   a thin layer of *curated how-to notes* (depth/why) shipped in the package.
2. **Delivery = hybrid**: always-available **auto-recall** (query-driven,
   per-turn) + an explicit **tool** for deep lookups when the recalled digest
   is not enough. The weak-model base case needs no tool call.
3. **Storage/freshness**: curated notes ship in `src/veles/` (like
   `builtin_skills`); the skeleton is generated from code; a **CI guard** test
   fails when a note references a command/flag/skill that no longer exists.
4. **Ranking = lightweight token-overlap** (same family as
   `core/skill_pattern_detector.py`) with a minimum-relevance threshold. No
   FTS index, no embeddings — right-sized for a curated set of tens of notes,
   deterministic, offline, and self-gating on non-Veles queries.
5. **Notes language = English** (matches code convention). The agent still
   answers in the user's language — the model translates the recalled content.

## Architecture — new module `core/knowledge/`

Single knowledge source, two surfaces (recall + tool). Framework-global,
distinct from per-project memory.

```
src/veles/
  knowledge/
    notes/*.md              # curated how-to notes, shipped in the package
  core/knowledge/
    __init__.py
    skeleton.py             # generate live capabilities from code
    notes.py                # load + parse notes/*.md (frontmatter + body)
    store.py                # KnowledgeStore: search(query, limit) + get(topic)
```

### `skeleton.py` — live capabilities from code

Introspects, at load time:
- **Commands + flags** — walk the argparse parser tree (`cli/_parsers/`).
- **Builtin skills** — `discover_skills(project=None, builtin_only=True)`
  (name + description).
- **Builtin tools** — the tool registry (name + description).
- **Config keys** — the config schema / known `[section] key` names.

Produces a list of `SkeletonEntry(kind, name, summary, aliases)` — the
"what exists" backbone. Never stale because it is derived, not written.

### `notes.py` — curated how-to notes

Each `notes/<slug>.md`:

```markdown
---
title: Run an interactive agent session
topics: [run, agent, session, prompt, interactive]
related: ["cmd:run", "flag:run:--manager", "skill:structure_design"]
---

To start an interactive run: `veles run "your prompt"`.
Why / when to use the REPL vs `run` ...
Example ...
```

- `title` — short, human-readable.
- `topics` — extra keywords for ranking (beyond body tokens).
- `related` — typed refs (`cmd:`, `flag:<cmd>:`, `skill:`, `tool:`, `config:`)
  the CI guard validates against the skeleton.
- Body — the depth layer: how + why + a concrete example.

`parse_note(path) -> Note(title, topics, related, body, slug)`.

### `store.py` — `KnowledgeStore`

- Loads notes (`notes.py`) + skeleton (`skeleton.py`) once; caches.
- `search(query, *, limit) -> list[KnowledgeHit]`:
  token-overlap score of `query` tokens against each entry's searchable text
  (title + topics + body for notes; name + summary + aliases for skeleton
  entries). Below a minimum-score threshold → excluded. Returns top-`limit`.
- `get(topic) -> KnowledgeHit | None`: exact/slug/title lookup for the tool's
  "give me the full note" path.
- `KnowledgeHit`: `{source: "note"|"skeleton", title, body, score}`.

Ranking detail: normalize to lowercase word tokens, drop stopwords, score =
sum of query-token hits weighted (title/topics > body). The threshold is a
constant tuned so a generic coding query ("fix this failing test") yields no
hits, while "how do I run a session in veles" surfaces the run note.

## Delivery surface 1 — auto-recall

New collector on `MemoryRouter` (`core/memory/router.py`):

- `_collect_about_veles(query, *, limit) -> list[RecallHit]` — calls
  `KnowledgeStore.search`, maps hits to `RecallHit` with a distinct source
  tag (e.g. `about-veles`). Added as a new stream in the round-robin
  `recall()` merge alongside wiki/insights/turns/extras.
- Engine-independent: does **not** consult `wiki_enabled` — the store is
  package-shipped, present in every layout.
- Self-gating: below-threshold queries contribute zero hits, so normal coding
  turns are unaffected; the `<memory-context>` block only carries Veles docs
  when the turn is actually about Veles.

The `injector.py` `<memory-context>` formatting already renders `RecallHit`s;
the new source rides that path with a short label so the model sees it is
authoritative Veles documentation.

## Delivery surface 2 — tool `veles_help`

Builtin tool in `core/tools/builtin`:

- `veles_help(query: str) -> str` — runs `KnowledgeStore.search`/`get` and
  returns the **full** matching note(s) + relevant skeleton lines, formatted
  markdown. For when the recalled digest is not enough (deep/edge questions).
- Shares the same `KnowledgeStore` singleton as recall — one source, two
  surfaces. Registered as a normal builtin tool (available to `_RUN_TOOLS`).

## Anti-rot — CI guard

`tests/test_knowledge_freshness.py`:

- Build the skeleton from code.
- For every note, parse `related` refs and assert each exists in the skeleton
  (`cmd:run` → a `run` command entry; `flag:run:--manager` → that flag on that
  command; `skill:structure_design` → a builtin skill; etc.).
- Fail with a clear message naming the note + the dangling ref.

Effect: removing/renaming a command turns the referencing note's test red,
forcing the note to be updated in the same change. This is what keeps the
curated layer honest against the CLAUDE.md "no back-compat, remove outright"
convention.

## Relationship to `self_doc`

Kept, unchanged. `self_doc` = per-project *state* snapshot (this project's
sessions/insights/routing). `core/knowledge` = framework *usage* knowledge,
identical across projects. Different questions, different lifetimes, no overlap.
(A future follow-up could have `self_doc` link to `veles_help`, but that is out
of scope here.)

## Data flow

```
User: "как в veles сделать X"
  │
  ├─ pre-turn: MemoryRouter.recall(query)
  │     └─ _collect_about_veles → KnowledgeStore.search
  │           └─ token-overlap ≥ threshold → top notes/skeleton
  │     └─ merged into <memory-context> (source: about-veles)
  │
  ├─ model answers from recalled digest (weak-model base case: no tool needed)
  │
  └─ if digest insufficient: model calls veles_help(query)
        └─ KnowledgeStore.search/get → full note(s) → back into the loop
```

## Components & boundaries

| Unit | Does | Depends on |
|------|------|------------|
| `skeleton.py` | Derive "what exists" from code | argparse tree, `discover_skills`, tool registry, config schema |
| `notes.py` | Parse curated `.md` notes | filesystem (package data) |
| `store.py` | Search/get over notes+skeleton | `skeleton.py`, `notes.py` |
| `_collect_about_veles` | Recall surface | `store.py`, `RecallHit` |
| `veles_help` tool | Deep-lookup surface | `store.py` |
| freshness test | Anti-rot guard | `skeleton.py`, `notes.py` |

Each unit is independently testable; `store.py` is the only shared seam.

## Testing

- **Unit** — `skeleton` generation (commands/flags/skills/tools present);
  `notes` parsing (frontmatter + body); `store.search` ranking + threshold
  (non-Veles query → []); `store.get` lookup.
- **Integration** — `MemoryRouter.recall` surfaces an about-veles hit on a
  how-to query and none on a plain coding query; `veles_help` returns full
  note text.
- **Freshness** — the CI guard test (above).

## Open questions / risks

- **Threshold tuning** — needs a couple of representative queries in tests to
  lock the constant; too low pollutes normal turns, too high misses. Mitigated
  by explicit positive/negative test cases.
- **Initial note set** — start small (~10-15 notes covering the top commands:
  `run`, `init`, `add`, `curate`, skills/modules, sessions, project/subproject,
  routing, trust, mcp, daemon/channels). Grow as gaps surface.
- **argparse introspection depth** — subparser/flag walking must handle the
  `cli/_parsers/` structure; if brittle, fall back to a registered command list.
```
