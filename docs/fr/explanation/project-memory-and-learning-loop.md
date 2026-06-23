# Mémoire de projet et la boucle d'apprentissage

> 🌐 **Langues :** [English](../../en/explanation/project-memory-and-learning-loop.md) · [简体中文](../../zh-CN/explanation/project-memory-and-learning-loop.md) · [繁體中文](../../zh-TW/explanation/project-memory-and-learning-loop.md) · [日本語](../../ja/explanation/project-memory-and-learning-loop.md) · [한국어](../../ko/explanation/project-memory-and-learning-loop.md) · [Español](../../es/explanation/project-memory-and-learning-loop.md) · **Français** · [Italiano](../../it/explanation/project-memory-and-learning-loop.md) · [Português (BR)](../../pt-BR/explanation/project-memory-and-learning-loop.md) · [Português (PT)](../../pt-PT/explanation/project-memory-and-learning-loop.md) · [Русский](../../ru/explanation/project-memory-and-learning-loop.md) · [العربية](../../ar/explanation/project-memory-and-learning-loop.md) · [हिन्दी](../../hi/explanation/project-memory-and-learning-loop.md) · [বাংলা](../../bn/explanation/project-memory-and-learning-loop.md) · [Tiếng Việt](../../vi/explanation/project-memory-and-learning-loop.md)

Le trait distinctif de Veles est qu'il **se souvient** et **apprend** par projet. Cette page
explique ce qu'est cette mémoire et comment la boucle d'apprentissage la maintient utile.

## La mémoire est un artefact structuré

La mémoire de projet réside dans `<project>/.veles/` — `memory.db` (SQLite, la source de
vérité) plus une arborescence `.veles/memory/` lisible par l'humain (vues d'insights rendues,
condensés de session, propositions, un journal des opérations système). Elle est **distincte
de votre contenu** et fonctionne à l'identique sous n'importe quelle mise en page (wiki, notes
ou bare). Ce n'est pas une décharge de transcription de chat — c'est un ensemble de couches
structurées :

- **Journal de session** — chaque conversation, une ligne par tour, indexée en texte intégral.
- **Règles** — de courts impératifs que l'agent doit suivre (`format`, `do`, `don't`,
  `preference`), injectés dans l'invite système stable.
- **Insights** — des leçons distillées à partir des sessions. La ligne SQL fait foi (le
  rappel, le vieillissement et la déduplication opèrent dessus) ; une vue markdown est rendue
  dans `.veles/memory/insights/` pour les humains et les exports.
- **Carte de l'arborescence du projet** — une carte de fichiers mise en cache et étiquetée
  sémantiquement, afin que l'agent lise les 3 à 5 fichiers pertinents et non toute
  l'arborescence.
- **Registres de skills et d'outils** — avec leur télémétrie (compteurs
  d'utilisation/succès/erreur) que le classement et la déduplication exploitent.

Voir la liste des tables dans
[mise en page du projet](../reference/project-layout.md#project-memory-velesmemorydb).

## Rappel : un contexte réduit, tiré à la demande

`AGENTS.md` est délibérément réduit. Quand vous posez une question, Veles ne tire que ce qui
est pertinent : les tours passés correspondants (texte intégral + reranking vectoriel
optionnel), les règles et insights applicables, et les fichiers que la carte de l'arborescence
classe le plus haut. Cela garde chaque appel au modèle ciblé et économique au lieu de tout
déverser.

## La boucle d'apprentissage

L'expérience devient connaissance durable via trois mécanismes :

### Insights — capturer les leçons
Après une exécution, un extracteur cherche ce qui mérite d'être retenu : les retours explicites
« remember X » / « never Y », et les schémas erreur-d'outil→récupération (un échec suivi d'un
correctif). Il les distille en insights et en règles afin que la même erreur ne se reproduise
pas.

### Curateur — consolider les sessions
Le curateur distille les sessions plus anciennes en mémoire durable : toujours des insights et
des règles SQL ; et en plus une page `wiki/sessions/` lorsque la mise en page du projet active
le moteur wiki. Il s'exécute sur des minuteurs d'inactivité / d'après-tour, ou à la demande
avec `veles curate`.

### Dreaming — maintenance en arrière-plan
`veles dream` (et le daemon lorsqu'il est inactif) extrait des insights, déduplique les
skills et les insights, suggère des promotions et (sous une mise en page wiki) effectue le
lint du wiki — gardant la mémoire fraîche sans vous bloquer. Ajoutez `--include-consolidation`
pour une passe LLM plus approfondie.

## Compression du contexte

Les longues conversations sont maintenues sous la limite de contexte du modèle par un
compresseur à fenêtre glissante : lorsque l'historique en mémoire franchit un seuil de jetons,
le milieu est résumé (par un modèle routé peu coûteux) et remplacé par un pointeur vers le
résumé sauvegardé dans `.veles/memory/sessions/`. L'historique complet demeure toujours dans
`memory.db` — seule la fenêtre en mémoire est compressée, donc c'est sans perte sur disque.

## Pourquoi c'est important

Parce que la mémoire est structurée et que la boucle s'exécute en continu, un projet Veles
devient **d'autant plus utile que vous l'utilisez** — il apprend vos conventions, évite les
erreurs répétées et ancre ses réponses dans ce qu'il a réellement vu.
