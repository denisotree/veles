# Premiers pas

> 🌐 **Langues :** [English](../../en/tutorials/getting-started.md) · [简体中文](../../zh-CN/tutorials/getting-started.md) · [繁體中文](../../zh-TW/tutorials/getting-started.md) · [日本語](../../ja/tutorials/getting-started.md) · [한국어](../../ko/tutorials/getting-started.md) · [Español](../../es/tutorials/getting-started.md) · **Français** · [Italiano](../../it/tutorials/getting-started.md) · [Português (BR)](../../pt-BR/tutorials/getting-started.md) · [Português (PT)](../../pt-PT/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md) · [العربية](../../ar/tutorials/getting-started.md) · [हिन्दी](../../hi/tutorials/getting-started.md) · [বাংলা](../../bn/tutorials/getting-started.md) · [Tiếng Việt](../../vi/tutorials/getting-started.md)

Dans ce tutoriel, vous installez Veles, lui fournissez une clé API, créez votre
premier projet et lancez votre première requête. Environ 10 minutes. Vous
obtiendrez à la fin un projet Veles fonctionnel avec lequel dialoguer.

## Prérequis

- **Python 3.13+** (Veles requiert `>=3.13`).
- Une clé API de LLM. Nous utiliserons **OpenRouter** (le fournisseur par défaut) ;
  n'importe lequel des [autres fournisseurs](../reference/providers.md) convient
  également, y compris ceux entièrement locaux qui ne nécessitent aucune clé.

## 1. Installer

Veles s'installe en tant que commande globale `veles` via [uv](https://docs.astral.sh/uv/) :

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

Pour mettre à jour plus tard : `uv tool upgrade veles-ai`.

## 2. Fournir une clé API à Veles

Obtenez une clé sur [openrouter.ai](https://openrouter.ai) et exportez-la :

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Vous pouvez aussi la stocker dans le trousseau du système d'exploitation pour ne
pas avoir à la réexporter à chaque shell :

```bash
veles secret set OPENROUTER_API_KEY
```

(Vous préférez une configuration entièrement locale sans clé ? Installez
[Ollama](https://ollama.com), faites `ollama pull qwen3:4b-instruct`, puis
utilisez `--provider ollama` ci-dessous.)

## 3. Créer votre premier projet

Un projet Veles n'est qu'un répertoire muni d'un dossier d'état `.veles/`.
Créez-en un :

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Cela crée `AGENTS.md` (le contexte de votre projet), `sources/` et `wiki/` (le
[layout LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) par défaut), ainsi
que `.veles/` (l'état machine). Voir [structure du projet](../reference/project-layout.md).

## 4. Lancer votre première requête

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles charge le contexte de votre projet, appelle le modèle et affiche la
réponse. Le tour de conversation est enregistré dans la mémoire du projet.

Ajoutez `--stream` pour voir les tokens arriver au fil de l'eau, ou `--verbose`
pour suivre la progression tour par tour :

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Ouvrir le REPL interactif

Pour une conversation à plusieurs tours, ouvrez le TUI :

```bash
veles tui
```

Saisissez un message et appuyez sur Entrée. Touches utiles : `Ctrl+D` pour
quitter, `Shift+Tab` pour faire défiler les [modes d'exécution](../explanation/modes.md),
`/help` pour lister les commandes slash. Liste complète dans la
[référence du TUI](../reference/tui.md).

## 6. Voir ce dont Veles se souvient

Chaque exécution est enregistrée. Listez et recherchez vos sessions :

```bash
veles sessions list
veles sessions search "three sentences"
```

## Où aller ensuite

- **[Construire une base de connaissances](building-a-knowledge-base.md)** —
  intégrez des sources dans le wiki et posez-leur des questions.
- **[Configurer les fournisseurs](../how-to/configure-providers.md)** — basculez vers
  Anthropic, OpenAI, Gemini ou un modèle entièrement local.
- **[Vue d'ensemble de l'architecture](../explanation/architecture.md)** —
  comprenez ce que Veles fait sous le capot.
