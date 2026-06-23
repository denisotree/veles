# Modes d'exécution

> 🌐 **Langues :** **English** · [Русский](../../ru/explanation/modes.md)

Dans la TUI, chaque invite est traitée par un **mode d'exécution** — une stratégie qui
décide du degré d'autonomie et de l'ensemble d'outils dont dispose le tour. Faites défiler
les modes avec `Shift+Tab` ; l'ordre est `auto → planning → writing → goal`.

## Les quatre modes

### `writing` — chat direct
Le mode le plus simple : votre invite part vers l'agent avec la palette d'outils complète à
disposition, et il répond. Utilisez-le pour le travail courant où vous voulez que l'agent
agisse.

### `planning` — recherche en lecture seule + un plan
Les modifications sont bloquées (pas de `write_file`, pas de `run_shell`). L'agent utilise
les outils de lecture/recherche pour rassembler le contexte, puis produit un artefact de
plan structuré. Utilisez-le pour réfléchir avant de toucher à quoi que ce soit — ou passez
`--plan` à `veles run` pour obtenir le même effet en CLI.

### `auto` — routage intelligent (par défaut)
Une classification rapide détermine si votre invite est une demande directe ou si elle
appelle de la planification, puis l'aiguille vers `writing` ou `planning` en conséquence.
C'est le repli le plus intelligent quand vous n'avez pas exprimé d'intention, raison pour
laquelle c'est la première étape par défaut du cycle.

### `goal` — objectif à long horizon
Pilote une machine à états finis pour un objectif en plusieurs étapes : il vous interroge
pour clarifier, confirme un plan, exécute les étapes (avec des contrôles de l'advisor), et
vérifie la condition d'achèvement — le tout sous des budgets explicites. L'équivalent en CLI
est la famille de commandes
[`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints).

## Pourquoi les modes existent

Différentes requêtes appellent des degrés de prudence différents. Une question rapide ne
devrait pas exiger de cérémonie ; un changement risqué bénéficie d'une passe de planification
en lecture seule au préalable ; un objectif d'ampleur a besoin de budgets et de points de
contrôle. Les modes rendent ce choix explicite et commutable à chaque tour, au lieu de figer
un seul comportement pour toute la session.

Lorsque vous changez en cours de session, l'agent est informé des nouvelles règles, de sorte
que son comportement change immédiatement.
