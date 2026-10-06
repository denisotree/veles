# Come gestire la sicurezza: fiducia, autopilot, segreti

> 🌐 **Lingue:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

Veles protegge le azioni pericolose dietro una **scala di fiducia**, isola
l'accesso ai file in una sandbox e conserva i segreti nel keychain del sistema
operativo. Per la motivazione, vedi [fiducia e sandbox](../explanation/trust-and-sandbox.md).

## La scala di fiducia

Gli strumenti sensibili (`run_shell`, `write_file`, `fetch_url`, …) chiedono
conferma prima dell'esecuzione. Tu scegli: consentire **una volta**, **sempre per
questo progetto**, **sempre ovunque**, oppure **rifiutare**. Le autorizzazioni
persistono, così non ti viene richiesto di nuovo.

Gestisci le autorizzazioni senza attendere una richiesta:

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

Alcune azioni sono **sempre confermate** anche con un'autorizzazione — eliminare
file, recuperare URL, installare una nuova skill/strumento/modulo, collegare un
canale e scrivere al di fuori del progetto.

## Autopilot — un bypass a tempo limitato

Per un'esecuzione non presidiata (un batch notturno), apri una finestra in cui le
richieste di fiducia vengono auto-consentite:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Ogni azione in autopilot viene registrata per una revisione successiva. I contesti
non interattivi (daemon, batch) rifiutano per impostazione predefinita a meno che
l'autopilot non sia attivo.

## Segreti

Le chiavi API e i token dei bot risiedono nel keychain del sistema operativo, mai
nei file di configurazione:

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # a key for one project only
```

La ricerca ricade sulla [variabile d'ambiente](../reference/environment-variables.md)
corrispondente a meno che tu non passi `--no-env-fallback`.

## La sandbox

Gli strumenti possono leggere all'interno del progetto attivo, di `~/.veles/skills/` e
di `~/.veles/locales/`, e scrivere solo dentro il progetto — oppure solo nelle zone
scrivibili del layout, quando questo le dichiara. Sovrascrivi le radici per
configurazioni avanzate con `VELES_SANDBOX_ROOTS` (separate da `:`). I recuperi di URL
mantengono una deny-list anti-SSRF; `VELES_FETCH_ALLOW_PRIVATE=1` rimuove il blocco
della rete privata.

Dentro la `.veles/` del progetto, gli strumenti per i file dell'agente possono scrivere
solo in `skills/`, `tools/`, `tmp/`, `plans/`, `memory/` e `artifacts/`. Tutto il resto
— `trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`, `memory.db` —
cambia solo tramite i comandi `veles` e gli strumenti propri di Veles. Gli strumenti per
i file rifiutano anche qualsiasi altra directory `.veles/` del progetto (quella di un
sottoprogetto, o una che l'agente pianterebbe in `wiki/`) a qualsiasi profondità. Così,
con i suoi strumenti per i file l'agente non può concedersi fiducia da solo né aggiungere
codice che Veles eseguirebbe (uno strumento che scrive in `.veles/tools/` viene caricato
solo dopo che ne hai approvato il file). Anche le altre grafie dello stesso file
(maiuscole/minuscole, `..`, un symlink) vengono rifiutate.

I file che vengono eseguiti senza un comando esplicito o che guidano una CLI di agente —
tutto ciò che sta sotto `.git/`, `.githooks/`, `.claude/`, `.gemini/`, `.agents/`,
`.codex/`, `.vscode/`, `.devcontainer/`, `.husky/`, e `.envrc`, `.mcp.json`,
`.pre-commit-config.yaml`, `lefthook.yml`, a qualsiasi profondità, più la directory
`core.hooksPath` del repository e la destinazione di un `.git` che è un symlink — gli
strumenti per i file dell'agente li scrivono solo dopo che confermi quella scrittura. Le
concessioni di fiducia e l'autopilot non la coprono; il daemon chiede nel canale, e
un'esecuzione batch senza nessuno a cui chiedere rifiuta.

I provider `claude-cli`, `codex` e `antigravity-cli` girano come un modello con i soli strumenti
di Veles: i loro strumenti di shell, modifica file e web, le impostazioni e gli hook di
`.claude/` del progetto e gli altri server MCP non si applicano, e ogni strumento di
Veles che chiamano passa per la scala di fiducia qui sopra (lì nessuno può rispondere a
una richiesta, quindi tutto ciò che non è già concesso viene rifiutato). La loro config
MCP si trova in `.veles/tmp/delegate-<pid>/`, una per ogni processo in esecuzione, che gli
strumenti per i file dell'agente non possono scrivere. `agy` gira in un workspace
temporaneo fuori dal progetto, sotto `~/.veles/tmp/`, quindi gli hook e i server MCP di
`.agents/` del progetto non lo raggiungono mai. Gira con `--dangerously-skip-permissions`
quando ha gli strumenti di Veles — altrimenti agy rifiuta le chiamate MCP in modalità
headless — e un hook in quel workspace nega ogni suo strumento; anche un hook che fallisce
nega. Gli strumenti per i file di Veles non possono scrivere fuori dal progetto, quindi
agy non può riscrivere quell'hook tramite essi. Anche `codex` gira fuori dal progetto,
con la tua config di codex ignorata, una sandbox in sola lettura e i suoi strumenti
disattivati da feature flag i cui nomi Veles controlla prima di ogni prima esecuzione —
un codex che ne ha rinominato uno da cui dipende viene rifiutato, non eseguito aperto. Il
suo server MCP va nei suoi argomenti (nessun file di config), vengono approvati solo gli
strumenti di quel server, e l'ambiente che quel server riceve viene inoltrato per nome —
mai `VELES_TRUST_AUTO_ALLOW`.

Limiti noti:

- `run_shell` è una shell: una volta che lo concedi (o sotto autopilot) può scrivere
  qualsiasi dei file qui sopra senza la conferma per file.
- Un'approvazione MCP fissa la riga di comando del server, non i file che esegue dal
  progetto (uno script indicato in `args`) — rivedi anche quelli.
- Con un provider CLI, le esecuzioni che preautorizzano gli strumenti solo per sé stesse
  (job in background del daemon, `veles research`) non lo trasmettono alla CLI
  delegata: la preautorizzazione vive nel processo di Veles, e il server MCP avviato
  dalla CLI è un altro processo, quindi i suoi strumenti di Veles richiedono una
  concessione permanente con `veles trust set` o una finestra di autopilot. Nemmeno la
  modalità di pianificazione dell'esecuzione genitore li raggiunge.
- `antigravity-cli` conta sul fatto che agy rispetti il `.agents/hooks.json` del suo
  workspace; una release di agy che smettesse di leggere gli hook del workspace
  lascerebbe aperti i suoi strumenti sotto `--dangerously-skip-permissions`.

I percorsi con caratteri di controllo (sequenze di escape del terminale, override bidi)
vengono rifiutati, e le conferme, la richiesta di fiducia e l'anteprima del diff
mostrano tali caratteri con l'escape — una chiamata a uno strumento non può falsificare
il testo che approvi.

I server MCP di una configurazione partono solo dopo che li hai approvati — vedi
[server MCP esterni](external-mcp-servers.md#approvare-ispezionare-e-testare).
