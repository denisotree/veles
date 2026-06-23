# Riferimento configurazione

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/configuration.md)

Veles si configura tramite due file TOML e un insieme di directory di stato. I
segreti (chiavi API, token dei bot) non vengono **mai** scritti in questi file —
risiedono nel keychain del sistema operativo o nelle variabili d'ambiente (vedi
[variabili d'ambiente](environment-variables.md)).

## Dove risiede lo stato

| Percorso | Scope | Contenuto |
|---|---|---|
| `~/.veles/` | Globale utente | `config.toml`, concessioni di trust, skill/tool cross-progetto, cache dei modelli, locale, registro |
| `<project>/.veles/` | Locale al progetto | `project.toml`, `config.toml`, `memory.db`, skill/tool del progetto, piani, artefatti di runtime |
| `<project>/AGENTS.md` | Progetto | Il file di contesto iniettato nell'agente (collegato con symlink a `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Progetto | Contenuti utente (il layout LLM-Wiki di default) |

`VELES_USER_HOME` reindirizza `~` (così lo stato utente finisce in
`<override>/.veles/`). Vedi [layout del progetto](project-layout.md) per l'albero
completo.

---

## Config utente — `~/.veles/config.toml`

Scritto dalla procedura guidata al primo avvio; può essere modificato a mano in
sicurezza.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Chiave | Tipo | Scopo |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale per le stringhe dell'interfaccia (sovrascrivibile con `VELES_LOCALE`) |
| `[user] default_provider` | string | Provider usato quando non ne viene fornito uno |
| `[user] default_model` | string | Modello usato quando non ne viene fornito uno |
| `[user] tui_theme` | string | Tema di colori predefinito della TUI |
| `[permissions] <tool>` | policy | Policy di permessi per tool (vedi [trust e sandbox](../explanation/trust-and-sandbox.md)) |

---

## Config di progetto — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### Sezioni

| Sezione | Scopo |
|---|---|
| `[provider]` | Provider di base (`default` = nome del provider) + modello (`model` = id del modello) per l'agente principale e la cascata di routing |
| `[routing.tasks]` | Override `provider:model` per task — vedi [routing per task](../how-to/per-task-routing.md) |
| `[permissions]` | Policy di permessi per tool (scope di progetto) |
| `[daemon]` | Bind + autostart del daemon senza nome/"default" |
| `[daemon.<name>]` | Una sessione daemon con nome (modello/provider/host/porta/mode propri) |
| `[channels.<type>]` | Un canale servito dal daemon senza nome (es. `telegram`) |
| `[daemon.<name>.channels.<type>]` | Un canale collegato a una sessione daemon con nome |
| `[mcp.servers.<name>]` | Un server MCP esterno (sorgente di tool) |

Tipi di task per `[routing.tasks]`: `default`, `curator`, `compressor`,
`insights`, `skills`, `advisor`, `vision`, `embedding`.

> I suggerimenti di routing in linguaggio naturale in `AGENTS.md` vengono
> analizzati e tradotti in un `routing.nl.toml` generato automaticamente; le voci
> esplicite di `[routing.tasks]` vincono sempre. Esegui `veles route refresh` per
> rianalizzarli. Vedi [routing per task](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` contiene i metadati immutabili del progetto
(`name`, `created_at`, `schema_version`, `layout`). Normalmente non lo modifichi a
mano.

---

## AGENTS.md

Il file di contesto del progetto, posto nella radice del progetto. Viene iniettato
nel system prompt dell'agente all'avvio e collegato con symlink a `CLAUDE.md` e
`GEMINI.md`, così che una CLI `claude` o `gemini` avviata nella directory recuperi
lo stesso contesto.

Tienilo piccolo — i file `.md` ausiliari (es. `wiki/INDEX.md`) si caricano su
richiesta. Convalida le sezioni richieste con `veles schema validate`. Vedi
[layout pack e la LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
