# How to back up and share a project

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · [Italiano](../../it/how-to/backup-and-share.md) · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · [বাংলা](../../bn/how-to/backup-and-share.md) · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

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
