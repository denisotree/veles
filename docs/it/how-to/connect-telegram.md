# Come collegare un canale Telegram

> 🌐 **Lingue:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · [Español](../../es/how-to/connect-telegram.md) · [Français](../../fr/how-to/connect-telegram.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

Comunica con un progetto Veles da Telegram. Un canale è un gateway che inoltra
i messaggi a un [daemon](run-as-daemon.md) e ne fa lo streaming delle risposte. Ogni chat ottiene
la propria sessione di conversazione.

Telegram è un modulo del registry ufficiale delle estensioni (`official/telegram`),
non parte del core di Veles. Non lo installi a mano: `veles channel add` te lo
propone, e un blocco `[channels.telegram]` nella tua configurazione lo installa al
prossimo `veles daemon start` — hai dichiarato il canale, quindi quello è il via
libera. Si installa solo dai registry che hai collegato.

## Prerequisiti

- Un progetto Veles (un daemon parte solo con un canale funzionante — questo lo è).
- Un token del bot Telegram da [@BotFather](https://t.me/BotFather).

## Opzione A — collegare tramite la procedura guidata (consigliata)

Dal progetto, esegui la procedura guidata del canale; scrive la configurazione e memorizza il
token nel portachiavi del sistema operativo:

```bash
veles channel add --channel telegram
```

Oppure collegalo a una specifica sessione del daemon con nome:

```bash
veles channel add --channel telegram --session api
```

Puoi farlo anche dalla [TUI di selezione del daemon](run-as-daemon.md#the-daemon-picker-tui):
premi `c` su un daemon e segui le istruzioni.

Questo produce un blocco di configurazione:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

La **whitelist** limita chi può ricevere risposte dal bot (`@username` Telegram o id utente
numerico). Lasciala vuota per rispondere a tutti — sconsigliato, dato che ogni
messaggio consuma token del modello.

Avvia (o riavvia) il daemon per applicare:

```bash
veles daemon start      # or: veles daemon restart
```

Scrivere il blocco a mano funziona allo stesso modo. Metti il token nel portachiavi
con `veles channel add`, oppure nel blocco come `bot_token = "…"`; se il token manca,
il daemon rifiuta di partire e indica il comando che risolve il problema.

## Opzione B — eseguire un gateway autonomo

Se preferisci un processo separato (invece del canale interno al daemon), esegui:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...   # or pass --secret
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

`veles channel run --channel telegram` installa prima il modulo se non c'è.

Il daemon con cui comunica si avvia solo con un canale proprio pronto, quindi questa opzione va bene per un daemon che ospita già un canale diverso. Non eseguire lo stesso bot in entrambi i posti: Telegram consegna gli aggiornamenti di un bot a un solo poller, quindi il secondo fallisce.

## Gestire le sessioni di chat

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Modalità dell'agente in una chat

`/mode` cambia la modalità dell'agente nella chat: `default` (l'agente risponde
direttamente, come prima di qualsiasi cambio), `auto` (decide per ogni messaggio
se pianificare prima), `planning` (pianifica soltanto, non modifica nulla) e
`writing` (agisce con i suoi strumenti). La modalità attuale è spuntata. La
scelta vale fino al riavvio del daemon. La riga di stato della modalità, per
esempio *auto → plan*, compare sopra la risposta.

`/goal <attività>` avvia un obiettivo nella chat. L'agente chiede ciò che gli
serve sapere e mostra il piano che seguirà. Quando rispondi `yes`, lavora da solo
e invia una riga dopo ogni passo, finché l'obiettivo è raggiunto o un budget si
esaurisce. Le approvazioni arrivano sempre come pulsanti. `/goal` mostra
l'avanzamento, `/goal cancel` lo ferma dopo il passo corrente e `/goal resume`
riprende un obiettivo fermato.

Quando l'agente ha bisogno di un dettaglio che solo tu puoi dare, lo chiede
nella chat. Tocca una delle risposte suggerite o scrivi la tua. Se non rispondi
entro cinque minuti, procede con la sua ipotesi migliore e dice quale.

`/settings` mostra in un solo messaggio il modello (fissato dalla configurazione del
daemon), la sessione della chat, il suo uso di token e i pulsanti di modalità.
`/tokens` mostra l'uso di token della sessione da quando il daemon è partito;
`/context` mostra quanto è piena la finestra di contesto del modello.

## Limitazione multimodale

L'invio di una **foto o di un messaggio vocale** restituisce attualmente un avviso "not configured".
Veles definisce i protocolli degli adapter `VisionAdapter` / STT e un registry
(`modules/vision.py`, `modules/stt.py`), ma **nessun adapter concreto viene distribuito e nessuno
è registrato all'avvio del daemon**, quindi immagini e audio non vengono ancora analizzati. La chat
testuale funziona pienamente. Vedi il [riferimento provider](../reference/providers.md#multimodal-status-vision--speech-to-text).
