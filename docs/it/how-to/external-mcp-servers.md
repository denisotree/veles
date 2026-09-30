# Come collegare server MCP esterni

> 🌐 **Lingue:** [English](../../en/how-to/external-mcp-servers.md) · [简体中文](../../zh-CN/how-to/external-mcp-servers.md) · [繁體中文](../../zh-TW/how-to/external-mcp-servers.md) · [日本語](../../ja/how-to/external-mcp-servers.md) · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · [Français](../../fr/how-to/external-mcp-servers.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/external-mcp-servers.md) · [Português (PT)](../../pt-PT/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · [العربية](../../ar/how-to/external-mcp-servers.md) · [हिन्दी](../../hi/how-to/external-mcp-servers.md) · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

Veles è un **client** [MCP](https://modelcontextprotocol.io/): può connettersi a
server MCP esterni ed esporre i loro tool all'agente come se fossero integrati
(GitHub, documentazione di librerie, ricerca web, i tuoi servizi, …).

## Configurare un server

Aggiungi un blocco `[mcp.servers.<name>]` a `<project>/.veles/config.toml` (oppure al
file globale dell'utente `~/.veles/config.toml`). Il `<name>` deve corrispondere a
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` — diventa parte del nome di ciascun tool. Sono supportati tre
transport: `stdio` (default), `http`, `sse`.

| Chiave | Transport | Default | Scopo |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (richiesto) | — | l'eseguibile da lanciare — **solo il programma, non i suoi argomenti** |
| `args` | stdio | `[]` | lista di argomenti, un token per elemento |
| `env` | stdio | `{}` | ambiente aggiuntivo per il sottoprocesso (unito sopra l'ambiente ereditato) |
| `url` | http/sse (richiesto) | — | l'endpoint del server |
| `timeout_s` | — | `120` | budget per una singola chiamata di tool |
| `connect_timeout_s` | — | `30` | budget per la connessione iniziale |
| `enabled` | — | `true` | imposta `false` per mantenere la voce ma saltare la connessione |

I valori stringa in `command`, `args`, `env` e `url` interpolano `${VAR}` dall'ambiente
(una variabile non impostata diventa una stringa vuota con un avviso) — tieni i
segreti fuori dal file.

> **`command` vs `args`.** Veles esegue il programma direttamente (senza shell), quindi
> l'eseguibile e i suoi argomenti sono campi **separati**. Scrivi
> `command = "npx"`, `args = ["-y", "pkg"]` — **non** `command = "npx -y pkg"`.

### stdio (sottoprocesso locale)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

Un server che gestisci tu stesso funziona allo stesso modo — fai puntare `command`/`args` ad esso:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### Un server che richiede una chiave API (context7)

[Context7](https://context7.com) fornisce documentazione di librerie sempre aggiornata. Passa la
chiave come argomento in modo che `${VAR}` la mantenga fuori dal file:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse (remoto)

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **Nessun header personalizzato (per ora).** I transport `http`/`sse` inviano solo l'`url` —
> Veles non può allegare un header `Authorization`. Per un server remoto che richiede una
> chiave, preferisci la sua variante `stdio` (es. `npx`) con la chiave in `args`/`env`, oppure un
> endpoint che accetti la chiave nell'URL.

## Nascondere tool specifici

Imposta `[mcp] disabled_tools` — una tabella che mappa ciascun server ai nomi dei tool da saltare:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## Approvare, ispezionare e testare

```bash
veles mcp approve github    # review the recipe, type `yes` — the server may now start
veles mcp list              # every configured server: transport, approved, status, tool count
veles mcp test github       # connect to one server and list its tools
```

Un server parte solo dopo che hai approvato la sua ricetta esatta. `veles mcp approve`
mostra l'intera tabella — `command`, `args`, i valori di `env` (un `PATH` lì decide
quale binario viene eseguito; i riferimenti `${VAR}` compaiono come scritti), `url`,
`transport` e qualsiasi altra chiave — e registra un hash della tabella così com'è in
`config.toml`, prima dell'espansione di `${VAR}`: ruotare un token mantiene quindi
l'approvazione, mentre qualsiasi modifica alla tabella (un progetto clonato, un
argomento cambiato) porta il server allo stato `changed` e ne impedisce l'avvio finché
non lo approvi di nuovo. L'approvazione copre la riga di comando; i file che esegue dal
progetto (uno script in `args`) non sono bloccati — rivedi anche quelli. Le
approvazioni si trovano in `~/.veles/mcp-approvals.json`. `veles registry install` di
un'estensione MCP mostra la stessa ricetta nella sua conferma e la approva; `veles
registry uninstall` la revoca.

`veles mcp list` termina sempre con 0 — è un ispettore, non un controllo di stato; non
avvia mai un server non approvato. `veles mcp test` termina con 1 quando il server non
è approvato o la connessione fallisce, e con 2 per un nome di server sconosciuto.

## Come appaiono i tool

Una volta configurati e approvati, i server vengono montati **automaticamente** al
successivo avvio di `veles run` / TUI / daemon — non c'è un flag separato "abilita
MCP". Un server non approvato viene saltato con un avviso per processo. Ogni tool entra nel registry normale come `mcp_<server>_<tool>`
ed è richiamabile dall'agente come qualsiasi tool integrato. Gli schemi vengono sanificati (limiti di
nome/lunghezza, rimozione dei caratteri di controllo) così che un server non affidabile non possa iniettare nel prompt.
Gli hint dei tool si mappano sulla scala di trust: i tool distruttivi chiedono sempre conferma, i tool
in sola lettura sono senza richiesta, tutto il resto passa attraverso il consueto
flusso di [trust](security-and-permissions.md) — concedi un'approvazione permanente con
`veles trust set` se non vuoi che ti venga chiesto ogni volta.

## Gestione dei fallimenti

Un server che non riesce a connettersi — un `command` mancante, un `url` errato o qualsiasi voce
non valida — viene registrato come avviso e saltato. Non blocca mai l'avvio o l'agente.
Riesegui `veles mcp list` per vedere lo stato e l'errore.
