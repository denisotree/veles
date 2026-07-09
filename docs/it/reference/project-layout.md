# Layout e stato del progetto

> 🌐 **Lingue:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · **Italiano** · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

Cosa crea `veles init`, dove Veles conserva lo stato e lo schema della memoria di progetto.

## Cosa produce `veles init`

La metà del contenuto utente dipende dal layout pack scelto (`--layout`,
default `llm-wiki`); la metà di stato `.veles/` è identica ovunque.

```
my-project/                  # veles init  (layout llm-wiki di default)
├── AGENTS.md                # contesto del progetto (iniettato nell'agente)
├── CLAUDE.md → AGENTS.md    # symlink, così una CLI `claude` recupera lo stesso contesto
├── GEMINI.md → AGENTS.md    # symlink, per una CLI `gemini`
├── sources/                 # materiale sorgente grezzo e immutabile (sola lettura per l'agente)
├── wiki/                    # la zona di conoscenza scrivibile dall'LLM
│   ├── concepts/ entities/ queries/ self-doc/ sessions/
└── .veles/                  # stato del progetto (non committare; gestito dalla macchina)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessioni, turni, insight, regole, telemetria
    ├── memory/              # gli artefatti di memoria dell'agente stesso:
    │   ├── LOG.md           #   journal append-only delle operazioni di sistema
    │   ├── insights/        #   viste renderizzate delle righe `insights`
    │   ├── sessions/        #   riepiloghi di compattazione
    │   └── proposals/       #   proposte di sottoprogetto / promozione di skill
    ├── jobs/                # output dei job pianificati
    └── skills/              # skill locali al progetto
```

Con `--layout notes` la metà del contenuto è una singola directory `notes/`; con
`--layout bare` non c'è alcuno scaffold di contenuto. `wiki/INDEX.md` (il
catalogo su richiesta) viene generato man mano che la wiki cresce; `config.toml`, `tools/`
e `plans/` compaiono sotto `.veles/` una volta che configuri qualcosa, un agente
scrive un tool o esegui un goal.

## Directory di stato

| Percorso | Scope | Da committare? |
|---|---|---|
| `<project>/AGENTS.md` + contenuto del layout (`wiki/`, `sources/`, `notes/`, …) | Contenuto del progetto | **Sì** — questa è la tua base di conoscenza |
| `<project>/.veles/` | Stato macchina del progetto (memoria, config, skill/tool locali) | No |
| `~/.veles/` | User-global: `config.toml`, concessioni di trust, skill/tool cross-project, layout pack, cache dei modelli, locale | No |

`VELES_USER_HOME` reindirizza `~` per l'albero user-global (test, sandbox).

## Memoria di progetto (`.veles/memory.db` + `.veles/memory/`)

La memoria di progetto di Veles è un **artefatto strutturato**, separato dal tuo
contenuto e indipendente dal layout. Il database SQLite (modalità WAL) è la
fonte di verità; `.veles/memory/` contiene il lato leggibile dall'uomo (viste
renderizzate degli insight, digest delle sessioni, proposte, il journal delle operazioni di sistema).
Tabelle chiave:

| Tabella | Contiene |
|---|---|
| `sessions`, `turns` | Cronologia della conversazione (una riga per turno) |
| `turns_fts` | Indice full-text sui turni (alimenta `veles sessions search`) |
| `insights`, `insights_fts`, `insight_refs` | Insight appresi (righe canoniche; le viste markdown sono rigenerabili) + link di dedup |
| `rules`, `rules_fts` | Regole di formato/fai/non-fare/preferenza iniettate nel prompt stabile |
| `skills`, `skill_uses`, `skill_tool_refs` | Registro delle skill + telemetria + link ai tool |
| `tools`, `tool_uses` | Registro dei tool + telemetria (conteggi di uso/successo/errore) |
| `project_tree` | Mappa dei file del progetto in cache + tag semantici per il ranking di rilevanza |

Vedi [Memoria di progetto e il ciclo di apprendimento](../explanation/project-memory-and-learning-loop.md)
per come queste vengono scritte e richiamate.

## Layout pack

`veles init --layout {llm-wiki|notes|bare|<custom>}` sceglie il layout del
contenuto; il pack possiede lo scaffold, il template di AGENTS.md, le zone scrivibili
e se il motore wiki (tool wiki, iniezione del prompt INDEX, recall
wiki) è attivo. Vedi
[layout pack e l'LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
