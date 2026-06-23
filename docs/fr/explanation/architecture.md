# Vue d'ensemble de l'architecture

> 🌐 **Langues :** [English](../../en/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md)

Cette page explique ce qu'*est* Veles et comment ses composants s'articulent, afin que
le reste de la documentation prenne tout son sens. Pour la vision produit faisant
autorité, voir `VISION.md` à la racine du dépôt.

## L'intention de conception

Veles est délibérément **minimaliste et proprement décomposé** — des modules à
responsabilité unique, pas de fichiers fourre-tout. Il fonctionne **en local d'abord** :
vous le lancez contre un répertoire de votre machine, et il y conserve sa propre mémoire
structurée.

## Les cinq piliers (le cœur)

Tout ce qui constitue le cœur sert l'une de ces cinq missions :

1. **La mémoire de projet** — un artefact structuré (distinct de votre contenu) qui
   contient le journal de session, les règles/insights appris, une carte des fichiers du
   projet et les registres de skills/outils avec leur télémétrie. Voir
   [mémoire de projet et boucle d'apprentissage](project-memory-and-learning-loop.md).
2. **La boucle d'apprentissage** — le curateur, l'extracteur d'insights et le rêve, qui
   maintiennent la mémoire à jour et transforment l'expérience en règles réutilisables.
3. **L'orchestration multi-agents** — un manager qui décompose une tâche et fait
   apparaître des workers spécialisés. Voir
   [orchestration multi-agents](multi-agent-orchestration.md).
4. **Un protocole de fournisseur** — une interface unique au-dessus de nombreux backends
   LLM (cloud, local, délégation CLI). Voir [fournisseurs](../reference/providers.md).
5. **Des outils et skills minimaux** — un petit jeu d'amorçage qui **s'accumule** à
   mesure que Veles écrit ses propres outils et formalise les processus récurrents en
   skills. Voir [skills et outils](skills-and-tools.md).

## Tout le reste est un module optionnel

Les passerelles/canaux, le daemon, le planificateur, la TUI, la vision/STT — tout cela
est **enfichable** et ne se charge qu'à l'usage. Veles démarre avec le minimum et
s'étend à la demande, si bien qu'un simple `veles run` reste simple.

## Comment s'enchaîne un tour

```
votre prompt
   │
   ▼
contexte : AGENTS.md (petit) + rappel à la demande depuis la mémoire de projet
   │
   ▼
boucle d'agent  ──►  fournisseur (routé par tâche)  ──►  appels d'outils
   │                                                      │
   │            (l'échelle de confiance encadre les outils sensibles)
   ▼
réponse  ──►  sauvegardée en mémoire  ──►  déclencheurs d'apprentissage (insights, curateur)
```

Le fichier de contexte (`AGENTS.md`) est volontairement maintenu petit ; les
connaissances auxiliaires (pages de wiki, carte des fichiers du projet, tours passés
pertinents) sont rappelées **à la demande** plutôt que déversées d'emblée.

## Où réside l'état

- `<project>/.veles/` — la mémoire, la configuration et les skills/outils locaux de ce projet.
- `~/.veles/` — la configuration globale utilisateur, les skills/outils inter-projets, les caches, la confiance.
- `<project>/AGENTS.md`, `wiki/`, `sources/` — votre contenu (la disposition LLM-Wiki).

Voir [disposition du projet](../reference/project-layout.md).

## Le multi-projet dans une seule boucle

Une seule boucle d'agent sert plusieurs projets. Chaque projet a son propre répertoire
avec son contexte et sa mémoire ; `AGENTS.md` est lié par symlink à `CLAUDE.md`/`GEMINI.md`
afin qu'un CLI externe lancé là-bas voie le même contexte. Voir
[plusieurs projets](../how-to/multi-project-and-subprojects.md).

## Les surfaces

- **CLI** (`veles run`, `veles add`, …) — usage ponctuel et scripté.
- **TUI** (`veles tui`) — REPL interactif avec des [modes d'exécution](modes.md).
- **Daemon + canaux** — API headless, Telegram, jobs planifiés.

Toutes trois pilotent la même boucle d'agent au cœur.
