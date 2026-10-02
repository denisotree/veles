# Layout packs & the LLM-Wiki

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

A **layout pack** defines how a project's *user content* is organised — which
directories exist, which the agent may write to, and which operations it offers.
The default is **`bare`**, which adds nothing to your directory but `.veles/` and
`AGENTS.md`. The **LLM-Wiki** is one option from the extension registry, **not**
a core Veles principle.

## What a layout pack is

A layout pack is a directory with a `layout.toml` manifest (plus optional
skill and template files). The manifest declares:

- **Writable zones** — directories the agent may write content into
  (enforced on every `write_file`).
- **Read-only zones** — material the agent reads but never modifies.
- **Operations** — named workflows, shipped as skills inside the pack.
- **Scaffold** (`[layout.scaffold]`) — what `veles init` creates: directories
  and an optional `AGENTS.md` template (`{name}` is substituted).
- **Engines** (`[layout.engines]`) — which content machinery the pack asks
  for. An engine is supplied by a module (the registry's `wiki` module
  supplies `wiki`). Without it, no wiki tools, no wiki recall, no INDEX
  injection exist in the project.
- **Context file** (`context_file`) — a file injected into the agent's
  stable system prompt (the LLM-Wiki uses `INDEX.md`).

## Available packs

| Pack | Where from | What `veles init --layout <name>` produces |
|---|---|---|
| `bare` *(default)* | built in | No content scaffold at all — for code repositories and free-form work. Writes are permissive inside the project root (still subject to the trust ladder). |
| `llm-wiki` | registry (`public:official/llm-wiki`, brings the `wiki` module) | The [Karpathy-style LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (raw, readonly by convention — not enforced), `wiki/` (agent-writable), `INDEX.md` injected into the prompt, `ingest`/`query`/`lint`/`organize`/`structure_design` skills, the wiki engine on, `veles add` and `/wiki`. A layout-declared behavioural prompt (`templates/behaviour.md`) carries the sources/wiki discipline and the migration/log-patch rules. |
| `notes` | registry (`public:official/notes`) | A single flat `notes/` directory the agent writes into. No wiki machinery. |

`veles init` at a terminal asks which pack to use (installed ones and those in
your registries); choosing one that isn't installed offers to install it.
`veles registry install llm-wiki` installs it ahead of time.

## Projects from before 1.2.3

A project whose layout isn't installed (an `llm-wiki` project after upgrading,
or one with no `layout` key — those were all wiki projects) still opens. At a
terminal, `veles` and `veles run` offer to install the pack (with the engine it
needs) under one confirmation; elsewhere — the daemon, channels, other verbs —
Veles prints the install command once and works without the wiki. Nothing in
`wiki/` is touched.

## Custom layouts

Drop a pack into `~/.veles/layouts/<name>/layout.toml` (user-global) or
`<project>/.veles/layouts/<name>/` (project-local; shadows user and builtin
packs of the same name) and pass `veles init --layout <name>`. The registry's
`notes` pack is a minimal example to copy. A pack that asks for an engine no
installed module supplies gets the same install offer. You can also describe
conventions in `AGENTS.md` — the layout enforces zones, AGENTS.md guides
behaviour.

## What it is *not*

The layout governs **your content only**. Veles' own project memory —
`memory.db` plus the `.veles/memory/` artefact tree (insights, session
digests, proposals, the system-ops journal) — is system-side and works
identically under any layout. Switching layouts never touches the learning
loop, sessions, or registries. See [architecture](architecture.md) and
[project layout](../reference/project-layout.md).
