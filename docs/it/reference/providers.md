# Provider

> 🌐 **Lingue:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · **Italiano** · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles è agnostico rispetto al provider. Passa `--provider <id>` a qualsiasi
comando dell'agente, oppure imposta un default nella config. Gli ID dei modelli
usano la convenzione di denominazione del provider stesso.

## Il catalogo dei provider

Ogni provider che Veles conosce è una voce di un unico catalogo, costruito da tre fonti:

1. **Integrati** — la tabella qui sotto, distribuita con Veles.
2. **I tuoi** — `~/.veles/providers.toml`: un'API ospitata compatibile con OpenAI o un
   server che gestisci tu, aggiungendo una voce (vedi
   [aggiungere il tuo provider](../how-to/configure-providers.md#aggiungere-il-tuo-provider)).
   Una voce con un id integrato sovrascrive le impostazioni di quel provider (il suo
   `base_url`, per esempio).
3. **Moduli** — un modulo del registro fornisce un provider (`antigravity-cli`). Nominarlo
   in `[engine] provider`, in una rotta o con `--provider` lo installa dai registri
   connessi alla prossima esecuzione, come un canale dichiarato.

`--provider`, `veles models`, le procedure guidate di configurazione, il routing e
`veles doctor` leggono tutti il catalogo, quindi un provider di qualsiasi fonte funziona
ovunque funzioni uno integrato. Un id sconosciuto è un errore di una riga che elenca ciò
che esiste; `veles doctor` controlla anche `~/.veles/providers.toml` e ogni provider
nominato dalle tue rotte.

| Provider | Tipo | Chiave API | Note |
|---|---|---|---|
| `openrouter` | Gateway cloud | `OPENROUTER_API_KEY` | **Default.** Inoltra centinaia di modelli; ID dei modelli come `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud diretto | `ANTHROPIC_API_KEY` | API Claude Messages, prompt caching |
| `openai` | Cloud diretto | `OPENAI_API_KEY` | Chat completion GPT |
| `gemini` | Cloud diretto | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI delegata | — (sessione CLI) | Delega a una CLI `claude` locale in modalità JSON-stream |
| `ollama` | Locale | nessuna | `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`) |
| `llamacpp` | Locale | nessuna | `LLAMACPP_BASE_URL` (default `http://localhost:8080/v1`) |
| `openai-compat` | Locale/personalizzato | `OPENAI_COMPAT_API_KEY` opzionale | `OPENAI_COMPAT_BASE_URL` (obbligatorio, nessun default) |

`gemini-cli` è stato rimosso nella 1.2.6 — Google non serve più la Gemini CLI agli
account personali. Usa `gemini` con una chiave API, oppure il modulo `antigravity-cli`.

Provider di default: `openrouter`. **Non esiste un modello di default hardcoded** —
impostane uno tramite la procedura guidata di configurazione, `[engine] model` o
`--model` (altrimenti l'agente segnala "no model configured"). Le rotte per task
ereditano `[engine]` come base, salvo override in `[routing.tasks]` — vedi
[routing per task](../how-to/per-task-routing.md).

## Provider locali

`ollama`, `llamacpp` e `openai-compat` non richiedono chiave API. Elenca i modelli
installati con `veles models <provider>` (sempre live per i provider locali).

**La chiamata-tool viene rilevata** da ciò che il backend dichiara: ollama riporta le
capacità di ogni modello, un server llama.cpp quelle del suo chat template.
`VELES_LOCAL_TOOLS=1` forza la chiamata-tool attiva, `=0` la disattiva; se non è
impostata, viene rilevata.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Sovrascrivi gli endpoint con le variabili d'ambiente `*_BASE_URL` (vedi
[variabili d'ambiente](environment-variables.md)).

## Delega alla CLI (`claude-cli`, `antigravity-cli`)

Se possiedi un abbonamento Claude o Google, Veles può eseguirne la CLI in modalità
headless e agire da coordinatore — senza una chiave API separata. `claude-cli` è
integrato; `antigravity-cli` (la CLI `agy`) è un modulo del registro che si installa
da solo quando lo nomini.

Il delegato è solo il modello: i tool di Veles lo raggiungono tramite un bridge MCP, e
ogni chiamata passa per la scala di fiducia di Veles. La config del bridge si trova in
una directory del processo in esecuzione, `.veles/tmp/delegate-<pid>/`, rimossa alla sua
uscita. `agy` gira lì in un workspace temporaneo, non nel tuo progetto, dietro un gate
che nega i suoi shell e tool per i file.

## Stato multimodale (vision / speech-to-text)

Veles definisce un `VisionAdapter` e un protocollo di adapter STT
(`modules/vision.py`, `modules/stt.py`) più un registro globale al processo, **ma
non viene fornito alcun adapter concreto e nessuno ne registra uno all'avvio del
daemon**. Pertanto una foto o un messaggio vocale inviato a un canale al momento
restituisce un avviso "not configured" invece di essere analizzato. Il task di
routing `vision` esiste per quando un adapter verrà collegato. Vedi
[connettere Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Scegliere un modello

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Per usare modelli diversi per lavori diversi (economico per la compressione,
potente per la pianificazione), vedi [routing per task](../how-to/per-task-routing.md).
