# Riferimento CLI

> 🌐 **Lingue:** [English](../../en/reference/cli.md) · [简体中文](../../zh-CN/reference/cli.md) · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · [Español](../../es/reference/cli.md) · [Français](../../fr/reference/cli.md) · **Italiano** · [Português (BR)](../../pt-BR/reference/cli.md) · [Português (PT)](../../pt-PT/reference/cli.md) · [Русский](../../ru/reference/cli.md) · [العربية](../../ar/reference/cli.md) · [हिन्दी](../../hi/reference/cli.md) · [বাংলা](../../bn/reference/cli.md) · [Tiếng Việt](../../vi/reference/cli.md)

Ogni comando, sottocomando e flag di Veles. Esegui `veles <command> --help` per
ottenere la firma autorevole e sempre aggiornata — questa pagina rispecchia i
parser degli argomenti in `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — salta la procedura guidata di configurazione iniziale anche se
  `~/.veles/config.toml` è assente (subordinato anche alla presenza di un TTY e a
  `VELES_NO_WIZARD=1`).
- Senza argomenti, `veles` avvia la [TUI](tui.md) interattiva.

La maggior parte dei comandi dell'agente accetta i [flag condivisi del ciclo
dell'agente](#shared-agent-loop-flags) e i [nomi dei provider](#provider-names)
elencati in fondo.

---

## Ciclo di vita del progetto

### `veles init [name]`
Crea un nuovo progetto Veles nella directory corrente (una directory di stato
`.veles/` + `AGENTS.md` + lo scaffold dei contenuti del layout pack scelto).

| Flag | Default | Scopo |
|---|---|---|
| `name` (posizionale) | basename della cwd | Nome del progetto |
| `--layout <name>` | `llm-wiki` | Layout pack per lo scaffold dei contenuti (`llm-wiki`, `notes`, `bare` o un pack personalizzato da `~/.veles/layouts/`) |
| `--force` | off | Ricrea `.veles/` anche se esiste già |

### `veles schema {validate,edit,fix}`
Convalida o modifica `AGENTS.md` (il file di contesto del progetto).

- `validate` — verifica la presenza delle sezioni H2 richieste.
- `edit` — apre `AGENTS.md` in `$EDITOR` (default `vi`), convalida all'uscita.
- `fix` — aggiunge interattivamente le sezioni mancanti tramite una procedura
  guidata LLM.

### `veles self-doc [refresh|show]`
Genera e visualizza l'auto-documentazione del progetto (`wiki/self-doc/overview.md`).
`veles self-doc` da solo mostra la pagina corrente; `refresh` la rigenera.

### `veles doctor`
Esegue controlli di integrità sullo stato globale dell'utente e sul progetto
attivo. Funziona con o senza un progetto attivo.

| Flag | Default | Scopo |
|---|---|---|
| `--json` | off | Emette un report JSON |
| `--strict` | off | Esce con codice diverso da zero in presenza di qualsiasi warning (gating CI) |

### `veles export {full,template} <path>`
Impacchetta il progetto in un bundle `.tar.gz`. Vedi [Backup e condivisione](../how-to/backup-and-share.md).

- `full <path>` — l'intero progetto (`.veles/` + `AGENTS.md`), esclusi gli effimeri di runtime.
- `template <path>` — sottoinsieme sanificato (schema + skill + moduli + pagine
  wiki non di sessione); rimuove `memory.db`, `sources/`, `sessions/`, le
  concessioni di `trust`, e redige le informazioni personali (PII) dal testo.

### `veles import <path>`
Ripristina un bundle creato da `veles export`.

| Flag | Default | Scopo |
|---|---|---|
| `path` (posizionale) | — | Percorso del bundle (`.tar.gz`) |
| `--into <dir>` | cwd | Directory di destinazione |
| `--force` | off | Sovrascrive un `.veles/` esistente nella destinazione |

---

## Esecuzione dell'agente

### `veles run "<prompt>"`
Esegue un singolo prompt end-to-end con persistenza della memoria e i trigger del
curator/apprendimento. Accetta tutti i [flag condivisi del ciclo
dell'agente](#shared-agent-loop-flags) più:

| Flag | Default | Scopo |
|---|---|---|
| `--resume <session_id>` | nuova sessione | Continua una sessione esistente |
| `--manager` | off | Decompone tramite il manager multi-agente (anche `VELES_MANAGER_MODE=1`) |
| `--verify` | off | Al termine, l'advisor instradato giudica la risposta; in caso di fallimento netto, riesegue sul modello più potente (anche `VELES_VERIFY_MODE=1`) |
| `--plan` | off | Modalità pianificazione: lettura/ricerca/bozza consentite, mutazioni bloccate |
| `--no-agents-md` | off | Non inietta `AGENTS.md` nel system prompt |
| `--no-index` | off | Non inietta `wiki/INDEX.md` |
| `--no-compress` | off | Disabilita la compressione del contesto a finestra scorrevole |
| `--no-curator` | off | Disabilita i trigger del curator per questa esecuzione |
| `--no-insights` | off | Disabilita l'estrazione degli insight a fine esecuzione |
| `--no-proposer` | off | Disabilita l'auto-trigger del proposer dei sottoprogetti |
| `--no-route-refresh` | off | Disabilita l'aggiornamento del routing NL da `AGENTS.md` |
| `--no-suggest-promote` | off | Disabilita il suggeritore di auto-promozione |
| `--compressor-model <id>` | instradato | Sovrascrive il modello di compressione |
| `--compress-threshold-tokens <n>` | `50000` | Dimensione della cronologia che attiva la compressione |

### `veles tui`
Apre la REPL interattiva. Vedi [Riferimento TUI](tui.md). Accetta i flag condivisi
del ciclo dell'agente, `--resume`, i flag `--no-*` di iniezione/compressione qui
sopra e:

| Flag | Default | Scopo |
|---|---|---|
| `--theme <name>` | config o `everforest` | Tema di colori (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
Legge una sorgente (un file locale o un URL `http(s)://`) e la sintetizza in una
pagina wiki. Accetta i flag condivisi del ciclo dell'agente.

### `veles curate`
Esegue un passaggio del curator: compatta le sessioni non elaborate in pagine
`wiki/sessions/`.

| Flag | Default | Scopo |
|---|---|---|
| `--limit <n>` | un piccolo default | Numero massimo di sessioni da elaborare in questa esecuzione |

Più i flag condivisi del ciclo dell'agente.

### `veles research "<question>"`
Ricerca approfondita: decompone in sotto-domande → esplora il web in parallelo →
sintetizza un report con citazioni.

| Flag | Default | Scopo |
|---|---|---|
| `--max-subquestions <n>` | `4` | Angolazioni di ricerca parallele |

Più i flag condivisi del ciclo dell'agente.

### `veles dream`
Esegue un ciclo di consolidamento della memoria in background (insight → dedup
delle skill → suggerimenti di promozione → lint della wiki, opzionalmente
consolidamento LLM).

| Flag | Default | Scopo |
|---|---|---|
| `--include-consolidation` | off | Esegue il costoso consolidamento LLM (richiede una chiave API) |
| `--dry-run` | off | Esegue tutti i passaggi ma salta le scritture in `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | Salta singoli passaggi |
| `--consolidation-model <id>` | instradato (ripiega su `anthropic/claude-haiku-4.5`) | Sovrascrive il modello di consolidamento |
| `--provider <name>` | instradato | Provider per il sub-agente di consolidamento (ometti per usare il provider instradato del progetto) |
| `--project-root <path>` | scoperto | Override del progetto |

---

## Conoscenza: skill, tool, moduli

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Sottocomando | Scopo |
|---|---|
| `list` | Elenca le skill del progetto attivo (con telemetria) |
| `show <name>` | Stampa il `SKILL.md` di una skill |
| `add <source> [--name N] [--scope project\|user] [-y]` | Installa da un URL git o da un percorso locale |
| `remove <name> [--scope project\|user] [-y]` | Elimina una skill installata |
| `promote <name> [--keep-telemetry]` | Copia una skill di progetto nello scope utente (`~/.veles/skills/`) |
| `demote <name> [-y]` | Copia una skill utente nel progetto attivo |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Trova skill quasi duplicate |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | Elenca le skill che soddisfano la soglia di auto-promozione |

### `veles tool {list,show,promote}`

| Sottocomando | Scopo |
|---|---|
| `list` | Elenca i tool catalogati nel `memory.db` di questo progetto |
| `show <name>` | Stampa il manifest + la telemetria di un tool |
| `promote <name> [-y]` | Sposta un tool di progetto in `~/.veles/tools/` (cross-progetto) |

### `veles module {list,show,add,remove}`

| Sottocomando | Scopo |
|---|---|
| `list` | Elenca i moduli installati |
| `show <name>` | Stampa il manifest di un modulo |
| `add <source> [--name N] [-y]` | Installa un modulo da un URL git o da un percorso locale |
| `remove <name> [-y]` | Elimina un modulo installato |

### `veles browse {modules,skills} [query]`
Sfoglia i registri curati.

| Flag | Default | Scopo |
|---|---|---|
| `query` (posizionale) | `""` | Filtro per sottostringa |
| `--source <url>` | canonico | Sovrascrive la sorgente del registro |
| `--json` | off | Emette JSON |

---

## Sessioni e memoria

### `veles sessions {list,show,delete,search}`

| Sottocomando | Scopo |
|---|---|
| `list [--limit n]` | Elenca le sessioni recenti (default 20) |
| `show <session_id>` | Stampa l'intera cronologia dei turni di una sessione |
| `delete <session_id>` | Elimina una sessione e i suoi turni |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Ricerca full-text (FTS5) sul contenuto dei turni |

---

## Multi-progetto

### `veles project {list,add,remove,switch}`

| Sottocomando | Scopo |
|---|---|
| `list` | Elenca i progetti registrati, dal più recente |
| `add <path> [--slug S]` | Registra una directory di progetto esistente |
| `remove <slug>` | Annulla la registrazione di un progetto (i file restano intatti) |
| `switch <slug>` | Stampa il percorso assoluto del progetto (usa `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Sottocomando | Scopo |
|---|---|
| `init <subdir> [--name N] [--description D]` | Crea + registra un sottoprogetto |
| `list` | Elenca i sottoprogetti del progetto attivo |
| `switch <slug>` | Stampa il percorso assoluto di un sottoprogetto |
| `remove <slug>` | Annulla la registrazione di un sottoprogetto |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Rileva cluster tematici e propone sottoprogetti |

---

## Routing e modelli

### `veles route {show,set,reset,refresh}`
Routing d'ensemble per task — quale `provider:model` gestisce ciascun tipo di task
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`). Vedi [routing per task](../how-to/per-task-routing.md).

| Sottocomando | Scopo |
|---|---|
| `show` | Stampa la tabella di routing risolta per il progetto attivo |
| `set <task> <provider:model>` | Fissa un task a una specifica |
| `reset [task]` | Ripristina un task (o tutti) ai default |
| `refresh [--force]` | Rianalizza i suggerimenti di routing in linguaggio naturale da `AGENTS.md` |

### `veles models <provider>`
Elenca i modelli di un provider. I provider cloud (openrouter/openai/gemini)
vengono messi in cache per 24h; i provider locali sono sempre live.

| Flag | Default | Scopo |
|---|---|---|
| `provider` (posizionale) | — | Uno dei [nomi dei provider](#provider-names) |
| `--refresh` | off | Bypassa la cache su disco (solo cloud) |
| `--json` | off | Emette `{provider, source, models}` come JSON |

---

## Task di lunga durata

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Obiettivi a lungo orizzonte con budget e checkpoint.

| Sottocomando | Scopo |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | Elenca gli obiettivi |
| `show <id> [--json]` | Mostra un obiettivo |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | Crea un obiettivo |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | Aggiunge un avanzamento |
| `pause <id>` / `resume <id>` | Metti in pausa / riprendi |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Completa / annulla |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Job dell'agente pianificati.

| Sottocomando | Scopo |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | Crea un job (schedule = cron, `<N><s\|m\|h\|d>` o timestamp ISO) |
| `list [--json]` / `show <id>` | Ispeziona i job |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Ciclo di vita |
| `history <id> [--limit n]` | Esecuzioni recenti |
| `tick` | Esegue in modo sincrono tutti i job scaduti una volta (nessun daemon necessario; accetta i flag del ciclo dell'agente) |

---

## Sicurezza e controllo degli accessi

### `veles trust {list,set,revoke,clear}`
Concessioni persistenti per i tool sensibili (`run_shell`, `write_file`,
`fetch_url`, …). Vedi [sicurezza](../how-to/security-and-permissions.md).

| Sottocomando | Scopo |
|---|---|
| `list` | Mostra le concessioni (scope utente + progetto) |
| `set <tool> [--scope project\|user]` | Concede un tool |
| `revoke <tool> [--scope project\|user\|both]` | Rimuove una concessione |
| `clear [--scope project\|user\|all]` | Cancella le concessioni in uno scope |

### `veles autopilot {enable,disable,status}`
Una finestra temporizzata in cui i prompt della scala di fiducia vengono
auto-consentiti.

| Sottocomando | Scopo |
|---|---|
| `enable --until <DUR>` | Apre una finestra (`+30m`, `+2h`, `+1d` o ISO `2026-05-12T18:00:00Z`) |
| `disable` | Chiude subito la finestra |
| `status` | Riporta se l'autopilot è attivo |

### `veles secret {set,get,list,delete}`
Segreti basati sul keychain del sistema operativo (chiavi API, token dei bot).

| Sottocomando | Scopo |
|---|---|
| `set <name> [value]` | Memorizza (ometti il valore per input interattivo / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Recupera (fallback su env per default) |
| `list` | Mostra quali segreti canonici sono configurati |
| `delete <name>` | Rimuove un segreto |

---

## Daemon e canali

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Avvia/controlla il daemon HTTP+WS. `veles daemon` da solo apre la TUI del
**selettore di daemon** (progetto → daemon → canali). Vedi
[esecuzione come daemon](../how-to/run-as-daemon.md).

| Sottocomando | Scopo |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Avvia un daemon (si stacca per default) |
| `stop [--name N]` / `status [--name N]` | Arresta / ispeziona |
| `list` | Elenca i daemon di tutti i progetti |
| `restart [target] [--name N]` | Arresta + riavvia sullo stesso host/porta |
| `delete <target> [-y]` | Arresta + rimuove dal registro |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Dichiara una sessione daemon con nome |
| `session list [--all]` / `session delete <name>` | Gestisce le sessioni con nome |
| `token add <name>` / `token list` / `token remove <name>` | CRUD dei bearer token |

`start` accetta anche i flag condivisi del ciclo dell'agente; per il daemon,
`--model` / `--provider` assumono come default la config del progetto e sono fissi
per tutta la durata del daemon.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
Gateway di chat esterni (Telegram, …) che dialogano con un daemon. Vedi
[connettere Telegram](../how-to/connect-telegram.md).

| Sottocomando | Scopo |
|---|---|
| `list` | Elenca le piattaforme di canale registrate + il conteggio delle sessioni |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | Avvia un gateway in primo piano |
| `list-sessions [--channel C]` | Mostra le mappature `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | Dimentica una mappatura (il prossimo messaggio parte da zero) |
| `add [--channel C] [--session S]` | Collega un canale a un daemon (procedura guidata; credenziali → keychain) |
| `remove <channel> [--session S]` | Rimuove un binding di canale |

---

## MCP (server di tool esterni)

### `veles mcp {list,test}`
Ispeziona i server MCP esterni configurati sotto `[mcp.servers.*]`. Vedi
[server MCP esterni](../how-to/external-mcp-servers.md).

| Sottocomando | Scopo |
|---|---|
| `list [--connect-timeout f]` | Mostra i server configurati, lo stato di connessione, il conteggio dei tool |
| `test <server>` | Si connette a un server ed elenca i suoi tool |

---

## Flag condivisi del ciclo dell'agente

Accettati da `run`, `add`, `tui`, `curate`, `research`, `job tick` e `daemon
start`:

| Flag | Default | Scopo |
|---|---|---|
| `--model <id>` | risolto dal modello `[provider]` del progetto → `default_model` utente (nessun default hardcoded) | ID del modello |
| `--provider <name>` | `openrouter` | Provider (vedi sotto) |
| `--max-tokens-total <n>` | `100000` | Budget cumulativo di token; `0` lo disabilita |
| `--max-iterations <n>` | `30` | Numero massimo di iterazioni di chiamata-tool per turno |
| `--stream` | off | Trasmette la risposta token per token |
| `--verbose` / `-v` | off | Avanzamento per turno su stderr |
| `--project-root <path>` | scoperto dalla cwd | Opera su un progetto altrove |

## Nomi dei provider

`openrouter` (default) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

I provider locali (`ollama`, `llamacpp`, `openai-compat`) non richiedono chiave
API. Vedi il [riferimento dei provider](providers.md) e
[configurare i provider](../how-to/configure-providers.md).
