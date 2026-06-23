# Construire une base de connaissances

> 🌐 **Langues :** **English** · [Русский](../../ru/tutorials/building-a-knowledge-base.md)

Dans ce tutoriel, vous transformez un projet Veles en une base de connaissances
vivante : vous y intégrez quelques sources, laissez Veles rédiger des pages wiki,
posez des questions, puis consolidez ce que vous avez appris. C'est le workflow
**LLM-Wiki** par défaut. Environ 15 minutes.

Vous devriez avoir terminé [Premiers pas](getting-started.md) au préalable.

## L'idée

Un projet Veles comporte deux zones de contenu :

- `sources/` — le matériau brut et immuable que vous lui fournissez (en lecture
  seule pour l'agent).
- `wiki/` — les connaissances propres à l'agent, générées par le LLM (la seule
  zone dans laquelle il écrit du contenu).

Vous y injectez des sources ; Veles les distille en pages wiki interconnectées ;
vous interrogez le wiki en langage naturel. Voir [packs de layout & le LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)
pour comprendre pourquoi.

## 1. Intégrer une source

`veles add` lit un fichier ou une URL et écrit une page wiki qui la résume :

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

Chaque `add` produit une page sous `wiki/` et la relie au graphe du wiki.

## 2. Regarder le wiki grandir

Observez ce qui a été écrit :

```bash
ls wiki/concepts wiki/entities wiki/sources
```

Les pages se référencent mutuellement. Le catalogue `wiki/INDEX.md`, chargé à la
demande, tient à jour une carte que l'agent charge lorsqu'il en a besoin (et non
un dump de contexte monolithique).

## 3. Poser des questions

Interrogez désormais votre base de connaissances en langage naturel :

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles parcourt le wiki, lit les pages pertinentes et répond — en s'appuyant sur
ce que vous avez intégré plutôt que sur ses seules données d'entraînement.

Pour un échange interactif, faites de même dans le TUI (`veles tui`).

## 4. Consolider les sessions

Au fil de votre travail, les conversations s'accumulent. Lancez le curateur pour
les compacter en pages wiki durables et en extraire des enseignements :

```bash
veles curate
```

Cela écrit des pages dans `wiki/sessions/` et met à jour les insights et les
règles du projet. Veles le fait aussi automatiquement au fil du temps — voir
[mémoire du projet & la boucle d'apprentissage](../explanation/project-memory-and-learning-loop.md).

## 5. Garder le wiki en bonne santé

Avec le temps, des pages deviennent obsolètes ou orphelines. L'opération `lint`
les repère :

```bash
veles run "lint"
```

(`ingest`, `query` et `lint` sont des skills livrés avec le layout LLM-Wiki ; vous
les invoquez avec `veles run "<operation>"` ou laissez l'agent les appeler.)

## Ce que vous avez construit

Une base de connaissances auto-organisée : des sources en entrée, des pages wiki
interconnectées en sortie, interrogeable en langage naturel, et qui s'ordonne à
mesure que Veles consolide. À partir d'ici :

- **[Gérer skills, outils et modules](../how-to/manage-skills-and-tools.md)** —
  apprenez à Veles des workflows réutilisables.
- **[Exécuter en tant que daemon](../how-to/run-as-daemon.md)** + **[connecter Telegram](../how-to/connect-telegram.md)** —
  dialoguez avec votre base de connaissances depuis votre téléphone.
- **[Projets et sous-projets multiples](../how-to/multi-project-and-subprojects.md)** —
  passez à l'échelle avec de nombreuses bases de connaissances.
