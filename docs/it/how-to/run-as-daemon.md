# Come eseguire Veles come daemon

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

Il daemon è un server HTTP+WS opzionale e di lunga durata che espone l'agente come
API — la base per i [canali](connect-telegram.md) (Telegram, …), i
[job](long-running-tasks.md) pianificati e l'uso remoto/headless.

## Avvio e arresto

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` si stacca e restituisce la shell. Per un processo in primo piano (systemd
`Type=simple`, Docker, debug) passa `--foreground`. Sovrascrivi il bind:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

Il modello e il provider del daemon provengono dalla config del progetto e sono
**fissi per tutta la sua durata** — impostali prima di avviarlo:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## Token di autenticazione

I client API si autenticano con un bearer token:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## Il selettore di daemon (TUI)

Esegui `veles daemon` senza sottocomando per aprire il pannello di controllo — un
albero dei daemon del tuo progetto e dei canali di ciascun daemon:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Tasti: `Enter` apre il log di un daemon; `s`/`t`/`r` avvia/arresta/riavvia; `d`
elimina; `c`/`x` aggiunge/rimuove un canale; `q` esce.

## Più daemon per progetto (sessioni con nome)

Un progetto può eseguire più daemon con modelli/porte diversi contemporaneamente.
Dichiara una sessione con nome, poi avviala:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

Ogni sessione con nome ha il proprio blocco di config `[daemon.<name>]` e i propri
canali (`[daemon.<name>.channels.*]`).

## Elencare i daemon di tutti i progetti

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## Passo successivo

- [Connettere un canale Telegram](connect-telegram.md)
- [Pianificare job](long-running-tasks.md)
