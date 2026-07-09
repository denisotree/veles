# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <b>Italiano</b> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**Un framework minimale per agenti da CLI che diventa più intelligente a ogni sessione.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="REPL di Veles — poni una domanda e ottieni una risposta fondata sulla memoria del progetto stesso" width="800">
</p>

A differenza degli strumenti di chat che ripartono da zero ogni volta, Veles mantiene una **memoria di progetto strutturata** — insight, regole e conoscenza curata che si accumulano attraverso le sessioni e rendono l'agente sempre più utile più a lungo lo usi. Il modo in cui sono organizzati i tuoi *contenuti* è modulare: una wiki LLM in stile Karpathy come impostazione predefinita, note piatte, oppure nessuna struttura per i repository di codice. Costruito in modo pulito: niente god-file, niente vendor lock-in, niente sincronizzazione cloud.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (just run `veles` with no subcommand)
```

---

## Perché Veles?

**Memoria che si accumula** — Ogni sessione viene distillata dal Curator nella memoria di progetto (insight, regole comportamentali, riepiloghi di sessione in `.veles/`). L'agente richiama automaticamente i fatti rilevanti e le decisioni passate — così smetti di rispiegare lo stesso contesto. La memoria funziona con *qualsiasi* layout di contenuti.

**Layout di contenuti modulari** — `veles init` predispone come impostazione predefinita una wiki LLM in stile Karpathy; `--layout notes` crea una directory piatta di note; `--layout bare` non aggiunge alcuna struttura (ideale per i repository di codice). I pacchetti di layout personalizzati sono un singolo file TOML in `~/.veles/layouts/`.

**Routing indipendente dal provider** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp, oppure il tuo abbonamento alla CLI `claude`/`gemini`. Tipi di attività diversi (pianificazione, compressione, insight) possono essere instradati verso modelli diversi.

**Skill che si accumulano** — Blocchi di prompt riutilizzabili diventano strumenti dell'agente. Promuovi una skill da un progetto al livello utente globale ed è disponibile ovunque. La deduplica integrata individua le skill quasi duplicate prima che divergano.

**Local-first + isolato** — Niente telemetria, niente sincronizzazione cloud. L'agente vede solo la directory del progetto attivo. La scala di fiducia chiede conferma per ogni chiamata a uno strumento sensibile; pre-autorizza per la CI.

**Modulare, non monolitico** — Un core minimale (memoria, ciclo dell'agente, protocollo dei provider, registro degli strumenti). Tutto il resto — daemon, gateway Telegram, deep research, scheduler dei job — è un modulo opzionale e caricabile.

---

## Avvio rapido

**Requisiti:** Python 3.13+, macOS / Linux (Windows con supporto best-effort). Installa prima [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

In alternativa apri la REPL interattiva (il semplice `veles` fa lo stesso):

```bash
veles
```

Al primo avvio, una procedura guidata di configurazione ti accompagna nella scelta della lingua preferita, del provider LLM, della chiave API, del modello predefinito, del tema colore e se inizializzare un progetto nella directory corrente.

---

## Provider

| Provider | Variabile d'ambiente | Note |
|---|---|---|
| **OpenRouter** *(consigliato)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — una chiave, centinaia di modelli |
| Anthropic | `ANTHROPIC_API_KEY` | API diretta |
| OpenAI | `OPENAI_API_KEY` | API diretta |
| Gemini | `GEMINI_API_KEY` o `GOOGLE_API_KEY` | API diretta |
| CLI `claude` | — | Usa il tuo abbonamento Claude; nessuna chiave API necessaria |
| CLI `gemini` | — | Usa il tuo abbonamento Gemini; nessuna chiave API necessaria |
| Ollama | — | Modelli locali, `http://localhost:11434/v1` |
| llamacpp | — | Modelli locali, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | Qualsiasi endpoint compatibile con OpenAI |

Sovrascrivi per singola esecuzione:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

Memorizza le chiavi API nel portachiavi del sistema operativo invece che nelle variabili d'ambiente:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## Flusso di lavoro principale

### Scegli un layout di contenuti

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

La memoria propria dell'agente (insight, regole, riepiloghi di sessione in `.veles/`) funziona in modo identico con ogni layout. I pacchetti personalizzati sono un singolo `layout.toml` in `~/.veles/layouts/<name>/`.

### Costruisci una base di conoscenza (layout llm-wiki)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Base di conoscenza di Veles — acquisisce una fonte in una pagina wiki, poi poni una domanda e ottieni una risposta che la cita" width="800">
</p>

Il Curator viene eseguito automaticamente dopo le sessioni. L'estrazione degli insight intercetta frasi come "preferire sempre X" o "non fare mai Y" e le scrive come insight di progetto persistenti.

### Deep research

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

Scompone la domanda in sotto-domande parallele, esplora ciascuna e sintetizza un report strutturato.

### Obiettivi a lungo termine

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### Job pianificati

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## Routing dei modelli (Ensemble)

Instrada tipi di attività diversi verso modelli diversi — imposti una volta e dimentichi.

**Tramite CLI:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**Tramite linguaggio naturale in `AGENTS.md`:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## Skill e moduli

Le **Skill** sono blocchi di prompt riutilizzabili (`SKILL.md`) che diventano automaticamente strumenti dell'agente.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

I **Moduli** sono plugin Python che possono agganciarsi al ciclo di vita dell'agente (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) e porre il veto alle chiamate agli strumenti.

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## Sessione interattiva (REPL)

```bash
veles                        # new session (bare `veles` launches the interactive REPL)
veles -c                     # continue the most recent session in this project
veles --resume <id>          # resume a specific session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="REPL di Veles — ispettori slash (/status, /context), cambio di modalità e palette dei comandi" width="800">
</p>

I comandi slash mostrano tutto in tempo reale — `/status`, `/tokens`, `/context`, `/mode`, `/help` — e `Shift+Tab` cicla tra le modalità (auto / planning / writing / goal).

| Tasto | Azione |
|---|---|
| `Enter` | Invia il messaggio |
| `Shift+Enter` | A capo nel compositore |
| `Ctrl+I` | Attiva/disattiva l'ispettore dell'attività degli strumenti |
| `Ctrl+R` | Overlay di selezione della sessione |
| `Ctrl+X Ctrl+E` | Apre `$EDITOR` sulla bozza corrente |
| `Tab` | Autocompletamento dei comandi slash |
| `Ctrl+D` | Esci |

Comandi slash: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` e altri.

---

## Daemon + Telegram

Esegui Veles come daemon persistente con un'API HTTP/WebSocket. In una directory di progetto nuova, `veles daemon start` ti guida attraverso la configurazione — inizializza il progetto, abilita il daemon e **collega un canale**: prima scegli un *tipo* di canale (Telegram è oggi l'unica piattaforma, ma il selettore è il punto di aggancio su cui si registrano i nuovi canali), poi compila i campi di quel canale (token del bot, whitelist). Non è necessario aprire prima la TUI.

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — procedura guidata che avvia il daemon e collega un canale Telegram (prima il tipo di canale, poi il suo token e la whitelist)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

Il semplice `veles daemon` apre un pannello di controllo dal vivo — un albero progetto → daemon → canali. Avvia, ferma, riavvia o elimina i daemon e aggiungi/rimuovi canali (lo stesso flusso con il tipo di canale per primo, tasto `c`) su ogni progetto, tutto dalla tastiera:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — TUI pannello di controllo: un albero progetto → daemon → canali con avvio/arresto/riavvio/eliminazione e gestione inline dei canali" width="800">
</p>

La stessa procedura guidata per i canali è disponibile anche in modo autonomo (`veles channel add`) su un progetto già in esecuzione.

Endpoint API: `POST /v1/runs` per inviare un prompt, `WS /v1/runs/{id}/events` per ricevere la risposta in streaming, `GET /v1/sessions` per elencare le sessioni. Tutti tranne `GET /v1/health` richiedono `Authorization: Bearer <token>` (generane uno con `veles daemon token add <name>`).

Ogni utente Telegram ottiene una sessione persistente. Usa `veles channel list-sessions` / `reset-session` per gestire le associazioni.

---

## Multi-progetto

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## Fiducia e sicurezza

Ogni chiamata a uno strumento sensibile (esecuzione di shell, scrittura di file, fetch di URL) chiede conferma:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

Pre-autorizza per la CI o per esecuzioni autonome estese:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

L'agente vede solo la directory del progetto attivo — gli altri progetti, le fughe tramite symlink e l'attraversamento `..` sono bloccati.

---

## Export / Import

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## Riferimento CLI

| Comando | Scopo |
|---|---|
| `veles init [name]` | Crea un nuovo progetto |
| `veles run "<prompt>"` | Esecuzione dell'agente a turno singolo |
| `veles` | REPL interattiva (nessun sottocomando) |
| `veles add <file\|url>` | Acquisisce una fonte → pagine wiki tematiche |
| `veles organize` | Riorganizza i contenuti del progetto secondo il layout attivo (proponi e applica) |
| `veles research "<question>"` | Ricerca approfondita multi-angolo |
| `veles curate` | Consolida le sessioni nella wiki |
| `veles sessions {list,show,delete,search}` | Gestione delle sessioni |
| `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}` | Gestione delle skill |
| `veles tool {list,show,promote,approve}` | Gestione degli strumenti (`approve` autorizza gli strumenti auto-generati) |
| `veles module {list,add,remove}` | Gestione dei plugin |
| `veles browse {modules,skills}` | Cerca nei registri curati di moduli / skill |
| `veles route {show,set,reset,refresh}` | Routing dei modelli |
| `veles schema {validate,edit}` | Valida / modifica AGENTS.md |
| `veles self-doc` | Genera l'auto-documentazione del progetto |
| `veles layout {sync}` | Manutenzione del layout-pack |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Obiettivi a lungo orizzonte |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Job pianificati |
| `veles dream` | Ciclo di consolidamento della memoria in background |
| `veles project {list,add,remove,switch}` | Registro multi-progetto |
| `veles subproject {init,list,switch,remove,suggest}` | Progetti figli |
| `veles trust {list,set,revoke,clear}` | Concessioni di fiducia |
| `veles autopilot {enable,disable,status}` | Bypass temporaneo della fiducia |
| `veles secret {set,get,list,delete}` | Segreti nel portachiavi del sistema operativo |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | Daemon HTTP/WS |
| `veles channel {list,run,list-sessions,reset-session,add,remove}` | Gateway per canali esterni |
| `veles mcp {list,test}` | Server MCP esterni |
| `veles models <provider>` | Elenca i modelli del provider |
| `veles doctor` | Controlli di integrità |
| `veles export / import` | Backup e trasferimento del progetto |

Ogni comando ha `--help`.

---

## Documentazione

Documentazione completa — organizzata secondo Diátaxis (tutorial · guide pratiche · riferimento · spiegazione):

- **Italiano:** [`docs/it/index.md`](docs/it/index.md)

Altre lingue: usa il selettore 🌐 in cima a qualsiasi pagina della documentazione.

---

## Contribuire

I contributi sono molto graditi — Veles è **progettato per essere esteso**. Il core rimane piccolo (ciclo dell'agente + memoria di progetto + protocollo dei provider); quasi tutto il resto è un punto di estensione modulare, quindi aggiungere una funzionalità raramente significa toccare il core:

- **Adapter per provider** (`src/veles/adapters/`) — collega un nuovo backend di modelli.
- **Skill** — blocchi di prompt e strumenti riutilizzabili con ereditarietà `extends:`, promuovibili da un progetto al livello utente globale.
- **Strumenti** — Python tipizzato che l'agente scrive e riutilizza, sotto `<project>/.veles/tools/`.
- **Pacchetti di layout** — un singolo `layout.toml` in `~/.veles/layouts/<name>/` definisce un intero layout di contenuti.
- **Hook dei moduli** — osservabilità, logging e policy tramite gli hook `pre_turn` / `post_turn` (`src/veles/core/modules.py`).
- **Canali e server MCP** — nuovi gateway e fonti di strumenti esterne.
- **Locale** — traduzioni in `src/veles/locales/`.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

Il codice è deliberatamente scomposto — responsabilità singola, niente god-file. Leggi [`CONTRIBUTING.md`](CONTRIBUTING.md) per le convenzioni e [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) prima di aprire una PR. Buoni primi contributi: adapter per provider, skill di flusso di lavoro, hook dei moduli e file di locale.

---

## Licenza

Apache 2.0 con concessione di brevetto — vedi [`LICENSE`](LICENSE) e [`NOTICE`](NOTICE).
