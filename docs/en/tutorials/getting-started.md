# Getting started

> 🌐 **Languages:** **English** · [Русский](../../ru/tutorials/getting-started.md)

In this tutorial you install Veles, give it an API key, create your first project,
and run your first prompt. About 10 minutes. You'll end with a working Veles
project you can talk to.

## Prerequisites

- **Python 3.13** (Veles pins `>=3.13,<3.14`).
- An LLM API key. We'll use **OpenRouter** (the default provider); any of the
  [other providers](../reference/providers.md) works too, including fully local
  ones with no key.

## 1. Install

Veles installs as a global `veles` command via [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

To update later: `uv tool install . --reinstall`.

## 2. Give Veles an API key

Get a key from [openrouter.ai](https://openrouter.ai) and export it:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

You can also store it in the OS keychain so you don't re-export it every shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(Prefer a fully local setup with no key? Install [Ollama](https://ollama.com),
`ollama pull qwen3:4b-instruct`, and use `--provider ollama` below.)

## 3. Create your first project

A Veles project is just a directory with a `.veles/` state folder. Create one:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

This creates `AGENTS.md` (your project context), `sources/` and `wiki/` (the
default [LLM-Wiki layout](../explanation/layout-packs-and-llm-wiki.md)), and
`.veles/` (machine state). See [project layout](../reference/project-layout.md).

## 4. Run your first prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles loads your project context, calls the model, and prints the answer. The
turn is saved to the project's memory.

Add `--stream` to see tokens as they arrive, or `--verbose` for per-turn progress:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Open the interactive REPL

For a multi-turn conversation, open the TUI:

```bash
veles tui
```

Type a message and press Enter. Useful keys: `Ctrl+D` to exit, `Shift+Tab` to
cycle [run modes](../explanation/modes.md), `/help` to list slash commands. Full
list in the [TUI reference](../reference/tui.md).

## 6. See what Veles remembers

Every run is saved. List and search your sessions:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Where to go next

- **[Building a knowledge base](building-a-knowledge-base.md)** — ingest sources
  into the wiki and ask questions about them.
- **[Configure providers](../how-to/configure-providers.md)** — switch to
  Anthropic, OpenAI, Gemini, or a fully local model.
- **[Architecture overview](../explanation/architecture.md)** — understand what
  Veles is doing under the hood.
