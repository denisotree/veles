# Comment travailler avec plusieurs projets et sous-projets

> 🌐 **Langues :** [English](../../en/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md)

Veles fait tourner de nombreux projets dans une seule boucle d'agent. Chaque
projet a sa propre mémoire, ses compétences et ses outils. Les **sous-projets**
sont des projets imbriqués sous un parent — utiles pour décomposer un grand
monorepo ou une base de connaissances en mémoires cloisonnées.

## Projets

Veles découvre le projet actif en remontant depuis votre répertoire courant
jusqu'à un répertoire `.veles/` (comme `git`). Gérez le registre :

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` affiche un chemin, ce qui vous permet de faire un `cd` dans un projet :

```bash
cd "$(veles project switch web)"
```

Exécutez une commande sur un projet situé ailleurs sans faire de `cd` :

```bash
veles run --project-root /path/to/project "..."
```

## Sous-projets

Un sous-projet est un projet Veles enfant à l'intérieur d'un parent. Pour en
créer un :

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Laisser Veles suggérer une découpe

Lorsque le wiki d'un projet grandit, Veles peut détecter des regroupements
thématiques et les proposer comme sous-projets :

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## Lequel utiliser et quand

- **Projets séparés** — bases de connaissances / bases de code sans rapport entre
  elles.
- **Sous-projets** — des parties d'un ensemble plus vaste qui profitent d'une
  mémoire cloisonnée tout en partageant un contexte parent.

Voir l'[architecture](../explanation/architecture.md) pour comprendre comment le
contexte multi-projets se charge à la demande plutôt que comme un unique vidage
monolithique.
