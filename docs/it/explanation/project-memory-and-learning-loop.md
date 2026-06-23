# Memoria di progetto e ciclo di apprendimento

> 🌐 **Lingue:** [English](../../en/explanation/project-memory-and-learning-loop.md) · [简体中文](../../zh-CN/explanation/project-memory-and-learning-loop.md) · [繁體中文](../../zh-TW/explanation/project-memory-and-learning-loop.md) · [日本語](../../ja/explanation/project-memory-and-learning-loop.md) · [한국어](../../ko/explanation/project-memory-and-learning-loop.md) · [Español](../../es/explanation/project-memory-and-learning-loop.md) · [Français](../../fr/explanation/project-memory-and-learning-loop.md) · **Italiano** · [Português (BR)](../../pt-BR/explanation/project-memory-and-learning-loop.md) · [Português (PT)](../../pt-PT/explanation/project-memory-and-learning-loop.md) · [Русский](../../ru/explanation/project-memory-and-learning-loop.md) · [العربية](../../ar/explanation/project-memory-and-learning-loop.md) · [हिन्दी](../../hi/explanation/project-memory-and-learning-loop.md) · [বাংলা](../../bn/explanation/project-memory-and-learning-loop.md) · [Tiếng Việt](../../vi/explanation/project-memory-and-learning-loop.md)

La caratteristica distintiva di Veles è che **ricorda** e **impara** per ogni
progetto. Questa pagina spiega cos'è quella memoria e come il ciclo di apprendimento
la mantiene utile.

## La memoria è un artefatto strutturato

La memoria di progetto vive in `<project>/.veles/` — `memory.db` (SQLite, la fonte
di verità) più un albero `.veles/memory/` leggibile dall'uomo (viste renderizzate
degli insight, digest di sessione, proposte, un giornale delle operazioni di
sistema). È **separata dai tuoi contenuti** e funziona in modo identico sotto
qualsiasi layout (wiki, notes o bare). Non è uno scarico di trascrizioni di chat — è
un insieme di strati strutturati:

- **Log delle sessioni** — ogni conversazione, una riga per turno, indicizzata a
  testo pieno.
- **Regole** — brevi imperativi che l'agente dovrebbe seguire (`format`, `do`,
  `don't`, `preference`), iniettati nel system prompt stabile.
- **Insight** — lezioni distillate dalle sessioni. La riga SQL è canonica (recall,
  invecchiamento e dedup operano su di essa); una vista markdown viene renderizzata
  in `.veles/memory/insights/` per gli umani e per gli export.
- **Mappa dell'albero del progetto** — una mappa dei file in cache, etichettata
  semanticamente, così l'agente legge i 3-5 file rilevanti, non l'intero albero.
- **Registri di skill e strumenti** — con telemetria (conteggi di uso/successo/errore)
  usata da ranking e dedup.

Vedi l'elenco delle tabelle in [layout del progetto](../reference/project-layout.md#project-memory-velesmemorydb).

## Recall: contesto piccolo, richiamato su richiesta

`AGENTS.md` è deliberatamente piccolo. Quando chiedi qualcosa, Veles richiama solo
ciò che è rilevante: i turni passati corrispondenti (testo pieno + reranking
vettoriale opzionale), le regole e gli insight applicabili e i file con il punteggio
più alto nella mappa dell'albero del progetto. Questo mantiene ogni chiamata al
modello focalizzata ed economica invece di riversare tutto.

## Il ciclo di apprendimento

L'esperienza diventa conoscenza duratura attraverso tre meccanismi:

### Insight — catturare le lezioni
Dopo un'esecuzione, un estrattore cerca cose degne di essere ricordate: feedback
espliciti del tipo "ricorda X" / "mai Y" e pattern di errore-strumento→recupero (un
fallimento seguito da una correzione). Li distilla in insight e regole così che lo
stesso errore non venga ripetuto.

### Curator — consolidare le sessioni
Il curator distilla le sessioni più vecchie in memoria duratura: sempre insight e
regole SQL; in aggiunta una pagina `wiki/sessions/` quando il layout del progetto
abilita l'engine wiki. Gira su timer di inattività/post-turno, o su richiesta con
`veles curate`.

### Dreaming — manutenzione in background
`veles dream` (e il daemon quando è inattivo) estrae insight, deduplica skill e
insight, suggerisce promozioni e (sotto un layout wiki) controlla (lint) la wiki —
mantenendo la memoria aggiornata senza bloccarti. Aggiungi `--include-consolidation`
per un passaggio LLM più approfondito.

## Compressione del contesto

Le conversazioni lunghe sono mantenute sotto il limite di contesto del modello da un
compressore a finestra scorrevole: quando la cronologia in memoria supera una soglia
di token, la parte centrale viene riassunta (da un modello instradato economico) e
sostituita con un puntatore al riassunto salvato in `.veles/memory/sessions/`. La
cronologia completa rimane sempre in `memory.db` — solo la finestra in memoria viene
compressa, quindi su disco è senza perdite.

## Perché conta

Poiché la memoria è strutturata e il ciclo gira di continuo, un progetto Veles
diventa **più utile quanto più lo usi** — apprende le tue convenzioni, evita errori
ripetuti e fonda le risposte su ciò che ha effettivamente visto.
