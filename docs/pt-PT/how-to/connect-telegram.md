# Como ligar um canal do Telegram

> 🌐 **Idiomas:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · [Español](../../es/how-to/connect-telegram.md) · [Français](../../fr/how-to/connect-telegram.md) · [Italiano](../../it/how-to/connect-telegram.md) · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · **Português (PT)** · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

Fale com um projeto Veles a partir do Telegram. Um canal é uma porta de ligação
(gateway) que encaminha mensagens para um [daemon](run-as-daemon.md) e devolve as
respostas em streaming. Cada conversa (chat) recebe a sua própria sessão de diálogo.

## Pré-requisitos

- Um daemon em execução (ver [executar como daemon](run-as-daemon.md)).
- Um token de bot do Telegram do [@BotFather](https://t.me/BotFather).

## Opção A — anexar através do assistente (recomendado)

A partir do projeto, execute o assistente de canais; ele escreve a configuração e
guarda o token no porta-chaves do sistema operativo:

```bash
veles channel add --channel telegram
```

Ou anexe a uma sessão de daemon com nome específico:

```bash
veles channel add --channel telegram --session api
```

Também pode fazer isto a partir da [TUI do seletor de daemons](run-as-daemon.md#the-daemon-picker-tui):
prima `c` num daemon e siga as instruções.

Isto produz um bloco de configuração:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

A **whitelist** restringe a quem o bot responde (`@username` do Telegram ou id
numérico de utilizador). Deixe-a vazia para responder a todos — não recomendado,
uma vez que cada mensagem gasta tokens do modelo.

Reinicie o daemon para aplicar:

```bash
veles daemon restart
```

## Opção B — executar uma porta de ligação autónoma

Se preferir um processo separado (em vez do canal integrado no daemon), execute:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## Gerir as sessões de conversa

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Limitação multimodal

Enviar uma **foto ou mensagem de voz** devolve atualmente um aviso de "não
configurado". O Veles define os protocolos de adaptador `VisionAdapter` / STT e um
registo (`modules/vision.py`, `modules/stt.py`), mas **não é fornecido nenhum
adaptador concreto nem é registado nenhum no arranque do daemon**, pelo que as
imagens e o áudio ainda não são analisados. O chat de texto funciona na totalidade.
Ver a [referência de fornecedores](../reference/providers.md#multimodal-status-vision--speech-to-text).
