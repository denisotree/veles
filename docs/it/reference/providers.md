# Provider

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/providers.md)

Veles è agnostico rispetto al provider. Passa `--provider <name>` a qualsiasi
comando dell'agente, oppure imposta un default nella config. Gli ID dei modelli
usano la convenzione di denominazione del provider stesso.

| Provider | Tipo | Chiave API | Note |
|---|---|---|---|
| `openrouter` | Gateway cloud | `OPENROUTER_API_KEY` | **Default.** Inoltra centinaia di modelli; ID dei modelli come `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud diretto | `ANTHROPIC_API_KEY` | API Claude Messages, prompt caching |
| `openai` | Cloud diretto | `OPENAI_API_KEY` | Chat completion GPT |
| `gemini` | Cloud diretto | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Sottoprocesso | — (sessione CLI) | Delega a una CLI `claude` locale in modalità JSON-stream |
| `gemini-cli` | Sottoprocesso | — (sessione CLI) | Delega a una CLI `gemini` locale |
| `ollama` | Locale | nessuna | `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`) |
| `llamacpp` | Locale | nessuna | `LLAMACPP_BASE_URL` (default `http://localhost:8080/v1`) |
| `openai-compat` | Locale/personalizzato | nessuna | `OPENAI_COMPAT_BASE_URL` (obbligatorio, nessun default) |

Provider di default: `openrouter`. **Non esiste un modello di default hardcoded** —
impostane uno tramite la procedura guidata di configurazione, `[provider] model` o
`--model` (altrimenti l'agente segnala "no model configured"). Le rotte per task
ereditano `[provider]` come base, salvo override in `[routing.tasks]` — vedi
[routing per task](../how-to/per-task-routing.md).

## Provider locali

`ollama`, `llamacpp` e `openai-compat` non richiedono chiave API. Elenca i modelli
installati con `veles models <provider>` (sempre live per i provider locali).

**La chiamata-tool è disattivata di default** sui provider locali — molti modelli
locali emettono chiamate-tool malformate. Abilitala una volta scelto un modello
capace di gestire i tool:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Sovrascrivi gli endpoint con le variabili d'ambiente `*_BASE_URL` (vedi
[variabili d'ambiente](environment-variables.md)).

## Delega alla CLI (`claude-cli`, `gemini-cli`)

Se possiedi un abbonamento alla CLI di Claude o Gemini, Veles può eseguire il
binario in modalità JSON-streaming e agire da coordinatore — mantenendo il ciclo
local-first senza una chiave API separata. I tool di Veles raggiungono il
sottoprocesso solo quando è configurato un bridge MCP.

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
