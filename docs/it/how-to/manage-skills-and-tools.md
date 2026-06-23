# Come gestire skill, strumenti e moduli

> 🌐 **Lingue:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles accumula capacità nel tempo. Le **skill** sono workflow riutilizzabili, gli
**strumenti** sono azioni eseguibili, i **moduli** sono plug-in opzionali. Ciascuno
vive a due livelli: locale al progetto (`<project>/.veles/`) e globale all'utente
(`~/.veles/`). Per i concetti, vedi [skill e strumenti](../explanation/skills-and-tools.md).

## Skill

Una skill è un `SKILL.md` (frontmatter + corpo del prompt) che l'agente può
invocare come uno strumento.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Promozione / retrocessione tra i livelli

Una skill che si rivela utile in un progetto può passare al livello utente in modo
che ogni progetto la veda (o viceversa):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Trovare duplicati e candidati alla promozione

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Strumenti

Gli strumenti sono catalogati nel `memory.db` del progetto con la telemetria
d'uso. Veles può scrivere i propri strumenti mentre lavora; li gestisci con:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Gli strumenti sensibili (`run_shell`, `write_file`, `fetch_url`, …) sono protetti
dalla [scala di fiducia](security-and-permissions.md).

## Moduli

I moduli aggiungono capacità opzionali (embedding, vision, STT) senza appesantire
il core. L'installazione di uno richiede conferma per impostazione predefinita.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## Scopri di più

Sfoglia i registri curati:

```bash
veles browse skills [query]
veles browse modules [query]
```
