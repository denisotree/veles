# Cómo conectar un canal de Telegram

> 🌐 **Idiomas:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · **Español** · [Français](../../fr/how-to/connect-telegram.md) · [Italiano](../../it/how-to/connect-telegram.md) · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

Habla con un proyecto de Veles desde Telegram. Un canal es una pasarela que
reenvía los mensajes a un [daemon](run-as-daemon.md) y devuelve las respuestas en
streaming. Cada chat obtiene su propia sesión de conversación.

Telegram es un módulo del registro oficial de extensiones (`official/telegram`),
no parte del núcleo de Veles. No lo instalas a mano: `veles channel add` te lo
ofrece, y un bloque `[channels.telegram]` en tu configuración lo instala en el
siguiente `veles daemon start` — has declarado el canal, así que eso es el visto
bueno. Se instala solo desde tus registros conectados.

## Requisitos previos

- Un proyecto de Veles (un daemon solo arranca con un canal operativo — este lo es).
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

Inicia (o reinicia) el daemon para aplicar los cambios:

```bash
veles daemon start      # or: veles daemon restart
```

Escribir el bloque a mano funciona igual. Guarda el token en el llavero con
`veles channel add`, o en el bloque como `bot_token = "…"`; si falta el token, el
daemon se niega a arrancar y nombra el comando que lo arregla.

## Opción B — ejecutar una pasarela independiente

Si prefieres un proceso separado (en lugar del canal dentro del daemon), ejecuta:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...   # or pass --secret
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

`veles channel run --channel telegram` instala antes el módulo si no está.

El daemon con el que habla solo arranca con un canal propio listo, así que esto encaja con un daemon que ya aloja un canal distinto. No ejecutes el mismo bot en ambos sitios: Telegram entrega las actualizaciones de un bot a un único poller, así que el segundo falla.

## Gestionar las sesiones de chat

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Modos del agente en un chat

`/mode` cambia el modo del agente en el chat: `default` (el agente responde
directamente, como antes de cualquier cambio), `auto` (decide en cada mensaje si
planificar primero), `planning` (solo planifica, no cambia nada) y `writing`
(actúa con sus herramientas). El modo actual aparece marcado. La elección dura
hasta que se reinicia el daemon. La línea de estado del modo, por ejemplo
*auto → plan*, aparece encima de la respuesta.

`/goal <tarea>` ejecuta un objetivo en el chat. El agente pregunta lo que
necesita saber y muestra el plan que seguirá. Cuando respondes `yes`, trabaja por
su cuenta y envía una línea tras cada paso, hasta cumplir el objetivo o agotar
un presupuesto. Las aprobaciones siguen llegando como botones. `/goal` muestra el
progreso, `/goal cancel` lo detiene tras el paso actual y `/goal resume`
continúa uno detenido.

Cuando el agente necesita un dato que solo tú puedes dar, pregunta en el chat.
Toca una de las respuestas sugeridas o escribe la tuya. Si no respondes en cinco
minutos, sigue con su mejor suposición y dice qué supuso.

`/settings` muestra en un solo mensaje el modelo (fijado por la configuración del
daemon), la sesión del chat, su uso de tokens y los botones de modo. `/tokens`
muestra el uso de tokens de la sesión desde que arrancó el daemon; `/context`
muestra cuán llena está la ventana de contexto del modelo.

## Limitación multimodal

Enviar una **foto o un mensaje de voz** actualmente devuelve un aviso de "no
configurado". Veles define los protocolos de adaptador `VisionAdapter` / STT y un
registro (`modules/vision.py`, `modules/stt.py`), pero **no se incluye ningún
adaptador concreto ni se registra ninguno al arrancar el daemon**, así que las
imágenes y el audio todavía no se analizan. El chat de texto funciona por completo.
Ver la [referencia de proveedores](../reference/providers.md#multimodal-status-vision--speech-to-text).
