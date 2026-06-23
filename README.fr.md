# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <b>Français</b> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**Un framework d'agent CLI minimaliste qui devient plus intelligent à chaque session.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="TUI Veles — posez une question, obtenez une réponse ancrée dans la mémoire propre du projet" width="800">
</p>

Contrairement aux outils de chat qui repartent de zéro à chaque fois, Veles entretient une **mémoire de projet structurée** — des enseignements, des règles et des connaissances curées qui s'accumulent au fil des sessions et rendent l'agent d'autant plus utile que vous l'utilisez longtemps. La façon dont votre *contenu* est organisé est modulable : un wiki LLM façon Karpathy par défaut, des notes à plat, ou aucune structure du tout pour les dépôts de code. Conçu proprement : pas de fichiers fourre-tout, pas de dépendance à un fournisseur, pas de synchronisation cloud.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (bare `veles` == `veles tui`)
```

---

## Pourquoi Veles ?

**Une mémoire cumulative** — Chaque session est distillée par le Curateur dans la mémoire propre à chaque projet (enseignements, règles comportementales, résumés de sessions dans `.veles/`). L'agent se remémore automatiquement les faits pertinents et les décisions passées — vous cessez de ré-expliquer le même contexte. La mémoire fonctionne sous *n'importe quelle* organisation de contenu.

**Des organisations de contenu modulables** — `veles init` échafaude par défaut un wiki LLM façon Karpathy ; `--layout notes` donne un répertoire de notes à plat ; `--layout bare` n'ajoute aucune structure (idéal pour les dépôts de code). Les packs d'organisation personnalisés tiennent dans un unique fichier TOML placé dans `~/.veles/layouts/`.

**Un routage indépendant du fournisseur** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp, ou votre abonnement CLI `claude`/`gemini`. Différents types de tâches (planification, compression, enseignements) peuvent être routés vers différents modèles.

**Des compétences qui s'accumulent** — Des blocs de prompt réutilisables deviennent des outils de l'agent. Promouvez une compétence d'un projet vers le niveau utilisateur global et elle devient disponible partout. La déduplication intégrée détecte les compétences quasi identiques avant qu'elles ne divergent.

**Local-first et bac à sable** — Pas de télémétrie, pas de synchronisation cloud. L'agent ne voit que le répertoire du projet actif. L'échelle de confiance demande l'autorisation à chaque appel d'outil sensible ; pré-accordez-la pour la CI.

**Modulaire, pas monolithique** — Un noyau minimal (mémoire, boucle d'agent, protocole de fournisseur, registre d'outils). Tout le reste — TUI, démon, passerelle Telegram, recherche approfondie, planificateur de tâches — est un module optionnel et chargeable.

---

## Démarrage rapide

**Prérequis :** Python 3.13+, macOS / Linux (Windows au mieux). Installez d'abord [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

Ouvrez plutôt le TUI interactif (le simple `veles` fait la même chose) :

```bash
veles
```

Au premier lancement, un assistant de configuration vous demandera votre langue préférée, votre fournisseur et le nom du projet.

---

## Fournisseurs

| Fournisseur | Variable d'env | Notes |
|---|---|---|
| **OpenRouter** *(recommandé)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — une seule clé, des centaines de modèles |
| Anthropic | `ANTHROPIC_API_KEY` | API directe |
| OpenAI | `OPENAI_API_KEY` | API directe |
| Gemini | `GEMINI_API_KEY` ou `GOOGLE_API_KEY` | API directe |
| CLI `claude` | — | Utilise votre abonnement Claude ; aucune clé API requise |
| CLI `gemini` | — | Utilise votre abonnement Gemini ; aucune clé API requise |
| Ollama | — | Modèles locaux, `http://localhost:11434/v1` |
| llamacpp | — | Modèles locaux, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | Tout point de terminaison compatible OpenAI |

Surcharge par exécution :

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

Stockez les clés API dans le trousseau du système d'exploitation plutôt que dans les variables d'environnement :

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## Flux de travail principal

### Choisir une organisation de contenu

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

La mémoire propre de l'agent (enseignements, règles, résumés de sessions dans `.veles/`) fonctionne de façon identique sous chaque organisation. Les packs personnalisés tiennent dans un unique `layout.toml` placé dans `~/.veles/layouts/<name>/`.

### Constituer une base de connaissances (organisation llm-wiki)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Base de connaissances Veles — ingérez une source dans une page de wiki, puis posez une question et obtenez une réponse qui la cite" width="800">
</p>

Le Curateur s'exécute automatiquement après les sessions. L'extraction d'enseignements repère des tournures comme « toujours préférer X » ou « ne jamais faire Y » et les inscrit comme des enseignements persistants du projet.

### Recherche approfondie

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

Décompose la question en sous-questions parallèles, explore chacune d'elles, et synthétise un rapport structuré.

### Objectifs de longue haleine

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### Tâches planifiées

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## Routage de modèles (ensembles)

Routez différents types de tâches vers différents modèles — configurez-le une fois et n'y pensez plus.

**En CLI :**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**En langage naturel dans `AGENTS.md` :**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## Compétences et modules

Les **compétences** sont des blocs de prompt réutilisables (`SKILL.md`) qui deviennent automatiquement des outils de l'agent.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

Les **modules** sont des plugins Python qui peuvent s'accrocher au cycle de vie de l'agent (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) et opposer un veto aux dispatchs d'outils.

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## TUI

```bash
veles                        # new session (bare `veles` launches the TUI)
veles tui --resume <id>      # continue a session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="TUI Veles — inspecteurs en slash (/status, /context), changement de mode et palette de commandes" width="800">
</p>

Les commandes en slash exposent tout en direct — `/status`, `/tokens`, `/context`, `/mode`, `/help` — et `Shift+Tab` fait défiler les modes (auto / planification / écriture / objectif).

| Touche | Action |
|---|---|
| `Enter` | Envoyer le message |
| `Shift+Enter` | Nouvelle ligne dans le composeur |
| `Ctrl+I` | Basculer l'inspecteur d'activité des outils |
| `Ctrl+R` | Superposition du sélecteur de sessions |
| `Ctrl+G` | Ouvrir `$EDITOR` sur le brouillon courant |
| `Tab` | Autocomplétion des commandes en slash |
| `Ctrl+D` | Quitter |

Commandes en slash : `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` et davantage.

---

## Démon + Telegram

Lancez Veles comme un démon persistant doté d'une API HTTP/WebSocket. Dans un répertoire de projet vierge, `veles daemon start` vous guide pas à pas dans la configuration — initialiser le projet, activer le démon et **connecter un canal** : choisissez d'abord un *type* de canal (Telegram est aujourd'hui la seule plateforme, mais le sélecteur est la jointure sur laquelle de nouveaux canaux s'enregistrent), puis renseignez les champs de ce canal (jeton du bot, liste blanche). Pas besoin d'ouvrir le TUI au préalable.

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — assistant qui démarre le démon et connecte un canal Telegram (d'abord le type de canal, puis son jeton et sa liste blanche)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

Le simple `veles daemon` ouvre un panneau de contrôle en direct — une arborescence projet → démons → canaux. Démarrez, arrêtez, redémarrez ou supprimez des démons, et ajoutez/retirez des canaux (le même flux « type de canal d'abord », touche `c`) sur tous les projets, le tout au clavier :

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — TUI panneau de contrôle : une arborescence projet → démons → canaux avec démarrer/arrêter/redémarrer/supprimer et gestion des canaux en ligne" width="800">
</p>

Le même assistant de canal est aussi disponible de façon autonome (`veles channel add`) sur un projet déjà en cours d'exécution.

Points de terminaison de l'API : `POST /v1/runs` pour soumettre un prompt, `WS /v1/runs/{id}/events` pour diffuser la réponse, `GET /v1/sessions` pour lister les sessions. Tous sauf `GET /v1/health` exigent `Authorization: Bearer <token>` (générez-en un avec `veles daemon token add <name>`).

Chaque utilisateur Telegram dispose d'une session persistante. Utilisez `veles channel list-sessions` / `reset-session` pour gérer les correspondances.

---

## Multi-projet

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## Confiance et sécurité

Chaque appel d'outil sensible (exécution de commandes shell, écritures de fichiers, récupérations d'URL) demande l'autorisation :

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

Pré-accordez l'autorisation pour la CI ou des exécutions autonomes prolongées :

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

L'agent ne voit que le répertoire du projet actif — les autres projets, les évasions par liens symboliques et la traversée par `..` sont bloqués.

---

## Export / import

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## Référence CLI

| Commande | Rôle |
|---|---|
| `veles init [name]` | Créer un nouveau projet |
| `veles run "<prompt>"` | Exécution d'agent en un seul tour |
| `veles tui` | REPL TUI interactif |
| `veles add <file\|url>` | Ingérer une source → page de wiki |
| `veles research "<question>"` | Recherche approfondie multi-angles |
| `veles curate` | Consolider les sessions dans le wiki |
| `veles sessions {list,show,delete,search}` | Gestion des sessions |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | Gestion des compétences |
| `veles tool {list,show,promote}` | Gestion des outils |
| `veles module {list,add,remove}` | Gestion des plugins |
| `veles route {show,set,reset,refresh}` | Routage de modèles |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Objectifs à long horizon |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Tâches planifiées |
| `veles dream` | Cycle de consolidation mémoire en arrière-plan |
| `veles project {list,add,remove,switch}` | Registre multi-projet |
| `veles subproject {init,list,switch,remove,suggest}` | Projets enfants |
| `veles trust {list,set,revoke,clear}` | Octrois de confiance |
| `veles autopilot {enable,disable,status}` | Contournement temporaire de confiance |
| `veles secret {set,get,list,delete}` | Secrets du trousseau de l'OS |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | Démon HTTP/WS |
| `veles channel {run,list-sessions,reset-session}` | Passerelle de canal externe |
| `veles mcp {list,test}` | Serveurs MCP externes |
| `veles models <provider>` | Lister les modèles d'un fournisseur |
| `veles doctor` | Vérifications de santé |
| `veles export / import` | Sauvegarde et transfert de projet |

Chaque commande dispose de `--help`.

---

## Documentation

Documentation complète — organisée selon Diátaxis (tutoriels · guides pratiques · référence · explication) :

- **Français :** [`docs/fr/index.md`](docs/fr/index.md)

Autres langues : utilisez le sélecteur 🌐 en haut de n'importe quelle page de la documentation.

---

## Contribuer

Les contributions sont les bienvenues — Veles est **conçu pour être étendu**. Le noyau reste petit (boucle d'agent + mémoire de projet + protocole de fournisseur) ; presque tout le reste est un point d'extension modulable, si bien qu'ajouter une capacité ne demande que rarement de toucher au noyau :

- **Adaptateurs de fournisseur** (`src/veles/adapters/`) — branchez un nouveau backend de modèle.
- **Compétences** — des blocs de prompt et outils réutilisables avec héritage `extends:`, promouvables d'un projet vers le niveau utilisateur global.
- **Outils** — du Python typé que l'agent écrit et réutilise, sous `<project>/.veles/tools/`.
- **Packs d'organisation** — un unique `layout.toml` dans `~/.veles/layouts/<name>/` définit toute une organisation de contenu.
- **Hooks de module** — observabilité, journalisation et politiques via les hooks `pre_turn` / `post_turn` (`src/veles/core/modules.py`).
- **Canaux et serveurs MCP** — de nouvelles passerelles et sources d'outils externes.
- **Locales** — des traductions dans `src/veles/locales/`.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

La base de code est délibérément décomposée — responsabilité unique, pas de fichiers fourre-tout. Lisez [`CONTRIBUTING.md`](CONTRIBUTING.md) pour les conventions et [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) avant d'ouvrir une PR. Bonnes premières contributions : adaptateurs de fournisseur, compétences de flux de travail, hooks de module et fichiers de locale.

---

## Licence

Apache 2.0 avec concession de brevet — voir [`LICENSE`](LICENSE) et [`NOTICE`](NOTICE).
