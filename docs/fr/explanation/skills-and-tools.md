# Compétences et outils comme capacité cumulative

> 🌐 **Langues :** **English** · [Русский](../../ru/explanation/skills-and-tools.md)

Veles démarre avec un ensemble minimal d'outils et de compétences et le **fait grandir** au
fil de son travail. Cette page explique la différence entre les deux et la façon dont ils
s'accumulent. Pour les commandes, voir
[gérer les compétences et outils](../how-to/manage-skills-and-tools.md).

## Outils vs compétences

- Un **outil** est une action exécutable unique — lire un fichier, lancer une commande shell,
  récupérer une URL, chercher sur le web, écrire une page de wiki. Les outils sont ce que le
  modèle appelle.
- Une **compétence** est un *processus* formalisé — un `SKILL.md` avec un corps d'invite et
  une liste d'outils autorisés, exécuté comme un sous-agent ciblé. Les compétences composent
  des outils en un workflow reproductible (par ex. les `ingest`/`query`/`lint` du LLM-Wiki).

## Démarrage minimal, expansion à la demande

Veles s'amorce avec juste ce qu'il faut pour être utile, plus un endroit connu où en puiser
davantage. Installer des extras (une compétence, un outil, un module) demande une approbation
par défaut ; vous pouvez accorder une autonomie permanente. Cela garde un projet neuf léger
tout en laissant la capacité croître là où c'est nécessaire.

## Comment la capacité s'accumule

1. **Veles écrit ses propres outils.** Lorsqu'il repère une tâche récurrente, il peut rédiger
   un outil Python propre, typé et réutilisable dans `<project>/.veles/tools/` (avec une passe
   de revue de code par l'advisor). L'outil rejoint le registre avec sa télémétrie.
2. **Les processus récurrents deviennent des compétences.** Un détecteur de schémas repère les
   séquences d'outils récurrentes et propose de les formaliser en compétence ; une compétence
   peut faire `extends:` d'une autre compétence pour hériter de son corps et de ses outils.
3. **La télémétrie pilote le classement.** Chaque outil/compétence porte des compteurs
   d'utilisation/succès/erreur. Ils alimentent la déduplication (`veles skill dedup`) et les
   suggestions de promotion.

## Deux portées, avec promotion

Les outils comme les compétences existent à deux niveaux :

- **Local au projet** (`<project>/.veles/`) — visible uniquement ici.
- **Global à l'utilisateur** (`~/.veles/`) — disponible dans chaque projet.

Une capacité qui fait ses preuves dans un projet peut être **promue** vers la portée
utilisateur afin que tous les projets en bénéficient (`veles skill promote`,
`veles tool promote`), ou **rétrogradée**. C'est ainsi que Veles transporte d'un projet à
l'autre les workflows durement acquis.

## Pourquoi un registre, et pas seulement des fichiers

Stocker les compétences/outils sous forme de fichiers simples les garde inspectables et
modifiables ; stocker leur *télémétrie* dans `memory.db` permet à Veles de raisonner sur ceux
qui fonctionnent réellement. C'est cette combinaison qui transforme « un dossier de scripts »
en capacité cumulative et auto-curatée.
