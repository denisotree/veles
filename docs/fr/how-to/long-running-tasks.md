# Exécuter des tâches de longue durée : objectifs, jobs, rêve, recherche

> 🌐 **Langues :** [English](../../en/how-to/long-running-tasks.md) · [简体中文](../../zh-CN/how-to/long-running-tasks.md) · [繁體中文](../../zh-TW/how-to/long-running-tasks.md) · [日本語](../../ja/how-to/long-running-tasks.md) · [한국어](../../ko/how-to/long-running-tasks.md) · [Español](../../es/how-to/long-running-tasks.md) · **Français** · [Italiano](../../it/how-to/long-running-tasks.md) · [Português (BR)](../../pt-BR/how-to/long-running-tasks.md) · [Português (PT)](../../pt-PT/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · [العربية](../../ar/how-to/long-running-tasks.md) · [हिन्दी](../../hi/how-to/long-running-tasks.md) · [বাংলা](../../bn/how-to/long-running-tasks.md) · [Tiếng Việt](../../vi/how-to/long-running-tasks.md)

Au-delà des prompts isolés, Veles peut poursuivre des **objectifs** multi-étapes
assortis de budgets, exécuter des **jobs planifiés**, **rêver** pour consolider la
mémoire, **rechercher** sur le web en parallèle, et décomposer le travail entre un
**manager** et des sous-agents.

## Objectifs — des buts assortis de budgets et de points de contrôle

Un objectif est un but à long horizon avec des limites explicites et un journal de
progression :

```bash
veles goal start "Draft a competitor analysis report" \
  --done-when "report.md exists and cites >=3 sources" \
  --max-steps 30 --max-cost-usd 5 --max-wall-time-s 3600

veles goal list
veles goal show <id>
veles goal checkpoint <id> "Outlined sections; cited 2 sources" --cost-usd 0.40
veles goal pause <id> ; veles goal resume <id>
veles goal done <id> --evidence report.md
veles goal cancel <id> --reason "scope changed"
```

Dans le TUI, le mode d'exécution **goal** (parcouru avec `Shift+Tab`) pilote la même
machine à états (FSM) de manière interactive : il vous interroge, confirme un plan,
exécute et vérifie.

## Jobs — exécutions d'agent planifiées

Planifiez l'exécution d'un prompt selon une expression cron, un intervalle ou une seule
fois à un instant donné :

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # exécute au prochain tick
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

`--schedule` accepte une expression cron, `<N><s|m|h|d>` (p. ex. `30m`) ou un horodatage
ISO. Les jobs s'exécutent quand le daemon est actif, ou exécutez-les tous une fois de
manière synchrone :

```bash
veles job tick                  # exécute les jobs dus maintenant, sans daemon
```

Livrez la sortie d'un job vers un canal avec `--deliver-to telegram:<chat_id>`.

## Rêve — consolidation de la mémoire en arrière-plan

`dream` extrait des insights, déduplique les skills, suggère des promotions et vérifie
le wiki — gardant la mémoire à jour sans que vous ayez à attendre :

```bash
veles dream
veles dream --include-consolidation     # exécute aussi la consolidation LLM (payante)
veles dream --dry-run                    # montre ce qu'il ferait
```

Un daemon en cours d'exécution rêve automatiquement lorsqu'il est inactif.

## Recherche — investigation web en parallèle

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles décompose la question, explore les angles en parallèle et synthétise un rapport
sourcé.

## Mode manager — décomposer n'importe quel prompt

Activez la décomposition multi-agents pour une seule exécution (un manager engendre des
sous-agents explorer / writer / advisor et n'écrit jamais lui-même la réponse finale) :

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# ou globalement : export VELES_MANAGER_MODE=1   (=0 pour forcer la désactivation)
```

Voir [orchestration multi-agents](../explanation/multi-agent-orchestration.md).
