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

A module is Python code (`module.toml` + an entrypoint) that runs inside Veles —
adding optional capabilities (memory providers, embeddings, vision, STT) without
bloating the core. Installing one requires confirmation by default, and it loads
on every run only while its files still match what you approved (see [keep
installs honest](extension-registries.md#keep-installs-honest)).

```bash
veles module list                              # both scopes, with a `scope` column
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # install to ~/.veles/modules/, all projects
veles module show <name> [--user]
veles module remove <name> [--user]
veles module approve <name> [--user]
```

Modules live at two scopes, same as skills and tools: project-local
(`<project>/.veles/modules/`) and user-global (`~/.veles/modules/`, loaded in
every project). A user-level module goes through the same approval gate as a
project one, and the gate runs before names are compared. If a project and a
user module share a name, an approved project module loads and Veles warns
about the user-level one being shadowed; an unapproved project module is
skipped (the warning names its directory) and the user module loads. Two
approved modules at the same scope sharing a name — the first (sorted by
directory) loads, the rest warn and are skipped. `veles module
{show,approve,remove}` take the manifest name (what `list` shows) and refuse
a name that more than one directory in the scope declares, listing them;
`veles module add` refuses to install a module whose name another directory
in the scope already declares.

### Write a module that adds a memory provider

Memory providers are one of several contribution points — for tools, recall,
prompt blocks, dream steps and the rest, see
[extend Veles with a module](extend-veles-with-modules.md).

A module's `register(api)` entrypoint can call
`api.add_memory_provider(name, factory)` to plug an external memory source
into recall. `name` must match a `[memory.external.<name>]` section in
`~/.veles/config.toml`; `factory` is called with that section (a `dict`) and
must return an object implementing Veles's `MemoryProvider` protocol
(`veles.core.memory.provider`), or `None` to skip the provider:

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

A provider that also implements `ingest(title, body, *, insight_id) ->
bool` (the `IngestingMemoryProvider` protocol) gets Veles's writes too, not
just reads. If two modules register the same provider name, loading the
second module fails — it is skipped with a warning, nothing partial is left
registered. A section configured in `config.toml` whose module isn't
installed prints one warning with the install command; recall keeps working
without it.

The registry ships Honcho, Mem0 and Supermemory as ready-made provider
modules — install with `veles registry install --user {honcho,mem0,supermemory}`,
then run the `uv tool install veles-ai --with '<package>'` command the install
prints (each declares an SDK — `mem0ai>=2.0`, `honcho-ai>=2.5`,
`supermemory>=3.62` — that Veles never installs for you), and fill in the
matching `[memory.external.<name>]` section:

- **mem0**: `api_key`, `user_id`, optional `agent_id` (also recall that
  agent's memories) and `host`. SDK telemetry is off by default; each recall
  makes one extra `GET /v1/ping/` request.
- **supermemory**: `api_key`, optional `user_id` (sent as the search's
  `container_tag`) and `base_url`.
- **honcho**: `api_key`, `workspace_id`, optional `peer_id` (search only that
  peer's messages) and `base_url`. Each recall does a workspace
  get-or-create — it creates `workspace_id` if it doesn't already exist.

## Discover more

Search connected extension registries and install reviewed skills, tools,
and modules — see [Install extensions from registries](extension-registries.md):

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
veles registry install <name>
```
