# Telegram channel कैसे connect करें

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/how-to/connect-telegram.md)

किसी Veles project से Telegram के ज़रिए बात करें। एक channel ऐसा gateway है जो
messages को किसी [daemon](run-as-daemon.md) तक forward करता है और replies वापस stream करता है।
हर chat को अपना खुद का conversation session मिलता है।

## पूर्व-शर्तें

- एक चालू daemon ([run as a daemon](run-as-daemon.md) देखें)।
- [@BotFather](https://t.me/BotFather) से एक Telegram bot token।

## विकल्प A — wizard के ज़रिए attach करें (अनुशंसित)

project से channel wizard चलाएँ; यह config लिखता है और token को
OS keychain में store करता है:

```bash
veles channel add --channel telegram
```

या किसी specific named daemon session से attach करें:

```bash
veles channel add --channel telegram --session api
```

आप इसे [daemon picker TUI](run-as-daemon.md#the-daemon-picker-tui) से भी कर सकते हैं:
किसी daemon पर `c` दबाएँ और prompts का पालन करें।

यह एक config block बनाता है:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

**whitelist** यह सीमित करती है कि bot किसे जवाब दे (Telegram `@username` या numeric
user id)। इसे खाली छोड़ने पर bot सबको जवाब देगा — यह अनुशंसित नहीं है, क्योंकि हर
message model tokens खर्च करता है।

लागू करने के लिए daemon restart करें:

```bash
veles daemon restart
```

## विकल्प B — एक standalone gateway चलाएँ

अगर आप (in-daemon channel के बजाय) एक अलग process पसंद करते हैं, तो चलाएँ:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## chat sessions manage करें

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Multimodal सीमा

**photo या voice message** भेजने पर फ़िलहाल "not configured" notice मिलता है।
Veles `VisionAdapter` / STT adapter protocols और एक registry परिभाषित करता है
(`modules/vision.py`, `modules/stt.py`), लेकिन **कोई concrete adapter ship नहीं होता और
daemon startup पर कोई register नहीं होता**, इसलिए images और audio अभी analyse नहीं होते। Text
chat पूरी तरह काम करता है। देखें [providers reference](../reference/providers.md#multimodal-status-vision--speech-to-text)।
