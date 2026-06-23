# Variables d'environnement

> 🌐 **Langues :** **English** · [Русский](../../ru/reference/environment-variables.md)

Veles lit ces variables à l'exécution. Les clés d'API et les jetons sont à stocker
de préférence dans le trousseau du système d'exploitation (`veles secret set …`) ;
les variables d'environnement servent de solution de repli et de surcharge.

## Clés d'API des fournisseurs

Cascade de recherche d'une clé d'API : trousseau du système (portée projet) →
trousseau du système (portée par défaut) → variable d'environnement.

| Variable | Fournisseur | Remarques |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Fournisseur par défaut |
| `ANTHROPIC_API_KEY` | anthropic | API Anthropic directe |
| `OPENAI_API_KEY` | openai | API OpenAI directe |
| `GEMINI_API_KEY` | gemini | Clé principale pour Google Gemini |
| `GOOGLE_API_KEY` | gemini | Solution de repli pour Google Gemini |

`claude-cli` et `gemini-cli` s'authentifient via leurs propres binaires — aucune variable d'environnement.

## Fournisseurs locaux

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Point de terminaison Ollama |
| `OLLAMA_HOST` | suit `OLLAMA_BASE_URL` | Hôte Ollama pour les embeddings |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Point de terminaison du serveur llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (requis) | Point de terminaison du fournisseur `openai-compat` |
| `VELES_LOCAL_TOOLS` | désactivé | Active l'appel d'outils sur les fournisseurs locaux (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | défaut du fournisseur | Surcharge le modèle d'embedding Ollama |

## Canaux & daemon

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Jeton du bot Telegram pour `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL de base du daemon utilisée par les passerelles de canaux |
| `VELES_DAEMON_TOKEN` | — | Jeton Bearer pour l'authentification du daemon |

## Chemins & locale

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `VELES_USER_HOME` | `~` | Surcharge le home qui contient `~/.veles/` (état, cache, index du trousseau) |
| `VELES_HOME` | — | Ancien alias de `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Surcharge le chemin du registre multi-projets |
| `VELES_LOCALE` | `[user] language` ou `en` | Surcharge la locale active de l'interface pour une exécution |
| `VELES_LOG_LEVEL` | `INFO` | Verbosité du daemon/des logs (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Surcharge le nom du fichier de config (tests) |

## Comportement & feature flags

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `VELES_NO_WIZARD` | désactivé | Saute l'assistant de premier lancement (nécessite aussi un TTY) |
| `VELES_MANAGER_MODE` | désactivé | Force le manager multi-agents pour `veles run` (`1` activé / `0` coupe-circuit) |
| `VELES_FENCED_TOOLS` | désactivé | Exécute les outils via le chemin d'exécution cloisonné / en bac à sable |
| `VELES_TRUST_AUTO_ALLOW` | désactivé | Contourne l'échelle de confiance (CI / autopilot / sous-agents pré-autorisés) |
| `VELES_SANDBOX_ROOTS` | projet + `~/.veles` | Surcharge (séparée par `:`) des racines lecture/écriture du bac à sable |
| `VELES_FETCH_ALLOW_PRIVATE` | désactivé | Autorise les outils à atteindre des adresses RFC-1918 / privées |
| `VELES_MEMORY_RERANK` | activé | Reclassement vectoriel du rappel mémoire (`0`/`false` désactive) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend de recherche web pour `research` et `web_search` |

## Registres

| Variable | Rôle |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Source pour `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Source pour `veles browse modules` |

## Interne / tests

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — internes ; vous ne devriez pas
avoir à les définir.
