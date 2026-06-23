# Riferimento configurazione

> 🌐 **Lingue:** [English](../../en/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · **Italiano**

Veles è configurato da due file TOML e da un insieme di directory di stato. I segreti
(chiavi API, token dei bot) **non** vengono mai scritti in questi file — vivono nel
portachiavi del SO o nelle variabili d'ambiente (vedi [variabili d'ambiente](environment-variables.md)).

## Dove risiede lo stato

| Percorso | Scope | Contenuti |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, concessioni di trust, skill/tool cross-project, cache dei modelli, locale, registro |
| `<project>/.veles/` | Locale al progetto | `project.toml`, `config.toml`, `memory.db`, skill/tool del progetto, piani, artefatti di runtime |
| `<project>/AGENTS.md` | Progetto | Il file di contesto iniettato nell'agente (collegato via symlink a `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Progetto | Contenuto utente (il layout LLM-Wiki di default) |

`VELES_USER_HOME` reindirizza `~` (così lo stato utente finisce in `<override>/.veles/`).
Vedi [layout del progetto](project-layout.md) per l'albero completo.

---

## Config utente — `~/.veles/config.toml`

Scritto dalla procedura guidata al primo avvio; modificabile a mano in sicurezza.

```toml
[user]
language = "en"                  # "en" | "ru" — locale delle stringhe UI
default_provider = "openrouter"  # provider di default per i nuovi progetti
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # registrato dalla procedura guidata
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # policy opzionale per-tool
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # routing opzionale a scope utente (vedi sotto)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # server MCP opzionali a scope utente
transport = "stdio"
command = "python"               # solo eseguibile — gli argomenti vanno in `args`
args = ["-m", "my_mcp_server"]
```

| Chiave | Tipo | Scopo |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale per le stringhe UI (sovrascrivibile via `VELES_LOCALE`) |
| `[user] default_provider` | string | Provider usato quando nessuno è indicato |
| `[user] default_model` | string | Modello usato quando nessuno è indicato |
| `[user] tui_theme` | string | Tema colore di default della TUI |
| `[permissions] <tool>` | policy | Policy di permesso per-tool (vedi [trust e sandbox](../explanation/trust-and-sandbox.md)) |

---

## Config di progetto — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base per l'agente principale + routing

[routing.tasks]                  # override per-task (priorità più alta sotto i flag espliciti)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # il daemon senza nome / "default"
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # una sessione daemon con nome ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # canali globali (serviti dal daemon senza nome)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # canali legati a una sessione daemon con nome
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # server MCP esterni (scope progetto)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # solo eseguibile — gli argomenti vanno in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpola dall'ambiente
```

### Sezioni

| Sezione | Scopo |
|---|---|
| `[provider]` | Provider/modello di base per l'agente principale e la cascata di routing |
| `[routing.tasks]` | Override `provider:model` per-task — vedi [routing per-task](../how-to/per-task-routing.md) |
| `[permissions]` | Policy di permesso per-tool (scope progetto) |
| `[daemon]` | Bind + autostart del daemon senza nome / "default" |
| `[daemon.<name>]` | Una sessione daemon con nome (proprio modello/provider/host/porta/mode) |
| `[channels.<type>]` | Un canale servito dal daemon senza nome (es. `telegram`) |
| `[daemon.<name>.channels.<type>]` | Un canale legato a una sessione daemon con nome |
| `[mcp.servers.<name>]` | Un server MCP esterno (fonte di tool) |

Tipi di task per `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> Gli hint di routing in linguaggio naturale in `AGENTS.md` vengono analizzati in un
> `routing.nl.toml` auto-generato; le voci esplicite `[routing.tasks]` vincono sempre. Esegui
> `veles route refresh` per rianalizzare. Vedi [routing per-task](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` contiene i metadati immutabili del progetto (`name`,
`created_at`, `schema_version`, `layout`). Di norma non lo modifichi a mano.

---

## AGENTS.md

Il file di contesto del progetto nella root del progetto. Viene iniettato nel prompt di
sistema dell'agente all'avvio e collegato via symlink a `CLAUDE.md` e `GEMINI.md` così che
una CLI `claude` o `gemini` avviata nella directory recuperi lo stesso contesto.

Mantienilo piccolo — i file `.md` ausiliari (es. `wiki/INDEX.md`) si caricano su richiesta.
Valida le sezioni richieste con `veles schema validate`. Vedi
[layout pack e l'LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
