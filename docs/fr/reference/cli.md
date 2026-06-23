# Référence CLI

> 🌐 **Langues :** [English](../../en/reference/cli.md) · [简体中文](../../zh-CN/reference/cli.md) · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · [Español](../../es/reference/cli.md) · **Français** · [Italiano](../../it/reference/cli.md) · [Português (BR)](../../pt-BR/reference/cli.md) · [Português (PT)](../../pt-PT/reference/cli.md) · [Русский](../../ru/reference/cli.md) · [العربية](../../ar/reference/cli.md) · [हिन्दी](../../hi/reference/cli.md) · [বাংলা](../../bn/reference/cli.md) · [Tiếng Việt](../../vi/reference/cli.md)

Toutes les commandes, sous-commandes et options de Veles. Exécutez `veles <command> --help`
pour obtenir la signature de référence, toujours à jour — cette page reflète les
analyseurs d'arguments de `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — ignore l'assistant de configuration initiale même si `~/.veles/config.toml`
  est absent (conditionné aussi par un TTY et par `VELES_NO_WIZARD=1`).
- Sans argument, `veles` lance la [TUI](tui.md) interactive.

La plupart des commandes d'agent acceptent les [options partagées de la boucle d'agent](#options-partagées-de-la-boucle-dagent)
ainsi que les [noms de fournisseurs](#noms-de-fournisseurs) listés en bas de page.

---

## Cycle de vie du projet

### `veles init [name]`
Crée un nouveau projet Veles dans le répertoire courant (un répertoire d'état `.veles/`
+ `AGENTS.md` + l'ossature de contenu du pack de mise en page choisi).

| Option | Défaut | Rôle |
|---|---|---|
| `name` (positionnel) | nom de base du cwd | Nom du projet |
| `--layout <name>` | `llm-wiki` | Pack de mise en page pour l'ossature de contenu (`llm-wiki`, `notes`, `bare`, ou un pack personnalisé issu de `~/.veles/layouts/`) |
| `--force` | désactivé | Recrée `.veles/` même s'il existe déjà |

### `veles schema {validate,edit,fix}`
Valide ou édite `AGENTS.md` (le fichier de contexte du projet).

- `validate` — vérifie la présence des sections H2 requises.
- `edit` — ouvre `AGENTS.md` dans `$EDITOR` (par défaut `vi`), valide à la fermeture.
- `fix` — ajoute interactivement les sections manquantes via un assistant LLM.

### `veles self-doc [refresh|show]`
Génère et affiche l'auto-documentation du projet (`wiki/self-doc/overview.md`).
`veles self-doc` seul affiche la page courante ; `refresh` la régénère.

### `veles doctor`
Lance des contrôles de santé sur l'état global de l'utilisateur et le projet actif.
Fonctionne avec ou sans projet actif.

| Option | Défaut | Rôle |
|---|---|---|
| `--json` | désactivé | Émet un rapport JSON |
| `--strict` | désactivé | Sort avec un code non nul au moindre avertissement (contrôle CI) |

### `veles export {full,template} <path>`
Empaquette le projet dans une archive `.tar.gz`. Voir [Sauvegarder et partager](../how-to/backup-and-share.md).

- `full <path>` — projet entier (`.veles/` + `AGENTS.md`), hors données éphémères d'exécution.
- `template <path>` — sous-ensemble assaini (schéma + skills + modules + pages wiki
  hors session) ; supprime `memory.db`, `sources/`, `sessions/`, les octrois `trust`,
  et caviarde les informations personnelles du texte.

### `veles import <path>`
Restaure une archive créée par `veles export`.

| Option | Défaut | Rôle |
|---|---|---|
| `path` (positionnel) | — | Chemin de l'archive (`.tar.gz`) |
| `--into <dir>` | cwd | Répertoire cible |
| `--force` | désactivé | Écrase un `.veles/` existant à la cible |

---

## Exécuter l'agent

### `veles run "<prompt>"`
Exécute un prompt unique de bout en bout, avec persistance de la mémoire et les
déclencheurs du curateur / d'apprentissage. Accepte toutes les [options partagées de la boucle d'agent](#options-partagées-de-la-boucle-dagent) ainsi que :

| Option | Défaut | Rôle |
|---|---|---|
| `--resume <session_id>` | nouvelle session | Poursuit une session existante |
| `--manager` | désactivé | Décompose via le gestionnaire multi-agent (aussi `VELES_MANAGER_MODE=1`) |
| `--verify` | désactivé | Après l'exécution, l'advisor routé juge la réponse ; en cas d'échec avéré, relance sur le modèle plus puissant (aussi `VELES_VERIFY_MODE=1`) |
| `--plan` | désactivé | Mode planification : lecture/recherche/brouillon autorisés, mutations bloquées |
| `--no-agents-md` | désactivé | N'injecte pas `AGENTS.md` dans le prompt système |
| `--no-index` | désactivé | N'injecte pas `wiki/INDEX.md` |
| `--no-compress` | désactivé | Désactive la compression de contexte par fenêtre glissante |
| `--no-curator` | désactivé | Désactive les déclencheurs du curateur pour cette exécution |
| `--no-insights` | désactivé | Désactive l'extraction d'insights après exécution |
| `--no-proposer` | désactivé | Désactive le déclenchement auto du proposeur de sous-projets |
| `--no-route-refresh` | désactivé | Désactive le rafraîchissement du routage NL depuis `AGENTS.md` |
| `--no-suggest-promote` | désactivé | Désactive le suggéreur de promotion automatique |
| `--compressor-model <id>` | routé | Surcharge le modèle de compression |
| `--compress-threshold-tokens <n>` | `50000` | Taille d'historique déclenchant la compression |

### `veles tui`
Ouvre le REPL interactif. Voir [référence de la TUI](tui.md). Accepte les options
partagées de la boucle d'agent, `--resume`, les options `--no-*` d'injection/compression
ci-dessus, et :

| Option | Défaut | Rôle |
|---|---|---|
| `--theme <name>` | config ou `everforest` | Thème de couleurs (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
Lit une source (un fichier local ou une URL `http(s)://`) et la synthétise en une page
wiki. Accepte les options partagées de la boucle d'agent.

### `veles curate`
Lance une passe du curateur : compacte les sessions non traitées en pages `wiki/sessions/`.

| Option | Défaut | Rôle |
|---|---|---|
| `--limit <n>` | petite valeur par défaut | Nombre max de sessions traitées par exécution |

Plus les options partagées de la boucle d'agent.

### `veles research "<question>"`
Recherche approfondie : décompose en sous-questions → explore le web en parallèle →
synthétise un rapport sourcé.

| Option | Défaut | Rôle |
|---|---|---|
| `--max-subquestions <n>` | `4` | Angles de recherche menés en parallèle |

Plus les options partagées de la boucle d'agent.

### `veles dream`
Lance un cycle de consolidation mémoire en arrière-plan (insights → déduplication des
skills → suggestions de promotion → lint du wiki, et éventuellement consolidation par LLM).

| Option | Défaut | Rôle |
|---|---|---|
| `--include-consolidation` | désactivé | Lance la consolidation par LLM (coûteuse, nécessite une clé API) |
| `--dry-run` | désactivé | Exécute toutes les étapes mais saute les écritures dans `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | désactivé | Saute des étapes individuelles |
| `--consolidation-model <id>` | routé (repli sur `anthropic/claude-haiku-4.5`) | Surcharge le modèle de consolidation |
| `--provider <name>` | routé | Fournisseur du sous-agent de consolidation (omettre pour utiliser le fournisseur routé du projet) |
| `--project-root <path>` | détection | Surcharge du projet |

---

## Connaissance : skills, outils, modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Sous-commande | Rôle |
|---|---|
| `list` | Liste les skills du projet actif (avec télémétrie) |
| `show <name>` | Affiche le `SKILL.md` d'un skill |
| `add <source> [--name N] [--scope project\|user] [-y]` | Installe depuis une URL git ou un chemin local |
| `remove <name> [--scope project\|user] [-y]` | Supprime un skill installé |
| `promote <name> [--keep-telemetry]` | Copie un skill projet vers la portée utilisateur (`~/.veles/skills/`) |
| `demote <name> [-y]` | Copie un skill utilisateur dans le projet actif |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Détecte les skills quasi-doublons |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | Liste les skills qui atteignent le seuil de promotion automatique |

### `veles tool {list,show,promote}`

| Sous-commande | Rôle |
|---|---|
| `list` | Liste les outils catalogués dans le `memory.db` de ce projet |
| `show <name>` | Affiche le manifeste + la télémétrie d'un outil |
| `promote <name> [-y]` | Déplace un outil projet vers `~/.veles/tools/` (inter-projets) |

### `veles module {list,show,add,remove}`

| Sous-commande | Rôle |
|---|---|
| `list` | Liste les modules installés |
| `show <name>` | Affiche le manifeste d'un module |
| `add <source> [--name N] [-y]` | Installe un module depuis une URL git ou un chemin local |
| `remove <name> [-y]` | Supprime un module installé |

### `veles browse {modules,skills} [query]`
Parcourt les registres curatés.

| Option | Défaut | Rôle |
|---|---|---|
| `query` (positionnel) | `""` | Filtre par sous-chaîne |
| `--source <url>` | canonique | Surcharge la source du registre |
| `--json` | désactivé | Émet du JSON |

---

## Sessions et mémoire

### `veles sessions {list,show,delete,search}`

| Sous-commande | Rôle |
|---|---|
| `list [--limit n]` | Liste les sessions récentes (20 par défaut) |
| `show <session_id>` | Affiche l'historique complet des tours d'une session |
| `delete <session_id>` | Supprime une session et ses tours |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Recherche plein texte (FTS5) sur le contenu des tours |

---

## Multi-projets

### `veles project {list,add,remove,switch}`

| Sous-commande | Rôle |
|---|---|
| `list` | Liste les projets enregistrés, le plus récent en premier |
| `add <path> [--slug S]` | Enregistre un répertoire de projet existant |
| `remove <slug>` | Désenregistre un projet (fichiers intacts) |
| `switch <slug>` | Affiche le chemin absolu du projet (utilisez `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Sous-commande | Rôle |
|---|---|
| `init <subdir> [--name N] [--description D]` | Crée + enregistre un sous-projet |
| `list` | Liste les sous-projets du projet actif |
| `switch <slug>` | Affiche le chemin absolu d'un sous-projet |
| `remove <slug>` | Désenregistre un sous-projet |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Détecte des clusters thématiques et propose des sous-projets |

---

## Routage et modèles

### `veles route {show,set,reset,refresh}`
Routage par ensemble selon la tâche — quel `provider:model` traite chaque type de tâche
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`). Voir [routage par tâche](../how-to/per-task-routing.md).

| Sous-commande | Rôle |
|---|---|
| `show` | Affiche la table de routage résolue pour le projet actif |
| `set <task> <provider:model>` | Fixe une tâche sur une spécification |
| `reset [task]` | Réinitialise une tâche (ou toutes) aux valeurs par défaut |
| `refresh [--force]` | Ré-analyse les indices de routage en langage naturel depuis `AGENTS.md` |

### `veles models <provider>`
Liste les modèles d'un fournisseur. Les fournisseurs cloud (openrouter/openai/gemini)
sont mis en cache 24 h ; les fournisseurs locaux sont toujours en direct.

| Option | Défaut | Rôle |
|---|---|---|
| `provider` (positionnel) | — | L'un des [noms de fournisseurs](#noms-de-fournisseurs) |
| `--refresh` | désactivé | Contourne le cache disque (cloud uniquement) |
| `--json` | désactivé | Émet `{provider, source, models}` en JSON |

---

## Tâches de longue durée

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Objectifs à long horizon, avec budgets et points de contrôle.

| Sous-commande | Rôle |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | Liste les objectifs |
| `show <id> [--json]` | Affiche un objectif |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | Crée un objectif |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | Ajoute une avancée |
| `pause <id>` / `resume <id>` | Suspend / reprend |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Termine / annule |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Tâches d'agent planifiées.

| Sous-commande | Rôle |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | Crée une tâche (schedule = cron, `<N><s\|m\|h\|d>`, ou horodatage ISO) |
| `list [--json]` / `show <id>` | Inspecte les tâches |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Cycle de vie |
| `history <id> [--limit n]` | Exécutions récentes |
| `tick` | Exécute de façon synchrone toutes les tâches dues, une fois (aucun daemon requis ; accepte les options de la boucle d'agent) |

---

## Sécurité et contrôle d'accès

### `veles trust {list,set,revoke,clear}`
Octrois persistants pour les outils sensibles (`run_shell`, `write_file`, `fetch_url`, …).
Voir [sécurité](../how-to/security-and-permissions.md).

| Sous-commande | Rôle |
|---|---|
| `list` | Affiche les octrois (portées utilisateur + projet) |
| `set <tool> [--scope project\|user]` | Octroie un outil |
| `revoke <tool> [--scope project\|user\|both]` | Retire un octroi |
| `clear [--scope project\|user\|all]` | Efface les octrois d'une portée |

### `veles autopilot {enable,disable,status}`
Une fenêtre temporelle pendant laquelle les invites de l'échelle de confiance s'autorisent
automatiquement.

| Sous-commande | Rôle |
|---|---|
| `enable --until <DUR>` | Ouvre une fenêtre (`+30m`, `+2h`, `+1d`, ou ISO `2026-05-12T18:00:00Z`) |
| `disable` | Ferme la fenêtre immédiatement |
| `status` | Indique si l'autopilote est actif |

### `veles secret {set,get,list,delete}`
Secrets adossés au trousseau de l'OS (clés API, jetons de bot).

| Sous-commande | Rôle |
|---|---|
| `set <name> [value]` | Stocke (omettez la valeur pour saisie interactive / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Recherche (repli sur les variables d'env par défaut) |
| `list` | Affiche quels secrets canoniques sont configurés |
| `delete <name>` | Supprime un secret |

---

## Daemon et canaux

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Lance/contrôle le daemon HTTP+WS. `veles daemon` seul ouvre le **sélecteur de daemon**
en TUI (projet → daemons → canaux). Voir [exécuter en daemon](../how-to/run-as-daemon.md).

| Sous-commande | Rôle |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Démarre un daemon (se détache par défaut) |
| `stop [--name N]` / `status [--name N]` | Arrête / inspecte |
| `list` | Liste les daemons de tous les projets |
| `restart [target] [--name N]` | Arrête + relance sur le même hôte/port |
| `delete <target> [-y]` | Arrête + retire du registre |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Déclare une session de daemon nommée |
| `session list [--all]` / `session delete <name>` | Gère les sessions nommées |
| `token add <name>` / `token list` / `token remove <name>` | CRUD des jetons Bearer |

`start` accepte aussi les options partagées de la boucle d'agent ; pour le daemon,
`--model` / `--provider` ont pour valeur par défaut la config du projet et sont fixés
pour toute la durée de vie du daemon.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
Passerelles de chat externes (Telegram, …) qui dialoguent avec un daemon. Voir
[connecter Telegram](../how-to/connect-telegram.md).

| Sous-commande | Rôle |
|---|---|
| `list` | Liste les plateformes de canaux enregistrées + le nombre de sessions |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | Démarre une passerelle au premier plan |
| `list-sessions [--channel C]` | Affiche les correspondances `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | Oublie une correspondance (le prochain message repart de zéro) |
| `add [--channel C] [--session S]` | Rattache un canal à un daemon (assistant ; identifiants → trousseau) |
| `remove <channel> [--session S]` | Retire une liaison de canal |

---

## MCP (serveurs d'outils externes)

### `veles mcp {list,test}`
Inspecte les serveurs MCP externes configurés sous `[mcp.servers.*]`. Voir
[serveurs MCP externes](../how-to/external-mcp-servers.md).

| Sous-commande | Rôle |
|---|---|
| `list [--connect-timeout f]` | Affiche les serveurs configurés, l'état de connexion, le nombre d'outils |
| `test <server>` | Se connecte à un serveur et liste ses outils |

---

## Options partagées de la boucle d'agent

Acceptées par `run`, `add`, `tui`, `curate`, `research`, `job tick`, et `daemon start` :

| Option | Défaut | Rôle |
|---|---|---|
| `--model <id>` | résolu depuis le modèle `[provider]` du projet → `default_model` utilisateur (aucun défaut codé en dur) | ID du modèle |
| `--provider <name>` | `openrouter` | Fournisseur (voir ci-dessous) |
| `--max-tokens-total <n>` | `100000` | Budget cumulé de tokens ; `0` le désactive |
| `--max-iterations <n>` | `30` | Nombre max d'itérations d'appel d'outils par tour |
| `--stream` | désactivé | Diffuse la réponse token par token |
| `--verbose` / `-v` | désactivé | Progression par tour vers stderr |
| `--project-root <path>` | détection depuis le cwd | Opère sur un projet situé ailleurs |

## Noms de fournisseurs

`openrouter` (par défaut) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Les fournisseurs locaux (`ollama`, `llamacpp`, `openai-compat`) ne nécessitent aucune
clé API. Voir la [référence des fournisseurs](providers.md) et [configurer les fournisseurs](../how-to/configure-providers.md).
