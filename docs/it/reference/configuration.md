# Riferimento configurazione

> 🌐 **Lingue:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · **Italiano** · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

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
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)
request_timeout_s = 180                              # facoltativo; quanto attendere una risposta
max_retries = 1                                      # facoltativo; tentativi per richiesta

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
| `[engine]` | Provider di base (`provider` = nome del provider) + modello (`model` = id del modello) per l'agente principale e la cascata di routing, più i budget del client `request_timeout_s` / `max_retries` |
| `[routing.tasks]` | Override `provider:model` per task — vedi [routing per task](../how-to/per-task-routing.md) |
| `[permissions]` | Policy di permessi per tool (scope di progetto) |
| `[daemon]` | Bind + autostart del daemon senza nome/"default" |
| `[daemon.<name>]` | Una sessione daemon con nome (modello/provider/host/porta/mode propri) |
| `[goal]` | Il budget di un nuovo obiettivo — `max_steps` (30), `max_cost_usd` (5.0), `max_wall_time_s` (3600); i flag di `veles goal start` lo sostituiscono |
| `[channels.<type>]` | Un canale servito dal daemon senza nome (es. `telegram`) |
| `[daemon.<name>.channels.<type>]` | Un canale collegato a una sessione daemon con nome |
| `[mcp.servers.<name>]` | Un server MCP esterno (sorgente di tool) |

Tipi di task per `[routing.tasks]`: `default`, `curator`, `compressor`,
`insights`, `skills`, `advisor`, `vision`, `embedding`.

> I suggerimenti di routing in linguaggio naturale in `AGENTS.md` vengono
> analizzati e tradotti in un `routing.nl.toml` generato automaticamente; le voci
> esplicite di `[routing.tasks]` vincono sempre. Esegui `veles route refresh` per
> rianalizzarli. Vedi [routing per task](../how-to/per-task-routing.md).

### Quanto attendere una risposta, e quanti tentativi

```toml
[engine]
request_timeout_s = 180
max_retries = 1
```

Sono parametri del **client**, per questo stanno piatti sotto `[engine]` e non in
`[engine.request.<provider>]`: quella sezione è il *corpo* della richiesta, e un
timeout lì dentro non viaggia mai.

Senza di esse il timeout si deduce dall'id del modello: una famiglia di
ragionamento riceve 900 s, una sua variante `flash`/`mini` 450 s, tutto il resto
120 s. È una congettura strutturalmente debole: **il nome descrive una famiglia,
mentre il tempo di risposta lo stabilisce il backend che la serve.** Uno stesso id
può girare a 33 tok/s su un backend e 0,8 tok/s su un altro. Quando il numero
dedotto non va bene per la tua esecuzione, impostalo; e fissa anche il backend
(sotto) se vuoi che quel numero significhi la stessa cosa due volte.

`max_retries` conta per lo stesso motivo. Senza, l'SDK riprova due volte, quindi un
timeout di 450 s vale fino a 1350 s su un solo turno: abbastanza per far saltare un
budget che sembrava generoso. `0` è un valore legittimo e non equivale a omettere
la chiave.

Precedenza per entrambe: argomento esplicito nel codice → `[engine]` → valore per
modello. Un valore che non sia un numero positivo (o, per `max_retries`, un intero
non negativo) interrompe con un `ConfigError` che nomina il file.

**Ambito:** oggi solo l'adattatore OpenRouter legge queste chiavi. I client
Anthropic, OpenAI e Gemini vengono costruiti senza entrambi i parametri e le ignorano.

### Fissare un backend e altre chiavi del corpo della richiesta

`[engine.request.<provider>]` viene inoltrato **così com'è** nel corpo della
richiesta di quel provider. Veles non modella lo schema del provider, quindi
qualunque opzione esso accetti funziona senza attendere che Veles la conosca:

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

La sezione è indicizzata per **nome del provider** (`openrouter`, `anthropic`,
`openai`, `gemini`, `ollama`, `llamacpp`, `openai-compat`) affinché una stessa
configurazione di progetto sopravviva a un cambio di backend: un blocco
`provider` di OpenRouter inviato a llama.cpp sarebbe un 400, perciò ogni backend
legge solo la propria sottosezione. Senza sezione dichiarata le richieste sono
identiche byte per byte a prima.

**Quando serve: misurazioni riproducibili.** Un relay come OpenRouter distribuisce
un solo modello su molti backend con quantizzazioni diverse, così due esecuzioni
sullo stesso input possono divergere per ragioni estranee all'input. Il routing
persistente per `session_id` tiene una conversazione su un solo backend, ma non
dice su **quale**.

Fissa con `order`, non con `quantizations`. Al 18/09/2026 `z-ai/glm-5.3-flash`
ha 29 endpoint: 16 a `fp8`, 3 a `fp4`, uno `nvfp4`, **9 che non dichiarano alcuna
quantizzazione** e nessuno a `bf16`. Quindi `quantizations = ["fp8"]` lascia
ancora 16 candidati, con finestre di contesto da 262144 a 1310720 token, mentre
un `order` di un solo elemento più `allow_fallbacks = false` determina il backend
in modo univoco. Per elencare gli endpoint di un modello:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

Tieni il pin solo nel progetto di misurazione: la produzione vuole il routing
persistente, che preserva disponibilità e fallback.

**Verificare che abbia tenuto.** Ogni chiamata al modello registra in
`.veles/traces.jsonl` sia l'intenzione sia l'esito: `request_extra` è ciò che è
stato inviato, `upstream_provider` il backend che ha risposto. Basta una riga:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

Più di una riga significa che l'esecuzione ha mescolato i backend. Gli stessi
record portano `reasoning_tokens` (quanta parte del budget è andata in
ragionamento) e `est_cost_usd` (il costo realmente fatturato dal provider, quando
lo comunica).

**Gli errori sono rumorosi di proposito.** Un nome di provider scritto male o un
errore nel percorso della sezione (`[engine.reqest.…]`) interrompe l'esecuzione
con un `ConfigError` che nomina il file e i provider noti: un pin che non è mai
arrivato sul filo invaliderebbe in silenzio la misurazione per cui era stato
scritto. Veles non controlla le chiavi *dentro* la sottosezione, perché lo fa il
provider stesso: OpenRouter risponde
`400 provider: Unrecognized key: "quantization"` a una chiave sconosciuta e
`404 No endpoints found …` a un valore senza corrispondenza.

### Per quanto tempo si conservano le trascrizioni

**Non viene eliminato nulla se non lo chiedi.** `turn_retention_days` vale `0`
di default, il che conserva per sempre tutti i turni di conversazione. Impostalo
a un numero di giorni per mettere un tetto a `memory.db`:

```toml
[memory]
turn_retention_days = 90   # 0 (predefinito) conserva tutto
```

Con l'opzione attiva, i turni grezzi più vecchi di quel periodo vengono
eliminati; gli **insight** e le regole che ne sono stati estratti si conservano
per sempre in ogni caso. La trascrizione è la materia prima, gli insight sono ciò
per cui è stata letta.

Perché una trascrizione venga scartata devono valere **entrambe** le condizioni:
essere più vecchia della finestra **e** che il curatore abbia già elaborato quella
sessione. Una sessione che il curatore non ha raggiunto non viene mai eliminata,
qualunque sia la sua età — altrimenti la trascrizione verrebbe distrutta prima che
se ne fosse appreso qualcosa.

Il costo di attivarlo: `veles sessions search` trova testo solo dentro la
finestra. `veles sessions list` continua a mostrare le esecuzioni più vecchie,
perché le righe di sessione (id, titolo, timestamp) restano: spariscono solo i
corpi dei messaggi. La pulizia avviene durante `veles dream`, dopo l'estrazione
degli insight.

### Rotazione dei log

`traces.jsonl` ed `events.jsonl` ruotano a 50 MB verso `<nome>.<unix_ts>`, e
vengono conservate le **10** rotazioni più recenti; le precedenti sono eliminate
alla rotazione successiva. Prima venivano tenute per sempre.

A volumi ordinari non c'è nulla da configurare: a ~530 byte per record di traccia
e ~1,1 KB di eventi per turno dell'agente, la prima rotazione è lontana anni.
L'impostazione esiste perché una crescita illimitata senza policy è una perdita
che dovrà scoprire chi eredita la macchina.

### Immagini

Una foto inviata a un canale viene descritta prima che il turno inizi, usando il
modello a cui punta `[routing.tasks].vision` — che, senza una rotta esplicita, è
il tuo modello `[engine]`. Un motore multimodale non richiede quindi alcuna
configurazione.

`[vision] mode` sceglie la pipeline:

- `model` (predefinito) — il modello di visione descrive l'immagine.
- `ocr` — solo Tesseract. Locale, gratuito, senza chiamata all'LLM; adatto alle
  scansioni di testo.
- `ocr+model` — prima il testo letterale, poi la descrizione del modello.
- `off` — non viene letto nulla; il file viene comunque salvato e l'agente può
  chiamare `image_describe` / `image_ocr` da sé, se vuole.

Imposta `[vision] model` quando il motore è solo testuale. Va bene qualsiasi
provider con capacità di visione, incluso un server locale: `ollama:llava`,
`llamacpp:…`, `openai-compat:…`.

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
