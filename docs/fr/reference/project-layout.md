# Mise en page et état du projet

> 🌐 **Langues :** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · **Français** · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

Ce que crée `veles init`, où Veles conserve son état, et le schéma de la mémoire de projet.

## Ce que produit `veles init`

La moitié « contenu utilisateur » dépend du pack de mise en page choisi (`--layout`,
par défaut `llm-wiki`) ; la moitié « état » dans `.veles/` est identique partout.

```
my-project/                  # veles init  (mise en page llm-wiki par défaut)
├── AGENTS.md                # contexte du projet (injecté dans l'agent)
├── CLAUDE.md → AGENTS.md    # lien symbolique, pour qu'un CLI `claude` reprenne le même contexte
├── GEMINI.md → AGENTS.md    # lien symbolique, pour un CLI `gemini`
├── sources/                 # matière source brute et immuable (lecture seule pour l'agent)
├── wiki/                    # la zone de connaissances inscriptible par le LLM
│   ├── concepts/ entities/ queries/ self-doc/ sessions/ sources/
└── .veles/                  # état du projet (ne pas committer ; géré par la machine)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite : sessions, tours, insights, règles, télémétrie
    ├── memory/              # les artefacts de mémoire propres à l'agent :
    │   ├── LOG.md           #   journal append-only des opérations système
    │   ├── insights/        #   vues rendues des lignes `insights`
    │   ├── sessions/        #   résumés de compaction
    │   └── proposals/       #   propositions de sous-projet / de promotion de skill
    ├── jobs/                # sorties des tâches planifiées
    └── skills/              # skills locaux au projet
```

Avec `--layout notes`, la moitié contenu se réduit à un unique répertoire `notes/` ;
avec `--layout bare`, il n'y a aucun échafaudage de contenu. `wiki/INDEX.md` (le
catalogue à la demande) est généré à mesure que le wiki grandit ; `config.toml`,
`tools/` et `plans/` apparaissent sous `.veles/` une fois que vous configurez
quelque chose, qu'un agent écrit un outil, ou que vous lancez un objectif.

## Répertoires d'état

| Chemin | Portée | Versionné ? |
|---|---|---|
| `<project>/AGENTS.md` + contenu de la mise en page (`wiki/`, `sources/`, `notes/`, …) | Contenu du projet | **Oui** — c'est votre base de connaissances |
| `<project>/.veles/` | État machine du projet (mémoire, config, skills/outils locaux) | Non |
| `~/.veles/` | Global à l'utilisateur : `config.toml`, autorisations de confiance, skills/outils inter-projets, packs de mise en page, cache des modèles, locales | Non |

`VELES_USER_HOME` redirige `~` pour l'arborescence globale à l'utilisateur (tests, bacs à sable).

## Mémoire de projet (`.veles/memory.db` + `.veles/memory/`)

La mémoire de projet de Veles est un **artefact structuré**, séparé de votre
contenu et indépendant de la mise en page. La base de données SQLite (mode WAL) fait
foi ; `.veles/memory/` héberge le côté lisible par l'humain (vues d'insights rendues,
condensés de sessions, propositions, journal des opérations système). Tables clés :

| Table | Contenu |
|---|---|
| `sessions`, `turns` | Historique des conversations (une ligne par tour) |
| `turns_fts` | Index plein texte sur les tours (alimente `veles sessions search`) |
| `insights`, `insights_fts`, `insight_refs` | Insights appris (lignes canoniques ; les vues markdown sont régénérables) + liens de déduplication |
| `rules`, `rules_fts` | Règles de format/à-faire/à-éviter/préférence injectées dans le prompt stable |
| `skills`, `skill_uses`, `skill_tool_refs` | Registre des skills + télémétrie + liens vers les outils |
| `tools`, `tool_uses` | Registre des outils + télémétrie (compteurs d'usage/succès/erreur) |
| `project_tree` | Carte en cache des fichiers du projet + balises sémantiques pour le classement par pertinence |

Voir [Mémoire de projet & la boucle d'apprentissage](../explanation/project-memory-and-learning-loop.md)
pour comprendre comment elles sont écrites et rappelées.

## Packs de mise en page

`veles init --layout {llm-wiki|notes|bare|<custom>}` choisit la mise en page du
contenu ; le pack possède l'échafaudage, le modèle d'AGENTS.md, les zones
inscriptibles, ainsi que l'activation ou non du moteur wiki (outils wiki, injection
de l'INDEX dans le prompt, rappel wiki). Voir
[packs de mise en page & le LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
