# Layout pack e la LLM-Wiki

> 🌐 **Lingue:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · **Italiano**

Un **layout pack** definisce come sono organizzati i *contenuti utente* di un
progetto — quali directory esistono, in quali l'agente può scrivere e quali
operazioni offre. Il default è la **LLM-Wiki**. Si tratta di un'opzione di
contenuto, **non** di un principio centrale di Veles.

## Cos'è un layout pack

Un layout pack è una directory con un manifest `layout.toml` (più eventuali file di
skill e template). Il manifest dichiara:

- **Zone scrivibili** — directory in cui l'agente può scrivere contenuti
  (applicate a ogni `write_file`).
- **Zone in sola lettura** — materiale che l'agente legge ma non modifica mai.
- **Operazioni** — flussi di lavoro nominati, distribuiti come skill dentro il pack.
- **Scaffold** (`[layout.scaffold]`) — ciò che `veles init` crea: directory
  e un template opzionale `AGENTS.md` (`{name}` viene sostituito).
- **Engine** (`[layout.engines]`) — quale macchinario di contenuto del core il pack
  attiva. Oggi esiste un solo engine: `wiki`. Senza di esso, nel progetto non
  esistono strumenti wiki, né recall wiki, né iniezione di INDEX.
- **File di contesto** (`context_file`) — un file iniettato nel system prompt stabile
  dell'agente (la LLM-Wiki usa `INDEX.md`).

## Pack builtin

| Pack | Cosa produce `veles init --layout <name>` |
|---|---|
| `llm-wiki` *(default)* | La [LLM-Wiki in stile Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (sola lettura), `wiki/` (scrivibile dall'agente), `INDEX.md` iniettato nel prompt, le skill `ingest`/`query`/`lint`, l'engine wiki attivo. |
| `notes` | Una singola directory piatta `notes/` in cui l'agente scrive. Nessun macchinario wiki. |
| `bare` | Nessuno scaffold di contenuto — per repository di codice e lavoro a forma libera. Le scritture sono permissive all'interno della radice del progetto (sempre soggette alla scala di fiducia). |

## Layout personalizzati

Inserisci un pack in `~/.veles/layouts/<name>/layout.toml` (globale dell'utente) o
`<project>/.veles/layouts/<name>/` (locale al progetto; oscura i pack utente e
builtin con lo stesso nome) e passa `veles init --layout <name>`. Il builtin `notes`
è l'esempio minimo da copiare. Puoi anche descrivere le convenzioni in `AGENTS.md` —
il layout fa rispettare le zone, AGENTS.md guida il comportamento.

## Cosa *non* è

Il layout governa **solo i tuoi contenuti**. La memoria di progetto di Veles —
`memory.db` più l'albero di artefatti `.veles/memory/` (insight, digest di sessione,
proposte, il giornale delle operazioni di sistema) — è lato sistema e funziona in
modo identico sotto qualsiasi layout. Cambiare layout non tocca mai il ciclo di
apprendimento, le sessioni o i registri. Vedi [architettura](architecture.md) e
[layout del progetto](../reference/project-layout.md).
