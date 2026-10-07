# Come gestire skill, strumenti e moduli

> 🌐 **Lingue:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles accumula capacità nel tempo. Le **skill** sono workflow riutilizzabili, gli
**strumenti** sono azioni eseguibili, i **moduli** sono plug-in opzionali. Ciascuno
vive a due livelli: locale al progetto (`<project>/.veles/`) e globale all'utente
(`~/.veles/`). Per i concetti, vedi [skill e strumenti](../explanation/skills-and-tools.md).

## Skill

Una skill è un `SKILL.md` (frontmatter + corpo del prompt) che l'agente può
invocare come uno strumento.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Promozione / retrocessione tra i livelli

Una skill che si rivela utile in un progetto può passare al livello utente in modo
che ogni progetto la veda (o viceversa):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Trovare duplicati e candidati alla promozione

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Strumenti

Gli strumenti sono catalogati nel `memory.db` del progetto con la telemetria
d'uso. Veles può scrivere i propri strumenti mentre lavora; li gestisci con:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Gli strumenti sensibili (`run_shell`, `write_file`, `fetch_url`, …) sono protetti
dalla [scala di fiducia](security-and-permissions.md).

## Moduli

Un modulo è codice Python (`module.toml` + un entrypoint) che gira dentro Veles —
aggiunge capacità opzionali (provider di memoria, embedding, vision, STT) senza
appesantire il core. L'installazione di uno richiede conferma per impostazione
predefinita, e viene caricato a ogni esecuzione solo finché i suoi file corrispondono a
ciò che hai approvato (vedi [mantenere le installazioni
affidabili](../../en/how-to/extension-registries.md#keep-installs-honest)).

```bash
veles module list                              # both scopes, with a `scope` column
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # install to ~/.veles/modules/, all projects
veles module show <name> [--user]             # manifest + sha256 dei file
veles module remove <name> [--user]
veles module approve <name> [--user]          # digita `yes` in un terminale
veles module approve <name> --sha256 <hash>   # senza terminale: l'hash che hai revisionato
```

I moduli vivono su due livelli, come skill e strumenti: locali al progetto
(`<project>/.veles/modules/`) e globali dell'utente (`~/.veles/modules/`, caricati in
ogni progetto). Un modulo utente passa dallo stesso controllo di approvazione di uno di
progetto, e il controllo viene eseguito prima del confronto dei nomi. Se un modulo di
progetto e uno utente hanno lo stesso nome, si carica il modulo di progetto approvato e
Veles avvisa che quello utente è oscurato; un modulo di progetto non approvato viene
saltato (l'avviso ne indica la directory) e si carica quello utente. Due moduli
approvati dello stesso livello con lo stesso nome — si carica il primo (ordinato per
directory), gli altri avvisano e vengono saltati. `veles module
{show,approve,remove}` accettano il nome del manifest (quello che mostra `list`) e
rifiutano un nome dichiarato da più di una directory del livello, elencandole; `veles
module add` rifiuta di installare un modulo il cui nome è già dichiarato da un'altra
directory del livello.

### Scrivere un modulo che aggiunge un provider di memoria

L'entrypoint `register(api)` di un modulo può chiamare
`api.add_memory_provider(name, factory)` per collegare una fonte di memoria esterna al
recall. `name` deve corrispondere a una sezione `[memory.external.<name>]` di
`~/.veles/config.toml`; a `factory` viene passata quella sezione (un `dict`) e deve
restituire un oggetto che implementa il protocollo `MemoryProvider` di Veles
(`veles.core.memory.provider`), oppure `None` per saltare il provider:

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

Un provider che implementa anche `ingest(title, body, *, insight_id) -> bool` (il
protocollo `IngestingMemoryProvider`) riceve anche le scritture di Veles, non solo le
letture. Se due moduli registrano lo stesso nome di provider, il caricamento del
secondo fallisce — viene saltato con un avviso, nulla resta registrato a metà. Una
sezione configurata in `config.toml` il cui modulo non è installato stampa un solo
avviso con il comando di installazione; il recall continua a funzionare senza.

Il registro include Honcho, Mem0 e Supermemory come moduli provider pronti all'uso —
installali con `veles registry install --user {honcho,mem0,supermemory}`, poi esegui il
comando `uv tool install veles-ai --with '<package>'` che l'installazione stampa (ognuno
dichiara un SDK — `mem0ai>=2.0`, `honcho-ai>=2.5`, `supermemory>=3.62` — che Veles non
installa mai al posto tuo), e compila la sezione `[memory.external.<name>]`
corrispondente:

- **mem0**: `api_key`, `user_id`, `agent_id` opzionale (richiama anche i ricordi di
  quell'agente) e `host`. La telemetria dell'SDK è disattivata di default; ogni recall
  fa una richiesta `GET /v1/ping/` in più.
- **supermemory**: `api_key`, `user_id` opzionale (inviato come `container_tag` della
  ricerca) e `base_url`.
- **honcho**: `api_key`, `workspace_id`, `peer_id` opzionale (cerca solo nei messaggi
  di quel peer) e `base_url`. Ogni recall esegue un get-or-create del workspace — crea
  `workspace_id` se non esiste già.

## Scopri di più

Cerca nei registri connessi:

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```
