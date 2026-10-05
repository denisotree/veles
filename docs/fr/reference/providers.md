# Fournisseurs

> 🌐 **Langues :** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · **Français** · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles est agnostique vis-à-vis des fournisseurs. Passez `--provider <id>` à
n'importe quelle commande d'agent, ou définissez une valeur par défaut dans la
config. Les identifiants de modèles suivent la nomenclature propre à chaque fournisseur.

## Le catalogue des fournisseurs

Tous les fournisseurs que Veles connaît sont des entrées d'un seul catalogue, construit
à partir de trois sources :

1. **Intégrés** — le tableau ci-dessous, livré avec Veles.
2. **Les vôtres** — `~/.veles/providers.toml` : une API hébergée compatible OpenAI ou un
   serveur que vous exploitez, en ajoutant une entrée (voir
   [ajouter votre propre fournisseur](../how-to/configure-providers.md#ajouter-votre-propre-fournisseur)).
   Une entrée portant un id intégré remplace les réglages de ce fournisseur (son
   `base_url`, par exemple).
3. **Modules** — un module du registre apporte un fournisseur (`antigravity-cli`). Le
   nommer dans `[engine] provider`, une route ou `--provider` l'installe depuis vos
   registres connectés à la prochaine exécution, comme un canal déclaré.

`--provider`, `veles models`, les assistants de configuration, le routage et
`veles doctor` lisent tous le catalogue : un fournisseur issu de n'importe quelle source
fonctionne partout où fonctionne un fournisseur intégré. Un id inconnu donne une erreur
d'une ligne qui liste ce qui existe ; `veles doctor` vérifie aussi
`~/.veles/providers.toml` et chaque fournisseur nommé par vos routes.

| Fournisseur | Type | Clé d'API | Remarques |
|---|---|---|---|
| `openrouter` | Passerelle cloud | `OPENROUTER_API_KEY` | **Par défaut.** Relaie des centaines de modèles ; identifiants du type `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | API Claude Messages, mise en cache des prompts |
| `openai` | Cloud direct | `OPENAI_API_KEY` | Chat completions GPT |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Délégué CLI | — (session CLI) | Délègue à un CLI `claude` local en mode JSON-stream |
| `ollama` | Local | aucune | `OLLAMA_BASE_URL` (défaut `http://localhost:11434/v1`) |
| `llamacpp` | Local | aucune | `LLAMACPP_BASE_URL` (défaut `http://localhost:8080/v1`) |
| `openai-compat` | Local/personnalisé | `OPENAI_COMPAT_API_KEY` facultative | `OPENAI_COMPAT_BASE_URL` (requis, sans valeur par défaut) |

`gemini-cli` a été retiré dans la 1.2.6 — Google ne propose plus le CLI Gemini aux
comptes personnels. Utilisez `gemini` avec une clé d'API, ou le module `antigravity-cli`.

Fournisseur par défaut : `openrouter`. Il n'existe **aucun modèle par défaut codé en
dur** — définissez-en un via l'assistant de configuration, `[engine] model`, ou
`--model` (sinon l'agent signale « no model configured »). Les routes par tâche
héritent de `[engine]` comme base, sauf surcharge dans `[routing.tasks]` — voir
[routage par tâche](../how-to/per-task-routing.md).

## Fournisseurs locaux

`ollama`, `llamacpp` et `openai-compat` ne nécessitent aucune clé d'API. Listez les
modèles installés avec `veles models <provider>` (toujours en direct pour les
fournisseurs locaux).

**L'appel d'outils est détecté** d'après ce que le backend annonce : ollama indique les
capacités de chaque modèle, un serveur llama.cpp celles de son modèle de chat.
`VELES_LOCAL_TOOLS=1` force l'appel d'outils, `=0` le désactive ; non défini, il est
détecté.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Surchargez les points de terminaison avec les variables d'environnement `*_BASE_URL`
(voir [variables d'environnement](environment-variables.md)).

## Délégation à un CLI (`claude-cli`, `antigravity-cli`)

Si vous disposez d'un abonnement Claude ou Google, Veles peut exécuter son CLI en mode
headless et jouer le rôle de coordinateur — sans clé d'API séparée. `claude-cli` est
intégré ; `antigravity-cli` (le CLI `agy`) est un module du registre qui s'installe tout
seul quand vous le nommez.

Le délégué n'est que le modèle : les outils de Veles lui parviennent par un pont MCP, et
chaque appel passe par l'échelle de confiance de Veles. La configuration du pont vit
dans un répertoire du processus en cours, `.veles/tmp/delegate-<pid>/`, supprimé à sa
sortie. `agy` s'exécute dans un espace de travail temporaire hors de votre projet (sous
`~/.veles/tmp/`), si bien que la configuration `.agents/` du projet ne lui parvient
jamais, derrière une barrière qui refuse ses propres outils shell et fichiers.

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
