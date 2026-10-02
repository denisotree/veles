# Layout pack e la LLM-Wiki

> 🌐 **Lingue:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · **Italiano** · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

Un **layout pack** definisce come sono organizzati i *contenuti utente* di un
progetto — quali directory esistono, in quali l'agente può scrivere e quali
operazioni offre. Il default è **`bare`**, che non aggiunge alla tua directory
altro che `.veles/` e `AGENTS.md`. La **LLM-Wiki** è un'opzione del registry di
estensioni, **non** un principio centrale di Veles.

## Cos'è un layout pack

Un layout pack è una directory con un manifest `layout.toml` (più eventuali file di
skill e template). Il manifest dichiara:

- **Zone scrivibili** — directory in cui l'agente può scrivere contenuti
  (applicate a ogni `write_file`).
- **Zone in sola lettura** — materiale che l'agente legge ma non modifica mai.
- **Operazioni** — flussi di lavoro nominati, distribuiti come skill dentro il pack.
- **Scaffold** (`[layout.scaffold]`) — ciò che `veles init` crea: directory
  e un template opzionale `AGENTS.md` (`{name}` viene sostituito).
- **Engine** (`[layout.engines]`) — quale macchinario di contenuto il pack
  richiede. Un engine è fornito da un modulo (il modulo `wiki` del registry fornisce
  `wiki`). Senza di esso, nel progetto non esistono strumenti wiki, né recall wiki,
  né iniezione di INDEX.
- **File di contesto** (`context_file`) — un file iniettato nel system prompt stabile
  dell'agente (la LLM-Wiki usa `INDEX.md`).

## Pack disponibili

| Pack | Provenienza | Cosa produce `veles init --layout <name>` |
|---|---|---|
| `bare` *(default)* | integrato | Nessuno scaffold di contenuto — per repository di codice e lavoro a forma libera. Le scritture sono permissive all'interno della radice del progetto (sempre soggette alla scala di fiducia). |
| `llm-wiki` | registry (`public:official/llm-wiki`, porta il modulo `wiki`) | La [LLM-Wiki in stile Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (sola lettura per convenzione, non imposta), `wiki/` (scrivibile dall'agente), `INDEX.md` iniettato nel prompt, le skill `ingest`/`query`/`lint`/`organize`/`structure_design`, l'engine wiki attivo, `veles add` e `/wiki`. Un prompt comportamentale dichiarato dal layout (`templates/behaviour.md`) porta la disciplina sources/wiki e le regole di migrazione/patch del log. |
| `notes` | registry (`public:official/notes`) | Una singola directory piatta `notes/` in cui l'agente scrive. Nessun macchinario wiki. |

`veles init` in un terminale chiede quale pack usare (quelli installati e quelli nei
tuoi registry); scegliendone uno non installato si offre di installarlo.
`veles registry install llm-wiki` lo installa in anticipo.

## Progetti precedenti alla 1.2.3

Un progetto il cui layout non è installato (un progetto `llm-wiki` dopo l'aggiornamento,
o uno senza chiave `layout` — erano tutti progetti wiki) si apre comunque. In un
terminale, `veles` e `veles run` offrono di installare il pack (con l'engine di cui ha
bisogno) con un'unica conferma; altrove — il daemon, i canali, gli altri verbi — Veles
stampa una volta il comando di installazione e lavora senza la wiki. Nulla in `wiki/`
viene toccato.

## Layout personalizzati

Inserisci un pack in `~/.veles/layouts/<name>/layout.toml` (globale dell'utente) o
`<project>/.veles/layouts/<name>/` (locale al progetto; oscura i pack utente e
builtin con lo stesso nome) e passa `veles init --layout <name>`. Il pack `notes` del registry
è un esempio minimo da copiare. Un pack che richiede un engine che nessun modulo
installato fornisce riceve la stessa offerta di installazione. Puoi anche descrivere le convenzioni in `AGENTS.md` —
il layout fa rispettare le zone, AGENTS.md guida il comportamento.

## Cosa *non* è

Il layout governa **solo i tuoi contenuti**. La memoria di progetto di Veles —
`memory.db` più l'albero di artefatti `.veles/memory/` (insight, digest di sessione,
proposte, il giornale delle operazioni di sistema) — è lato sistema e funziona in
modo identico sotto qualsiasi layout. Cambiare layout non tocca mai il ciclo di
apprendimento, le sessioni o i registri. Vedi [architettura](architecture.md) e
[layout del progetto](../reference/project-layout.md).
