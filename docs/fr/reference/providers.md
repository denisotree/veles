# Fournisseurs

> 🌐 **Langues :** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · **Français** · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles est agnostique vis-à-vis des fournisseurs. Passez `--provider <name>` à
n'importe quelle commande d'agent, ou définissez une valeur par défaut dans la
config. Les identifiants de modèles suivent la nomenclature propre à chaque fournisseur.

| Fournisseur | Type | Clé d'API | Remarques |
|---|---|---|---|
| `openrouter` | Passerelle cloud | `OPENROUTER_API_KEY` | **Par défaut.** Relaie des centaines de modèles ; identifiants du type `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | API Claude Messages, mise en cache des prompts |
| `openai` | Cloud direct | `OPENAI_API_KEY` | Chat completions GPT |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Sous-processus | — (session CLI) | Délègue à un CLI `claude` local en mode JSON-stream |
| `gemini-cli` | Sous-processus | — (session CLI) | Délègue à un CLI `gemini` local |
| `ollama` | Local | aucune | `OLLAMA_BASE_URL` (défaut `http://localhost:11434/v1`) |
| `llamacpp` | Local | aucune | `LLAMACPP_BASE_URL` (défaut `http://localhost:8080/v1`) |
| `openai-compat` | Local/personnalisé | aucune | `OPENAI_COMPAT_BASE_URL` (requis, sans valeur par défaut) |

Fournisseur par défaut : `openrouter`. Il n'existe **aucun modèle par défaut codé en
dur** — définissez-en un via l'assistant de configuration, `[provider] model`, ou
`--model` (sinon l'agent signale « no model configured »). Les routes par tâche
héritent de `[provider]` comme base, sauf surcharge dans `[routing.tasks]` — voir
[routage par tâche](../how-to/per-task-routing.md).

## Fournisseurs locaux

`ollama`, `llamacpp` et `openai-compat` ne nécessitent aucune clé d'API. Listez les
modèles installés avec `veles models <provider>` (toujours en direct pour les
fournisseurs locaux).

**L'appel d'outils est désactivé par défaut** sur les fournisseurs locaux — de
nombreux modèles locaux émettent des appels d'outils malformés. Activez-le une fois
que vous avez choisi un modèle capable d'appeler des outils :

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Surchargez les points de terminaison avec les variables d'environnement `*_BASE_URL`
(voir [variables d'environnement](environment-variables.md)).

## Délégation à un CLI (`claude-cli`, `gemini-cli`)

Si vous disposez d'un abonnement au CLI Claude ou Gemini, Veles peut exécuter le
binaire en mode JSON-streaming et jouer le rôle de coordinateur — en gardant la
boucle d'abord locale, sans clé d'API séparée. Les outils de Veles n'atteignent le
sous-processus que lorsqu'un pont MCP est configuré.

## État du multimodal (vision / reconnaissance vocale)

Veles définit un `VisionAdapter` et un protocole d'adaptateur STT (`modules/vision.py`,
`modules/stt.py`) ainsi qu'un registre global au processus, **mais aucun adaptateur
concret n'est livré et rien n'en enregistre un au démarrage du daemon**. Ainsi, une
photo ou un message vocal envoyé à un canal renvoie pour l'instant un avis
« non configuré » plutôt que d'être analysé. La tâche de routage `vision` existe pour
le jour où un adaptateur sera branché. Voir
[connecter Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Choisir un modèle

```bash
veles models openrouter            # en cache 24 h
veles models openrouter --refresh  # contourne le cache
veles models ollama                # toujours en direct
```

Pour utiliser différents modèles selon les tâches (bon marché pour la compression,
puissant pour la planification), voir [routage par tâche](../how-to/per-task-routing.md).
