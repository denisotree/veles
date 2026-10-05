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
[engine]
provider = "openrouter"                 # nom du fournisseur
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

L'appel d'outils est **détecté** d'après ce que le serveur annonce. Forcez-le avec
`VELES_LOCAL_TOOLS=1` (ou désactivez-le avec `=0`).

Redéfinissez les points d'accès si votre serveur n'écoute pas sur le port par défaut :

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # requis pour openai-compat
```

## Ajouter votre propre fournisseur

Toute API hébergée compatible OpenAI, ou un serveur que vous exploitez, devient un
fournisseur grâce à une entrée dans `~/.veles/providers.toml` — sans code. L'id est le
nom de la table :

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

Utilisez-le ensuite comme n'importe quel fournisseur intégré :

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| Clé | Signification |
|---|---|
| `kind` | `openai-api` (une API hébergée) ou `local` (un serveur que vous exploitez) |
| `base_url` | le point de terminaison compatible OpenAI, se terminant par `/v1` (ou l'équivalent du fournisseur) |
| `base_url_env` | une variable d'environnement qui remplace `base_url` quand elle est définie |
| `key_env` | noms des variables d'environnement d'où la clé est lue ; le trousseau est essayé en premier |
| `label`, `tagline` | la façon dont les assistants l'affichent |
| `tools` | `auto` (par défaut), `on` ou `off` — si le modèle reçoit des appels d'outils |

Une entrée portant un id intégré (`[providers.ollama]`) modifie les réglages de ce
fournisseur — son `base_url`, par exemple — mais pas son type. Un fichier cassé est
signalé une seule fois, et Veles continue avec les fournisseurs intégrés ;
`veles doctor` liste ce qui ne va pas.

Points de départ pour des API courantes — **non vérifiés par l'équipe Veles**,
consultez la documentation du fournisseur pour le point de terminaison actuel :

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## Déléguer à un abonnement Claude / Google

Si vous disposez du CLI `claude` authentifié, Veles peut le piloter :

```bash
veles run --provider claude-cli "..."
```

Pour un abonnement Google, installez le CLI Antigravity (`agy`) et connectez-vous une
fois, puis nommez son fournisseur — le module `antigravity-cli` s'installe tout seul
depuis vos registres connectés lors de cette exécution :

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
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
