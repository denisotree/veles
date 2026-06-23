# Packs de disposition et le LLM-Wiki

> 🌐 **Langues :** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · **Français** · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

Un **pack de disposition** (layout pack) définit la façon dont le *contenu utilisateur*
d'un projet est organisé — quels répertoires existent, dans lesquels l'agent peut écrire,
et quelles opérations il propose. La disposition par défaut est le **LLM-Wiki**. C'est une
option de contenu, **et non** un principe fondamental de Veles.

## Ce qu'est un pack de disposition

Un pack de disposition est un répertoire doté d'un manifeste `layout.toml` (ainsi que de
fichiers de skills et de modèles facultatifs). Le manifeste déclare :

- **Zones inscriptibles** — les répertoires dans lesquels l'agent peut écrire du contenu
  (appliqué à chaque `write_file`).
- **Zones en lecture seule** — le matériau que l'agent lit mais ne modifie jamais.
- **Opérations** — des workflows nommés, livrés sous forme de skills au sein du pack.
- **Scaffold** (`[layout.scaffold]`) — ce que `veles init` crée : des répertoires et un
  modèle `AGENTS.md` facultatif (`{name}` est substitué).
- **Moteurs** (`[layout.engines]`) — quelle machinerie de contenu du cœur le pack active.
  Il existe aujourd'hui un seul moteur : `wiki`. Sans lui, il n'y a dans le projet aucun
  outil wiki, aucun rappel wiki, aucune injection d'INDEX.
- **Fichier de contexte** (`context_file`) — un fichier injecté dans l'invite système
  stable de l'agent (le LLM-Wiki utilise `INDEX.md`).

## Packs intégrés

| Pack | Ce que produit `veles init --layout <name>` |
|---|---|
| `llm-wiki` *(par défaut)* | Le [LLM-Wiki de style Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) : `sources/` (lecture seule), `wiki/` (inscriptible par l'agent), `INDEX.md` injecté dans l'invite, les skills `ingest`/`query`/`lint`, le moteur wiki activé. |
| `notes` | Un unique répertoire plat `notes/` dans lequel l'agent écrit. Aucune machinerie wiki. |
| `bare` | Aucun scaffold de contenu — pour les dépôts de code et le travail en forme libre. Les écritures sont permissives à l'intérieur de la racine du projet (toujours soumises à l'échelle de confiance). |

## Dispositions personnalisées

Déposez un pack dans `~/.veles/layouts/<name>/layout.toml` (global à l'utilisateur) ou dans
`<project>/.veles/layouts/<name>/` (local au projet ; il masque les packs utilisateur et
intégrés portant le même nom), puis lancez `veles init --layout <name>`. Le pack intégré `notes`
est l'exemple minimal à copier. Vous pouvez aussi décrire des conventions dans `AGENTS.md` —
la disposition applique les zones, AGENTS.md guide le comportement.

## Ce que ce n'est *pas*

La disposition gouverne **uniquement votre contenu**. La mémoire de projet propre à Veles —
`memory.db` plus l'arborescence d'artefacts `.veles/memory/` (insights, condensés de session,
propositions, le journal des opérations système) — relève du système et fonctionne à
l'identique sous n'importe quelle disposition. Changer de disposition ne touche jamais à la
boucle d'apprentissage, aux sessions ou aux registres. Voir [architecture](architecture.md)
et [disposition du projet](../reference/project-layout.md).
