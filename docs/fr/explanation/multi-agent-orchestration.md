# Orchestration multi-agents

> 🌐 **Langues :** **English** · [Русский](../../ru/explanation/multi-agent-orchestration.md)

Pour le travail complexe, Veles peut répartir une tâche entre un **manager** et des
sous-agents **worker** spécialisés au lieu de tout faire dans un seul contexte. Cette page
explique le modèle ; pour l'activer, voir
[le mode manager](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt).

## La forme

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- Le **manager** planifie la décomposition et coordonne — mais il n'écrit **pas** lui-même
  le livrable final.
- Les **workers** ont des invites système propres à leur rôle : `explorer` collecte,
  `writer` produit la réponse, `advisor` relit. L'ensemble est extensible.
- À la fin, le manager rédige un court rapport dans la mémoire.

## Pas de téléphone arabe

Une règle clé : les artefacts intermédiaires parviennent au synthétiseur **mot pour mot**,
et non comme une paraphrase du manager. Les trouvailles d'un explorer sont remises
directement au writer, de sorte qu'aucun détail ne se perd dans une chaîne de résumés. C'est
ce qui fait que la décomposition ajoute de la qualité au lieu de la diluer.

## Pourquoi « le manager n'écrit jamais »

Si le coordinateur écrivait aussi la réponse, il serait tenté de court-circuiter les workers
et de perdre le bénéfice de la spécialisation. Garder la synthèse dans un `writer` dédié
(alimenté par des entrées mot pour mot) impose la division du travail. Veles en fait une
garantie au moment de l'exécution.

## Quand cela aide — et quand cela n'aide pas

La décomposition est payante pour les tâches larges ou à multiples facettes (auditer ce
dépôt de code, étudier cette question sous plusieurs angles). Pour une requête rapide à
contexte unique, elle ne fait qu'ajouter du surcoût — raison pour laquelle le mode manager
est en **opt-in explicite**, désactivé par défaut (`veles run --manager` ou
`VELES_MANAGER_MODE=1`).
