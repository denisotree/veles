# Cómo conectar un canal de Telegram

> 🌐 **Idiomas:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · **Español** · [Français](../../fr/how-to/connect-telegram.md) · [Italiano](../../it/how-to/connect-telegram.md) · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

Habla con un proyecto de Veles desde Telegram. Un canal es una pasarela que
reenvía los mensajes a un [daemon](run-as-daemon.md) y devuelve las respuestas en
streaming. Cada chat obtiene su propia sesión de conversación.

## Requisitos previos

- Un daemon en ejecución (ver [ejecutar como daemon](run-as-daemon.md)).
- Un token de bot de Telegram de [@BotFather](https://t.me/BotFather).

## Opción A — adjuntar mediante el asistente (recomendado)

Desde el proyecto, ejecuta el asistente de canales; este escribe la configuración y
guarda el token en el llavero del sistema operativo:

```bash
veles channel add --channel telegram
```

O adjúntalo a una sesión de daemon con nombre concreto:

```bash
veles channel add --channel telegram --session api
```

También puedes hacerlo desde la [TUI del selector de daemons](run-as-daemon.md#the-daemon-picker-tui):
pulsa `c` sobre un daemon y sigue las indicaciones.

Esto genera un bloque de configuración:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

La **whitelist** restringe a quién responde el bot (el `@username` de Telegram o el
id numérico de usuario). Déjala vacía para responder a todo el mundo — no
recomendado, ya que cada mensaje consume tokens del modelo.

Reinicia el daemon para aplicar los cambios:

```bash
veles daemon restart
```

## Opción B — ejecutar una pasarela independiente

Si prefieres un proceso separado (en lugar del canal dentro del daemon), ejecuta:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## Gestionar las sesiones de chat

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Limitación multimodal

Enviar una **foto o un mensaje de voz** actualmente devuelve un aviso de "no
configurado". Veles define los protocolos de adaptador `VisionAdapter` / STT y un
registro (`modules/vision.py`, `modules/stt.py`), pero **no se incluye ningún
adaptador concreto ni se registra ninguno al arrancar el daemon**, así que las
imágenes y el audio todavía no se analizan. El chat de texto funciona por completo.
Ver la [referencia de proveedores](../reference/providers.md#multimodal-status-vision--speech-to-text).
