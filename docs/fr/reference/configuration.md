# Référence de configuration

> 🌐 **Langues :** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · **Français** · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

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
| `<project>/wiki/`, `sources/` | Projet | Contenu utilisateur (la mise en page LLM-Wiki par défaut) |

`VELES_USER_HOME` redirige `~` (l'état utilisateur se retrouve donc dans `<override>/.veles/`).
Voir [mise en page du projet](project-layout.md) pour l'arborescence complète.

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
fetch_url  = "approval_required" # allow | approval_required | always_confirm
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
[engine]
provider = "openrouter"                               # nom du fournisseur pour l'agent principal + base du routage
model = "anthropic/claude-sonnet-4.6"                # id du modèle (omettre pour exiger --model ou le default_model utilisateur)

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
| `[engine]` | Fournisseur de base (`provider` = nom du fournisseur) + modèle (`model` = id du modèle) pour l'agent principal et la cascade de routage |
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

### Épingler un backend et autres clés du corps de requête

`[engine.request.<provider>]` est transmis **tel quel** dans le corps de requête
de ce fournisseur. Veles ne modélise pas le schéma du fournisseur : tout ce que
celui-ci accepte fonctionne sans attendre que Veles en ait connaissance :

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

La section est indexée par le **nom du fournisseur** (`openrouter`, `anthropic`,
`openai`, `gemini`, `ollama`, `llamacpp`, `openai-compat`) afin qu'une même
configuration de projet survive à un changement de backend : un bloc `provider`
d'OpenRouter envoyé à llama.cpp donnerait un 400, donc chaque backend ne lit que
sa propre sous-section. Sans section déclarée, les requêtes sont identiques
octet pour octet à ce qu'elles étaient.

**Quand c'est utile : des mesures reproductibles.** Un relais comme OpenRouter
répartit un même modèle sur de nombreux backends avec des quantisations
différentes, si bien que deux exécutions sur la même entrée peuvent diverger pour
des raisons étrangères à l'entrée. Le routage persistant par `session_id`
maintient une conversation sur un seul backend, mais ne dit rien sur **lequel**.

Épinglez par `order`, pas par `quantizations`. Au 18/09/2026,
`z-ai/glm-5.3-flash` compte 29 endpoints : 16 en `fp8`, 3 en `fp4`, un en
`nvfp4`, **9 qui ne déclarent aucune quantisation** et aucun en `bf16`. Ainsi
`quantizations = ["fp8"]` laisse encore 16 candidats, avec des fenêtres de
contexte de 262144 à 1310720 jetons, tandis qu'un `order` à un seul élément plus
`allow_fallbacks = false` détermine le backend sans ambiguïté. Pour lister les
endpoints d'un modèle :

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

Ne gardez l'épinglage que dans le projet de mesure : la production veut le
routage persistant, qui préserve disponibilité et repli.

**Vérifier qu'il a tenu.** Chaque appel au modèle consigne dans
`.veles/traces.jsonl` l'intention et le résultat : `request_extra` correspond à ce
qui a été envoyé, `upstream_provider` au backend qui a répondu. Une ligne suffit :

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

Plus d'une ligne signifie que l'exécution a mélangé les backends. Les mêmes
enregistrements portent `reasoning_tokens` (la part du budget passée à raisonner)
et `est_cost_usd` (le coût réellement facturé par le fournisseur, quand il le
communique).

**Les erreurs sont bruyantes à dessein.** Un nom de fournisseur mal orthographié
ou une faute dans le chemin de la section (`[engine.reqest.…]`) interrompt
l'exécution avec une `ConfigError` nommant le fichier et les fournisseurs connus :
un épinglage qui n'a jamais atteint le câble invaliderait silencieusement la
mesure pour laquelle il avait été écrit. Veles ne vérifie pas les clés *à
l'intérieur* de la sous-section, car le fournisseur s'en charge : OpenRouter
répond `400 provider: Unrecognized key: "quantization"` pour une clé inconnue et
`404 No endpoints found …` pour une valeur sans correspondance.

### Durée de conservation des transcriptions

```toml
[memory]
turn_retention_days = 90   # 0 conserve tout indéfiniment
```

Les tours de conversation bruts sont supprimés au bout de ce délai ; les
**insights** et les règles qui en ont été extraits sont conservés indéfiniment.
La transcription est la matière première, les insights sont ce pour quoi elle a
été lue : `memory.db` cesse donc de croître sans limite tandis que l'agent garde
ce qu'il a appris.

**Deux** conditions doivent être réunies avant qu'une transcription disparaisse :
être plus ancienne que la fenêtre **et** que le curateur ait déjà traité cette
session. Une session que le curateur n'a pas atteinte n'est jamais supprimée,
quel que soit son âge — sinon la transcription serait détruite avant qu'on en ait
rien appris.

Le coût visible : `veles sessions search` ne trouve du texte qu'à l'intérieur de
la fenêtre. `veles sessions list` continue d'afficher les exécutions anciennes,
car les lignes de session (id, titre, horodatages) sont conservées : seuls les
corps de messages disparaissent. Le nettoyage a lieu pendant `veles dream`, après
l'extraction des insights.

### Rotation des journaux

`traces.jsonl` et `events.jsonl` tournent à 50 Mo vers `<nom>.<unix_ts>`, et les
**10** rotations les plus récentes sont conservées — les plus anciennes sont
supprimées à la rotation suivante. Auparavant elles étaient gardées
indéfiniment.

Rien à configurer à volume ordinaire : à ~530 octets par enregistrement de trace
et ~1,1 Ko d'événements par tour d'agent, la première rotation est à des années.
Le réglage existe parce qu'une croissance sans limite ni politique est une fuite
que devra découvrir celui qui héritera de la machine.

### Images

Une photo envoyée dans un canal est décrite avant le début du tour, avec le
modèle vers lequel pointe `[routing.tasks].vision` — soit, sans route explicite,
votre modèle `[engine]`. Un moteur multimodal ne demande donc aucune
configuration.

`[vision] mode` choisit le pipeline :

- `model` (par défaut) — le modèle de vision décrit l'image.
- `ocr` — Tesseract seul. Local, gratuit, sans appel au LLM ; adapté aux scans de
  texte.
- `ocr+model` — d'abord le texte littéral, puis la description du modèle.
- `off` — rien n'est lu ; le fichier est tout de même enregistré et l'agent peut
  appeler `image_describe` / `image_ocr` de lui-même s'il le souhaite.

Renseignez `[vision] model` lorsque le moteur est uniquement textuel. N'importe
quel fournisseur capable de vision convient, y compris un serveur local :
`ollama:llava`, `llamacpp:…`, `openai-compat:…`.

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
Voir [packs de mise en page & le LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
