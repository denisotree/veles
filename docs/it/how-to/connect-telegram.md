# Come collegare un canale Telegram

> 🌐 **Lingue:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · [Español](../../es/how-to/connect-telegram.md) · [Français](../../fr/how-to/connect-telegram.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

Comunica con un progetto Veles da Telegram. Un canale è un gateway che inoltra
i messaggi a un [daemon](run-as-daemon.md) e ne fa lo streaming delle risposte. Ogni chat ottiene
la propria sessione di conversazione.

## Prerequisiti

- Un daemon in esecuzione (vedi [eseguire come daemon](run-as-daemon.md)).
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

Riavvia il daemon per applicare:

```bash
veles daemon restart
```

## Opzione B — eseguire un gateway autonomo

Se preferisci un processo separato (invece del canale interno al daemon), esegui:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## Gestire le sessioni di chat

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Limitazione multimodale

L'invio di una **foto o di un messaggio vocale** restituisce attualmente un avviso "not configured".
Veles definisce i protocolli degli adapter `VisionAdapter` / STT e un registry
(`modules/vision.py`, `modules/stt.py`), ma **nessun adapter concreto viene distribuito e nessuno
è registrato all'avvio del daemon**, quindi immagini e audio non vengono ancora analizzati. La chat
testuale funziona pienamente. Vedi il [riferimento provider](../reference/providers.md#multimodal-status-vision--speech-to-text).
