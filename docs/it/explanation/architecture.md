# Panoramica dell'architettura

> 🌐 **Lingue:** [English](../../en/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md) · **Italiano**

Questa pagina spiega cosa *è* Veles e come si incastrano le sue parti, così che il
resto della documentazione abbia senso. Per la visione di prodotto autorevole vedi
`VISION.md` nella radice del repository.

## L'intento progettuale

Veles è deliberatamente **minimalista e decomposto in modo pulito** — moduli a
singola responsabilità, niente file-monstre. È **local-first**: lo esegui su una
directory della tua macchina, e lì conserva la propria memoria strutturata.

## I cinque pilastri (il core)

Tutto ciò che sta nel core serve a uno di cinque compiti:

1. **Memoria di progetto** — un artefatto strutturato (separato dai tuoi contenuti)
   che contiene il log delle sessioni, le regole/insight apprese, una mappa dei file
   del progetto e i registri di skill/strumenti con la telemetria. Vedi
   [memoria di progetto e ciclo di apprendimento](project-memory-and-learning-loop.md).
2. **Il ciclo di apprendimento** — il curator, l'estrattore di insight e il sogno
   (dreaming) che mantengono la memoria aggiornata e trasformano l'esperienza in
   regole riutilizzabili.
3. **Orchestrazione multi-agente** — un manager che scompone un compito e genera
   worker specializzati. Vedi [orchestrazione multi-agente](multi-agent-orchestration.md).
4. **Un protocollo per i provider** — un'unica interfaccia su molti backend LLM
   (cloud, locali, delega a CLI). Vedi [provider](../reference/providers.md).
5. **Strumenti e skill minimi** — un piccolo insieme di partenza che **si accumula**
   man mano che Veles scrive i propri strumenti e formalizza i processi ricorrenti in
   skill. Vedi [skill e strumenti](skills-and-tools.md).

## Tutto il resto è un modulo opzionale

Gateway/canali, il daemon, lo scheduler, la TUI, vision/STT — tutto è **collegabile
a innesto** e si carica solo quando viene usato. Veles si avvia con il minimo e si
espande su richiesta, così un semplice `veles run` resta semplice.

## Come scorre un turno

```
il tuo prompt
   │
   ▼
contesto: AGENTS.md (piccolo) + recall su richiesta dalla memoria di progetto
   │
   ▼
loop dell'agente  ──►  provider (instradato per compito)  ──►  chiamate a strumenti
   │                                                            │
   │            (la scala di fiducia regola gli strumenti sensibili)
   ▼
risposta  ──►  salvata in memoria  ──►  trigger di apprendimento (insight, curator)
```

Il file di contesto (`AGENTS.md`) è tenuto piccolo di proposito; la conoscenza
ausiliaria (pagine wiki, la mappa dei file del progetto, i turni passati rilevanti)
viene richiamata **su richiesta** invece di essere riversata tutta in anticipo.

## Dove vive lo stato

- `<project>/.veles/` — la memoria di questo progetto, la configurazione, le
  skill/strumenti locali.
- `~/.veles/` — configurazione globale dell'utente, skill/strumenti cross-progetto,
  cache, fiducia.
- `<project>/AGENTS.md`, `wiki/`, `sources/` — i tuoi contenuti (il layout LLM-Wiki).

Vedi [layout del progetto](../reference/project-layout.md).

## Multi-progetto in un solo loop

Un unico loop dell'agente serve molti progetti. Ogni progetto ha la propria
directory con il proprio contesto e la propria memoria; `AGENTS.md` è collegato via
symlink a `CLAUDE.md`/`GEMINI.md` così che una CLI esterna avviata lì veda lo stesso
contesto. Vedi [progetti multipli](../how-to/multi-project-and-subprojects.md).

## Le superfici

- **CLI** (`veles run`, `veles add`, …) — uso one-shot e scriptato.
- **TUI** (`veles tui`) — REPL interattivo con [modalità di esecuzione](modes.md).
- **Daemon + canali** — API headless, Telegram, job pianificati.

Tutte e tre pilotano lo stesso loop centrale dell'agente.
