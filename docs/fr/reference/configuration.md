# Référence de configuration

> 🌐 **Langues :** **English** · [Русский](../../ru/reference/configuration.md)

Veles se configure via deux fichiers TOML et un ensemble de répertoires d'état. Les
secrets (clés d'API, jetons de bot) ne sont **jamais** écrits dans ces fichiers — ils
résident dans le trousseau du système d'exploitation ou dans des variables
d'environnement (voir [variables d'environnement](environment-variables.md)).

## Où l'état est stocké

| Chemin | Portée | Contenu |
|---|---|---|
| `~/.veles/` | Global à l'utilisateur | `config.toml`, autorisations de confiance, skills/outils inter-projets, cache des modèles, locales, registre |
| `<project>/.veles/` | Local au projet | `project.toml`, `config.toml`, `memory.db`, skills/outils du projet, plans, artefacts d'exécution |
| `<project>/AGENTS.md` | Projet | Le fichier de contexte injecté dans l'agent (lié symboliquement à `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Projet | Contenu utilisateur (la disposition LLM-Wiki par défaut) |

`VELES_USER_HOME` redirige `~` (l'état utilisateur se retrouve donc dans `<override>/.veles/`).
Voir [structure du projet](project-layout.md) pour l'arborescence complète.

---

## Config utilisateur — `~/.veles/config.toml`

Écrite par l'assistant de premier lancement ; modifiable à la main sans risque.

```toml
[user]
language = "en"                  # "en" | "ru" — locale des chaînes de l'interface
default_provider = "openrouter"  # fournisseur par défaut pour les nouveaux projets
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # enregistré par l'assistant
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # politique optionnelle par outil
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # routage optionnel à la portée utilisateur (voir ci-dessous)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # serveurs MCP optionnels à la portée utilisateur
transport = "stdio"
command = "python"               # exécutable seulement — les arguments vont dans `args`
args = ["-m", "my_mcp_server"]
```

| Clé | Type | Rôle |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale des chaînes de l'interface (surchargeable via `VELES_LOCALE`) |
| `[user] default_provider` | string | Fournisseur utilisé quand aucun n'est précisé |
| `[user] default_model` | string | Modèle utilisé quand aucun n'est précisé |
| `[user] tui_theme` | string | Thème de couleurs par défaut de la TUI |
| `[permissions] <tool>` | policy | Politique de permission par outil (voir [confiance & bac à sable](../explanation/trust-and-sandbox.md)) |

---

## Config projet — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base pour l'agent principal + le routage

[routing.tasks]                  # surcharges par tâche (priorité la plus haute en dessous des flags explicites)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # le daemon anonyme / « par défaut »
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # une session de daemon nommée (« api »)
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # canaux globaux (servis par le daemon anonyme)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # canaux liés à une session de daemon nommée
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # serveurs MCP externes (portée projet)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # exécutable seulement — les arguments vont dans `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} est interpolé depuis l'environnement
```

### Sections

| Section | Rôle |
|---|---|
| `[provider]` | Fournisseur/modèle de base pour l'agent principal et la cascade de routage |
| `[routing.tasks]` | Surcharges `provider:model` par tâche — voir [routage par tâche](../how-to/per-task-routing.md) |
| `[permissions]` | Politique de permission par outil (portée projet) |
| `[daemon]` | Liaison + démarrage automatique du daemon anonyme / « par défaut » |
| `[daemon.<name>]` | Une session de daemon nommée (modèle/fournisseur/host/port/mode propres) |
| `[channels.<type>]` | Un canal servi par le daemon anonyme (par ex. `telegram`) |
| `[daemon.<name>.channels.<type>]` | Un canal lié à une session de daemon nommée |
| `[mcp.servers.<name>]` | Un serveur MCP externe (source d'outils) |

Types de tâches pour `[routing.tasks]` : `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> Les indices de routage en langage naturel présents dans `AGENTS.md` sont analysés
> pour produire automatiquement un `routing.nl.toml` ; les entrées `[routing.tasks]`
> explicites l'emportent toujours. Lancez `veles route refresh` pour relancer
> l'analyse. Voir [routage par tâche](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` contient les métadonnées immuables du projet (`name`,
`created_at`, `schema_version`, `layout`). Vous n'avez normalement pas à le modifier à la main.

---

## AGENTS.md

Le fichier de contexte du projet, à la racine de celui-ci. Il est injecté dans le
prompt système de l'agent au démarrage et lié symboliquement à `CLAUDE.md` et
`GEMINI.md`, afin qu'un CLI `claude` ou `gemini` lancé dans le répertoire reprenne
le même contexte.

Gardez-le compact — les fichiers `.md` auxiliaires (par ex. `wiki/INDEX.md`) se
chargent à la demande. Validez les sections requises avec `veles schema validate`.
Voir [packs de disposition & le LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
