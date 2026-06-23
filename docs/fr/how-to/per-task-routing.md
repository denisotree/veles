# Comment router les tâches vers différents modèles

> 🌐 **Langues :** [English](../../en/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md)

Veles n'est pas figé sur un seul modèle. Chaque **tâche** interne peut utiliser un
`provider:model` différent — un modèle économique pour la compression du contexte,
un modèle puissant pour l'agent principal, un modèle de vision pour les images.
C'est le système de *routage d'ensemble*.

## Types de tâches

| Tâche | Utilisée pour |
|---|---|
| `default` | La boucle de l'agent principal |
| `curator` | Consolidation session → wiki |
| `compressor` | Compression du contexte par fenêtre glissante |
| `insights` | Extraction d'insights après exécution |
| `skills` | Exécution des compétences |
| `advisor` | L'auto-vérification `advisor_review` |
| `vision` | `image_describe` (quand un adaptateur de vision est branché) |
| `embedding` | Similarité de `veles skill dedup` |

## Voir le routage actuel

```bash
veles route show
```

Cette commande affiche le `provider:model` résolu pour chaque tâche ainsi qu'une
étiquette `source` indiquant quelle couche l'a décidé.

## Épingler une tâche à un modèle

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Ces commandes écrivent `[routing.tasks]` dans `<project>/.veles/config.toml` :

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Réinitialiser

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Indications en langage naturel dans AGENTS.md

Vous pouvez exprimer le routage en prose dans `AGENTS.md` (par ex. « utiliser un
modèle économique pour la compression »). Veles analyse ces indications dans un
`routing.nl.toml` généré automatiquement :

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Les entrées explicites `[routing.tasks]` l'emportent toujours sur les indications
en langage naturel.

## Ordre de résolution

Pour chaque tâche, la première couche qui produit une spécification l'emporte :

1. `[routing.tasks][task]` du projet
2. `[routing.tasks].default` du projet
3. indication NL du projet (`routing.nl.toml`)
4. base `[provider]` du projet
5. `[routing.tasks][task]` / `.default` de l'utilisateur
6. `[user] default_provider` + `default_model` de l'utilisateur
7. valeur par défaut intégrée pour cette tâche

(`embedding` ignore les couches fourre-tout — un modèle de chat n'est pas un modèle
d'embedding.)
