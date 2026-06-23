# Per iniziare

> 🌐 **Lingue:** [English](../../en/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md)

In questo tutorial installi Veles, gli fornisci una chiave API, crei il tuo primo progetto
ed esegui il tuo primo prompt. Circa 10 minuti. Finirai con un progetto Veles
funzionante con cui potrai dialogare.

## Prerequisiti

- **Python 3.13+** (Veles richiede `>=3.13`).
- Una chiave API per un LLM. Useremo **OpenRouter** (il provider predefinito); funziona anche
  uno qualsiasi degli [altri provider](../reference/providers.md), inclusi quelli
  completamente locali senza chiave.

## 1. Installazione

Veles si installa come comando globale `veles` tramite [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

Per aggiornarlo in seguito: `uv tool install . --reinstall`.

## 2. Fornire a Veles una chiave API

Ottieni una chiave da [openrouter.ai](https://openrouter.ai) ed esportala:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Puoi anche memorizzarla nel portachiavi del sistema operativo, così da non doverla riesportare a ogni shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(Preferisci una configurazione completamente locale senza chiave? Installa [Ollama](https://ollama.com),
`ollama pull qwen3:4b-instruct` e usa `--provider ollama` qui sotto.)

## 3. Creare il tuo primo progetto

Un progetto Veles è semplicemente una directory con una cartella di stato `.veles/`. Creane una:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Questo crea `AGENTS.md` (il contesto del tuo progetto), `sources/` e `wiki/` (il
[layout LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) predefinito) e
`.veles/` (lo stato della macchina). Vedi [il layout del progetto](../reference/project-layout.md).

## 4. Eseguire il tuo primo prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles carica il contesto del tuo progetto, chiama il modello e stampa la risposta. Il
turno viene salvato nella memoria del progetto.

Aggiungi `--stream` per vedere i token man mano che arrivano, oppure `--verbose` per il progresso turno per turno:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Aprire la REPL interattiva

Per una conversazione a più turni, apri la TUI:

```bash
veles tui
```

Digita un messaggio e premi Invio. Tasti utili: `Ctrl+D` per uscire, `Shift+Tab` per
scorrere le [modalità di esecuzione](../explanation/modes.md), `/help` per elencare gli slash command. Elenco
completo nel [riferimento della TUI](../reference/tui.md).

## 6. Vedere cosa Veles ricorda

Ogni esecuzione viene salvata. Elenca e cerca nelle tue sessioni:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Dove andare adesso

- **[Costruire una base di conoscenza](building-a-knowledge-base.md)** — importa fonti
  nella wiki e fai domande su di esse.
- **[Configurare i provider](../how-to/configure-providers.md)** — passa a
  Anthropic, OpenAI, Gemini o a un modello completamente locale.
- **[Panoramica dell'architettura](../explanation/architecture.md)** — capisci cosa
  fa Veles sotto il cofano.
