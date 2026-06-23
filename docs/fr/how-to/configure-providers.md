# Configurer les fournisseurs

> 🌐 **Langues :** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · **Français** · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Basculez Veles entre OpenRouter, Anthropic, OpenAI, Gemini, des modèles locaux ou un
abonnement CLI. Liste complète des fournisseurs : [référence des fournisseurs](../reference/providers.md).

## Choisir un fournisseur par commande

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Définir une valeur par défaut pour le projet

Placez une base dans `<project>/.veles/config.toml` :

```toml
[provider]
default = "openrouter"                 # nom du fournisseur
model = "anthropic/claude-sonnet-4.6"  # id du modèle
```

Ou une valeur par défaut globale (au niveau utilisateur) dans `~/.veles/config.toml` :

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Fournir la clé d'API

Les fournisseurs cloud nécessitent une clé. Stockez-la une fois dans le trousseau du
système d'exploitation :

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…ou exportez la [variable d'environnement](../reference/environment-variables.md) :

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Ordre de recherche : trousseau (portée projet) → trousseau (par défaut) → variable
d'environnement. Les clés ne sont **jamais** écrites dans les fichiers de configuration.

## Utiliser un modèle entièrement local (sans clé)

Installez [Ollama](https://ollama.com), récupérez un modèle et pointez Veles vers lui :

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # vérifie qu'il est bien listé
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

L'appel d'outils est **désactivé par défaut** sur les fournisseurs locaux. Activez-le
une fois que vous avez choisi un modèle capable d'utiliser les outils :

```bash
export VELES_LOCAL_TOOLS=1
```

Redéfinissez les points d'accès si votre serveur n'écoute pas sur le port par défaut :

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Déléguer à un abonnement CLI Claude / Gemini

Si vous disposez du CLI `claude` ou `gemini` authentifié, Veles peut le piloter :

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

Aucune clé d'API nécessaire — le CLI gère l'authentification.

## Lister les modèles disponibles

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## Suite

- [Router différentes tâches vers différents modèles](per-task-routing.md) — un
  modèle bon marché pour la compression, un modèle puissant pour la planification.
