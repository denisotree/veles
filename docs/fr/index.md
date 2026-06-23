# Documentation de Veles

> 🌐 **Langues :** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · **Français** · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles est un framework d'agent CLI minimaliste, pensé pour le local d'abord. Vous le
pointez vers un répertoire de projet ; il tient une **mémoire de projet** structurée,
**apprend** de vos sessions, fait tourner n'importe quel fournisseur LLM (cloud ou
local) et accumule des **skills** et des **outils** réutilisables au fil de son travail.

Cette documentation suit le modèle [Diátaxis](https://diataxis.fr/). Choisissez le
quadrant qui correspond à ce dont vous avez besoin maintenant.

## Commencez ici

Si vous n'avez jamais lancé Veles, faites les deux tutoriels dans l'ordre :

1. **[Premiers pas](tutorials/getting-started.md)** — installer Veles, configurer une
   clé d'API, créer votre premier projet et lancer votre premier prompt.
2. **[Construire une base de connaissances](tutorials/building-a-knowledge-base.md)** —
   ingérer des sources dans le LLM-Wiki, poser des questions et consolider les sessions.

## Tutoriels — apprendre en faisant

- [Premiers pas](tutorials/getting-started.md)
- [Construire une base de connaissances](tutorials/building-a-knowledge-base.md)

## Guides pratiques — accomplir une tâche

- [Configurer les fournisseurs (cloud et local)](how-to/configure-providers.md)
- [Router différentes tâches vers différents modèles](how-to/per-task-routing.md)
- [Lancer Veles en tant que daemon](how-to/run-as-daemon.md)
- [Connecter un canal Telegram](how-to/connect-telegram.md)
- [Gérer les skills, outils et modules](how-to/manage-skills-and-tools.md)
- [Travailler avec plusieurs projets et sous-projets](how-to/multi-project-and-subprojects.md)
- [Sécurité : confiance, autopilote, secrets](how-to/security-and-permissions.md)
- [Tâches de longue durée : objectifs, jobs, rêve, recherche](how-to/long-running-tasks.md)
- [Connecter des serveurs MCP externes](how-to/external-mcp-servers.md)
- [Sauvegarder et partager un projet](how-to/backup-and-share.md)

## Référence — consulter

- [Référence des commandes CLI](reference/cli.md)
- [Configuration (`config.toml`)](reference/configuration.md)
- [Variables d'environnement](reference/environment-variables.md)
- [Fournisseurs](reference/providers.md)
- [Raccourcis clavier et commandes slash de la TUI](reference/tui.md)
- [Mise en page et état du projet](reference/project-layout.md)

## Explication — comprendre la conception

- [Vue d'ensemble de l'architecture](explanation/architecture.md)
- [Mémoire de projet et boucle d'apprentissage](explanation/project-memory-and-learning-loop.md)
- [Skills et outils, une capacité qui s'accumule](explanation/skills-and-tools.md)
- [Modes d'exécution](explanation/modes.md)
- [Orchestration multi-agents](explanation/multi-agent-orchestration.md)
- [Packs de mise en page et le LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Confiance et bac à sable](explanation/trust-and-sandbox.md)

---

Pour la vision produit et les justifications de conception, voir `VISION.md` (à la racine
du dépôt) ; pour l'historique complet de l'implémentation, voir `MILESTONES.md`. Ces
documents s'adressent aux développeurs — cette documentation, elle, vise à **utiliser**
Veles.
