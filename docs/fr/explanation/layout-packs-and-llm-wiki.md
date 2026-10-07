# Packs de mise en page et le LLM-Wiki

> 🌐 **Langues :** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · **Français** · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

Un **pack de mise en page** (layout pack) définit la façon dont le *contenu utilisateur*
d'un projet est organisé — quels répertoires existent, dans lesquels l'agent peut écrire,
et quelles opérations il propose. La mise en page par défaut est **`bare`**, qui n'ajoute à votre
répertoire que `.veles/` et `AGENTS.md`. Le **LLM-Wiki** est une option du registre
d'extensions, **et non** un principe fondamental de Veles.

## Ce qu'est un pack de mise en page

Un pack de mise en page est un répertoire doté d'un manifeste `layout.toml` (ainsi que de
fichiers de skills et de modèles facultatifs). Le manifeste déclare :

- **Zones inscriptibles** — les répertoires dans lesquels l'agent peut écrire du contenu
  (appliqué à chaque `write_file`).
- **Zones en lecture seule** — le matériau que l'agent lit mais ne modifie jamais.
- **Opérations** — des workflows nommés, livrés sous forme de skills au sein du pack.
- **Scaffold** (`[layout.scaffold]`) — ce que `veles init` crée : des répertoires et un
  modèle `AGENTS.md` facultatif (`{name}` est substitué).
- **Moteurs** (`[layout.engines]`) — quelle machinerie de contenu le pack demande.
  Un moteur est fourni par un module (le module `wiki` du registre fournit `wiki`).
  Sans lui, il n'y a dans le projet aucun outil wiki, aucun rappel wiki, aucune
  injection d'INDEX.
- **Fichier de contexte** (`context_file`) — un fichier injecté dans l'invite système
  stable de l'agent (le LLM-Wiki utilise `INDEX.md`).

## Packs disponibles

| Pack | Provenance | Ce que produit `veles init --layout <name>` |
|---|---|---|
| `bare` *(par défaut)* | intégré | Aucun scaffold de contenu — pour les dépôts de code et le travail en forme libre. Les écritures sont permissives à l'intérieur de la racine du projet (toujours soumises à l'échelle de confiance). |
| `llm-wiki` | registre (`public:official/llm-wiki`, apporte le module `wiki`) | Le [LLM-Wiki de style Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) : `sources/` (lecture seule par convention, non appliquée), `wiki/` (inscriptible par l'agent), `INDEX.md` injecté dans l'invite, les skills `ingest`/`query`/`lint`/`organize`/`structure_design`, le moteur wiki activé, `veles add` et `/wiki`. Une invite comportementale déclarée par la mise en page (`templates/behaviour.md`) porte la discipline sources/wiki et les règles de migration/correctif du journal. |
| `notes` | registre (`public:official/notes`) | Un unique répertoire plat `notes/` dans lequel l'agent écrit. Aucune machinerie wiki. |

`veles init` dans un terminal demande quel pack utiliser (les packs installés et ceux de
vos registres) ; choisir un pack non installé propose de l'installer.
`veles registry install llm-wiki` l'installe à l'avance.

## Projets antérieurs à 1.2.3

Un projet dont la mise en page n'est pas installée (un projet `llm-wiki` après mise à
jour, ou un projet sans clé `layout` — c'étaient tous des projets wiki) s'ouvre quand
même. Dans un terminal, `veles` et `veles run` proposent d'installer le pack (avec le
moteur dont il a besoin) en une seule confirmation ; ailleurs — le daemon, les canaux,
les autres verbes — Veles affiche une fois la commande d'installation et fonctionne sans
le wiki. Rien dans `wiki/` n'est touché.

## Mises en page personnalisées

Déposez un pack dans `~/.veles/layouts/<name>/layout.toml` (global à l'utilisateur) ou dans
`<project>/.veles/layouts/<name>/` (local au projet ; il masque les packs utilisateur et
intégrés portant le même nom), puis lancez `veles init --layout <name>`. Le pack `notes` du registre
est un exemple minimal à copier. Un pack qui demande un moteur qu'aucun module installé
ne fournit reçoit la même offre d'installation. Vous pouvez aussi décrire des conventions dans `AGENTS.md` —
la mise en page applique les zones, AGENTS.md guide le comportement.

## Ce que ce n'est *pas*

La mise en page gouverne **uniquement votre contenu**. La mémoire de projet propre à Veles —
`memory.db` plus l'arborescence d'artefacts `.veles/memory/` (insights, condensés de session,
propositions, le journal des opérations système) — relève du système et fonctionne à
l'identique sous n'importe quelle mise en page. Changer de mise en page ne touche jamais à la
boucle d'apprentissage, aux sessions ou aux registres. Voir [architecture](architecture.md)
et [mise en page du projet](../reference/project-layout.md).
