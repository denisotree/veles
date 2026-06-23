# How to manage skills, tools, and modules

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles accumulates capability over time. **Skills** are reusable workflows,
**tools** are executable actions, **modules** are optional plug-ins. Each lives at
two scopes: project-local (`<project>/.veles/`) and user-global (`~/.veles/`). For
the concepts, see [skills & tools](../explanation/skills-and-tools.md).

## Skills

A skill is a `SKILL.md` (frontmatter + prompt body) the agent can invoke like a
tool.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Promote / demote between scopes

A skill that proves useful in one project can move to user scope so every project
sees it (or the reverse):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Find duplicates and promotion candidates

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Tools

Tools are catalogued in the project's `memory.db` with usage telemetry. Veles can
write its own tools as it works; you manage them with:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Sensitive tools (`run_shell`, `write_file`, `fetch_url`, …) are gated by the
[trust ladder](security-and-permissions.md).

## Modules

Modules add optional capabilities (embeddings, vision, STT) without bloating the
core. Installing one requires confirmation by default.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## Discover more

Browse the curated registries:

```bash
veles browse skills [query]
veles browse modules [query]
```
