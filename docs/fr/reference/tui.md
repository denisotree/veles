# Raccourcis clavier & commandes slash de la TUI

> 🌐 **Langues :** **English** · [Русский](../../ru/reference/tui.md)

`veles tui` (ou simplement `veles`) ouvre le REPL interactif. C'est un chat avec
historique défilant, doté d'un composeur multi-lignes, d'une barre d'état et d'un
inspecteur repliable.

## Raccourcis clavier

| Touche | Action |
|---|---|
| `Ctrl+D` | Quitter |
| `Ctrl+C` | Copier la dernière réponse de l'assistant ; appuyer deux fois en 1,5 s pour quitter |
| `Ctrl+V` | Coller depuis le presse-papiers |
| `Ctrl+Shift+C` / `⌘C` | Copier la sélection courante (OSC52). Sur Terminal.app (macOS), la sélection native par glisser + ⌘C fonctionne directement |
| `Ctrl+I` | Afficher/masquer l'inspecteur (raisonnement, activité des outils, journal des tokens/erreurs) |
| `Ctrl+R` | Ouvrir le sélecteur de session (reprendre une session passée) |
| `Ctrl+T` | Ouvrir le sélecteur de thème |
| `Shift+Tab` | Faire défiler le mode d'exécution : `auto → planning → writing → goal` |
| `Tab` | Faire défiler les complétions de commandes slash |
| `Up` / `Down` | Historique (et dépiler les prompts en file d'attente) |

Les modes d'exécution sont expliqués dans [Modes d'exécution](../explanation/modes.md).

## Commandes slash

Tapez `/` dans le composeur ; `Tab` complète. Les commandes enregistrées sont :

| Commande | Rôle |
|---|---|
| `/help` | Lister les commandes disponibles |
| `/quit`, `/q`, `/exit` | Quitter le REPL |
| `/clear` | Effacer le journal du chat |
| `/model` | Ouvrir le sélecteur de modèle |
| `/mode` | Changer de mode d'exécution (auto/planning/writing/goal) |
| `/session` | Ouvrir le sélecteur de session (reprise) |
| `/save` | Enregistrer / nommer la session courante |
| `/history` | Afficher l'historique des sessions |
| `/tokens` | Consommation de tokens (entrée / sortie / par tour / par session) |
| `/context` | Taille du contexte courant par rapport à la limite |
| `/status` | Aperçu : modèle, fournisseur, mode, session, occupation, file d'attente |
| `/insights` | Afficher les insights appris pour le projet |
| `/rules` | Afficher le condensé des règles du projet |
| `/schema` | Valider / corriger `AGENTS.md` |
| `/wiki` | Opérations wiki pour la disposition active |
| `/daemon` | Ouvrir le panneau de contrôle du daemon (projet → daemons → canaux) |

> L'ensemble des commandes slash est le même que vous lanciez la TUI directement ou
> que vous la poussiez depuis un autre écran. Les canaux (par ex. Telegram) exposent
> leur propre ensemble de commandes, distinct.

## Thèmes

Thèmes intégrés : `everforest` (par défaut), `dracula`, `gruvbox`, `tokyo-night`,
`catppuccin`. Choisissez-en un avec `Ctrl+T`, `veles tui --theme <name>`, ou
`[user] tui_theme` dans `~/.veles/config.toml`.
