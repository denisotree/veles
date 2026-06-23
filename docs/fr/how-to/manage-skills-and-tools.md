# Comment gérer les compétences, les outils et les modules

> 🌐 **Langues :** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · **Français** · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles accumule des capacités au fil du temps. Les **compétences** (skills) sont des
workflows réutilisables, les **outils** (tools) sont des actions exécutables, les
**modules** sont des greffons optionnels. Chacun existe à deux portées : locale au
projet (`<project>/.veles/`) et globale à l'utilisateur (`~/.veles/`). Pour les
concepts, voir [compétences et outils](../explanation/skills-and-tools.md).

## Compétences

Une compétence est un `SKILL.md` (frontmatter + corps de prompt) que l'agent peut
invoquer comme un outil.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Promouvoir / rétrograder entre les portées

Une compétence qui s'avère utile dans un projet peut être déplacée vers la portée
utilisateur pour que tous les projets la voient (ou l'inverse) :

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Trouver les doublons et les candidats à la promotion

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Outils

Les outils sont catalogués dans le `memory.db` du projet avec une télémétrie
d'utilisation. Veles peut écrire ses propres outils au fil de son travail ; vous
les gérez avec :

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Les outils sensibles (`run_shell`, `write_file`, `fetch_url`, …) sont protégés par
l'[échelle de confiance](security-and-permissions.md).

## Modules

Les modules ajoutent des capacités optionnelles (embeddings, vision, STT) sans
alourdir le cœur. Installer un module nécessite une confirmation par défaut.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## Découvrir davantage

Parcourez les registres organisés :

```bash
veles browse skills [query]
veles browse modules [query]
```
