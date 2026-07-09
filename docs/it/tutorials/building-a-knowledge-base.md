# Costruire una base di conoscenza

> 🌐 **Lingue:** [English](../../en/tutorials/building-a-knowledge-base.md) · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · [日本語](../../ja/tutorials/building-a-knowledge-base.md) · [한국어](../../ko/tutorials/building-a-knowledge-base.md) · [Español](../../es/tutorials/building-a-knowledge-base.md) · [Français](../../fr/tutorials/building-a-knowledge-base.md) · **Italiano** · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · [Português (PT)](../../pt-PT/tutorials/building-a-knowledge-base.md) · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · [العربية](../../ar/tutorials/building-a-knowledge-base.md) · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · [বাংলা](../../bn/tutorials/building-a-knowledge-base.md) · [Tiếng Việt](../../vi/tutorials/building-a-knowledge-base.md)

In questo tutorial trasformerai un progetto Veles in una base di conoscenza viva: importi
alcune fonti, lasci che Veles scriva pagine wiki, fai domande e consolidi ciò che
hai imparato. Questo è il flusso di lavoro **LLM-Wiki** predefinito. Circa 15 minuti.

Dovresti aver completato prima [Per iniziare](getting-started.md).

## L'idea

Un progetto Veles ha due zone di contenuto:

- `sources/` — il materiale grezzo e immutabile che gli fornisci (in sola lettura per l'agente).
- `wiki/` — la conoscenza dell'agente stesso, generata dall'LLM (l'unica zona in cui
  scrive contenuti).

Tu fornisci le fonti; Veles le distilla in pagine wiki collegate; tu interroghi la
wiki in linguaggio naturale. Vedi [i layout pack e la LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)
per il perché.

## 1. Importare una fonte

`veles add` legge un file o un URL e scrive una pagina wiki che lo riassume:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

Ogni `add` produce una pagina sotto `wiki/` e la collega al grafo della wiki.

## 2. Guardare la wiki crescere

Osserva ciò che è stato scritto:

```bash
ls wiki/concepts wiki/entities
```

Le pagine si fanno riferimento a vicenda. Il catalogo on-demand `wiki/INDEX.md` mantiene una
mappa che l'agente carica quando ne ha bisogno (non un dump monolitico di contesto).

## 3. Fare domande

Ora interroga la tua base di conoscenza in linguaggio naturale:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles cerca nella wiki, legge le pagine pertinenti e risponde — basandosi su ciò che
hai importato piuttosto che solo sui suoi dati di addestramento.

Per uno scambio interattivo, fai lo stesso nella TUI (`veles tui`).

## 4. Consolidare le sessioni

Man mano che lavori, le conversazioni si accumulano. Esegui il curatore per compattarle in
pagine wiki durature ed estrarre lezioni:

```bash
veles curate
```

Questo scrive le pagine `wiki/sessions/` e aggiorna gli insight e le regole del progetto.
Veles lo fa anche automaticamente nel tempo — vedi
[memoria del progetto e ciclo di apprendimento](../explanation/project-memory-and-learning-loop.md).

## 5. Mantenere la wiki in salute

Col tempo le pagine diventano obsolete o orfane. L'operazione `lint` le individua:

```bash
veles run "lint"
```

(`ingest`, `query` e `lint` sono skill incluse nel layout LLM-Wiki; le
invochi con `veles run "<operation>"` oppure lasci che sia l'agente a chiamarle.)

## Cosa hai costruito

Una base di conoscenza auto-organizzante: fonti in ingresso, pagine wiki collegate in uscita, interrogabile in
linguaggio naturale, che diventa più ordinata man mano che Veles consolida. Da qui:

- **[Gestire skill, tool e moduli](../how-to/manage-skills-and-tools.md)** —
  insegna a Veles flussi di lavoro riutilizzabili.
- **[Eseguire come daemon](../how-to/run-as-daemon.md)** + **[collegare Telegram](../how-to/connect-telegram.md)** —
  parla alla tua base di conoscenza dal telefono.
- **[Progetti multipli e sottoprogetti](../how-to/multi-project-and-subprojects.md)** —
  scala verso molte basi di conoscenza.
