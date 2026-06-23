# Come eseguire task di lunga durata: obiettivi, job, dreaming, ricerca

> 🌐 **Lingue:** [English](../../en/how-to/long-running-tasks.md) · [简体中文](../../zh-CN/how-to/long-running-tasks.md) · [繁體中文](../../zh-TW/how-to/long-running-tasks.md) · [日本語](../../ja/how-to/long-running-tasks.md) · [한국어](../../ko/how-to/long-running-tasks.md) · [Español](../../es/how-to/long-running-tasks.md) · [Français](../../fr/how-to/long-running-tasks.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/long-running-tasks.md) · [Português (PT)](../../pt-PT/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · [العربية](../../ar/how-to/long-running-tasks.md) · [हिन्दी](../../hi/how-to/long-running-tasks.md) · [বাংলা](../../bn/how-to/long-running-tasks.md) · [Tiếng Việt](../../vi/how-to/long-running-tasks.md)

Oltre ai singoli prompt, Veles può perseguire **obiettivi** multi-step con budget, eseguire
**job pianificati**, fare **dreaming** per consolidare la memoria, fare **ricerca** sul web in
parallelo e scomporre il lavoro tra un **manager** e dei sub-agenti.

## Obiettivi — traguardi con budget e checkpoint

Un obiettivo è un traguardo di lungo orizzonte con limiti espliciti e un log di avanzamento:

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

Nella TUI, la modalità di esecuzione **goal** (ciclabile con `Shift+Tab`) guida la stessa FSM
in modo interattivo: ti intervista, conferma un piano, esegue e verifica.

## Job — esecuzioni pianificate dell'agente

Pianifica l'esecuzione di un prompt secondo un'espressione cron, un intervallo o una sola volta a un orario:

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # run on the next tick
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

`--schedule` accetta un'espressione cron, `<N><s|m|h|d>` (es. `30m`) o un timestamp
ISO. I job vengono eseguiti quando il daemon è attivo, oppure eseguili tutti una volta in modo sincrono:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

Consegna l'output di un job a un canale con `--deliver-to telegram:<chat_id>`.

## Dreaming — consolidamento della memoria in background

`dream` estrae insight, deduplica le skill, suggerisce promozioni e fa il lint della
wiki — mantenendo la memoria fresca senza farti attendere:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

Un daemon in esecuzione fa dreaming automaticamente quando è inattivo.

## Ricerca — investigazione web in parallelo

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles scompone la domanda, esplora gli angoli in parallelo e sintetizza un
report con citazioni.

## Modalità manager — scomporre qualsiasi prompt

Attiva la scomposizione multi-agente per una singola esecuzione (un manager genera sub-agenti
explorer / writer / advisor e non scrive mai la risposta finale da solo):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

Vedi [orchestrazione multi-agente](../explanation/multi-agent-orchestration.md).
