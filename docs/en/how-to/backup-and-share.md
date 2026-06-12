# How to back up and share a project

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/backup-and-share.md)

Veles projects are portable. Export a project to a single `.tar.gz` bundle for
backup or migration, or a sanitised template to share without leaking your data.

## Full backup

Packs the entire project (`.veles/` + `AGENTS.md`), minus runtime ephemera (locks,
budget state):

```bash
veles export full ./my-project-backup.tar.gz
```

Restore it anywhere:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

A full bundle includes your `memory.db` (sessions, insights), so treat it like
private data.

## Shareable template

Packs only the reusable scaffolding — schema, skills, modules, and non-session
wiki pages. It **strips** `memory.db`, `sources/`, `sessions/`, trust grants, and
PII-redacts text:

```bash
veles export template ./my-template.tar.gz
```

Hand the template to a colleague; they `veles import` it and get your structure
and skills without your conversation history or raw sources.

## Which to use

| Goal | Command |
|---|---|
| Back up / move a project intact | `veles export full` |
| Share structure + skills, not data | `veles export template` |
