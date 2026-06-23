# Sauvegarder et partager un projet

> 🌐 **Langues :** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · **Français** · [Italiano](../../it/how-to/backup-and-share.md) · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · [বাংলা](../../bn/how-to/backup-and-share.md) · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

Les projets Veles sont portables. Exportez un projet sous forme d'une unique archive
`.tar.gz` pour la sauvegarde ou la migration, ou bien sous forme d'un modèle assaini
afin de le partager sans divulguer vos données.

## Sauvegarde complète

Empaquette l'intégralité du projet (`.veles/` + `AGENTS.md`), à l'exception des
éléments éphémères d'exécution (verrous, état du budget) :

```bash
veles export full ./my-project-backup.tar.gz
```

Restaurez-le n'importe où :

```bash
veles import ./my-project-backup.tar.gz                # dans le répertoire courant
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # écrase un .veles/ existant
```

Une archive complète inclut votre `memory.db` (sessions, insights) : traitez-la donc
comme des données privées.

## Modèle partageable

N'empaquette que la structure réutilisable — schéma, compétences, modules et pages wiki
hors session. Il **supprime** `memory.db`, `sources/`, `sessions/`, les autorisations
de confiance, et caviarde les données personnelles (PII) dans le texte :

```bash
veles export template ./my-template.tar.gz
```

Transmettez le modèle à un collègue ; il l'importe avec `veles import` et récupère
votre structure et vos compétences, sans votre historique de conversation ni vos sources
brutes.

## Lequel utiliser

| Objectif | Commande |
|---|---|
| Sauvegarder / déplacer un projet intact | `veles export full` |
| Partager structure + compétences, pas les données | `veles export template` |
