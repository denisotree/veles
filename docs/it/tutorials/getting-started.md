# Per iniziare

> 🌐 **Lingue:** [English](../../en/tutorials/getting-started.md) · [简体中文](../../zh-CN/tutorials/getting-started.md) · [繁體中文](../../zh-TW/tutorials/getting-started.md) · [日本語](../../ja/tutorials/getting-started.md) · [한국어](../../ko/tutorials/getting-started.md) · [Español](../../es/tutorials/getting-started.md) · [Français](../../fr/tutorials/getting-started.md) · **Italiano** · [Português (BR)](../../pt-BR/tutorials/getting-started.md) · [Português (PT)](../../pt-PT/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md) · [العربية](../../ar/tutorials/getting-started.md) · [हिन्दी](../../hi/tutorials/getting-started.md) · [বাংলা](../../bn/tutorials/getting-started.md) · [Tiếng Việt](../../vi/tutorials/getting-started.md)

In questo tutorial installi Veles, gli fornisci una chiave API, crei il tuo primo
progetto ed esegui il tuo primo prompt. Circa 10 minuti. Al termine avrai un
progetto Veles funzionante con cui dialogare.

## Prerequisiti

- **Python 3.13+** (Veles richiede `>=3.13`).
- Una chiave API per un LLM. Useremo **OpenRouter** (il provider di default); va
  bene anche uno qualsiasi degli [altri provider](../reference/providers.md),
  compresi quelli completamente locali senza chiave.

## 1. Installazione

Veles si installa come comando globale `veles` tramite [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

Per aggiornare in seguito: `uv tool upgrade veles-ai`.

## 2. Fornire a Veles una chiave API

Ottieni una chiave da [openrouter.ai](https://openrouter.ai) ed esportala:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Puoi anche conservarla nel keychain del sistema operativo per non doverla
ri-esportare a ogni shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(Preferisci una configurazione completamente locale senza chiave? Installa
[Ollama](https://ollama.com), `ollama pull qwen3:4b-instruct` e usa `--provider
ollama` qui sotto.)

## 3. Creare il primo progetto

Un progetto Veles è semplicemente una directory con una cartella di stato
`.veles/`. Creane una:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Questo crea `AGENTS.md` (il contesto del tuo progetto), `sources/` e `wiki/` (il
[layout LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) di default) e
`.veles/` (lo stato macchina). Vedi [layout del progetto](../reference/project-layout.md).

## 4. Eseguire il primo prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles carica il contesto del tuo progetto, chiama il modello e stampa la risposta.
Il turno viene salvato nella memoria del progetto.

Aggiungi `--stream` per vedere i token man mano che arrivano, oppure `--verbose`
per l'avanzamento per turno:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Aprire il REPL interattivo

Per una conversazione a più turni, apri la TUI:

```bash
veles tui
```

Digita un messaggio e premi Invio. Tasti utili: `Ctrl+D` per uscire, `Shift+Tab`
per scorrere le [modalità di esecuzione](../explanation/modes.md), `/help` per
elencare i comandi slash. Elenco completo nel [riferimento TUI](../reference/tui.md).

## 6. Vedere cosa ricorda Veles

Ogni esecuzione viene salvata. Elenca e cerca tra le tue sessioni:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Dove andare poi

- **[Costruire una knowledge base](building-a-knowledge-base.md)** — ingerisci
  sorgenti nella wiki e poni domande su di esse.
- **[Configurare i provider](../how-to/configure-providers.md)** — passa ad
  Anthropic, OpenAI, Gemini o a un modello completamente locale.
- **[Panoramica dell'architettura](../explanation/architecture.md)** — comprendi
  cosa fa Veles dietro le quinte.
