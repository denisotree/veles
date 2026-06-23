# Como conectar um canal do Telegram

> 🌐 **Idiomas:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · [Español](../../es/how-to/connect-telegram.md) · [Français](../../fr/how-to/connect-telegram.md) · [Italiano](../../it/how-to/connect-telegram.md) · **Português (BR)** · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

Converse com um projeto Veles a partir do Telegram. Um canal é um gateway que encaminha
mensagens para um [daemon](run-as-daemon.md) e transmite as respostas de volta. Cada chat ganha
sua própria sessão de conversa.

## Pré-requisitos

- Um daemon em execução (veja [executar como daemon](run-as-daemon.md)).
- Um token de bot do Telegram obtido com o [@BotFather](https://t.me/BotFather).

## Opção A — anexar pelo assistente (recomendado)

A partir do projeto, execute o assistente de canal; ele grava a configuração e armazena o
token no keychain do SO:

```bash
veles channel add --channel telegram
```

Ou anexe a uma sessão de daemon nomeada específica:

```bash
veles channel add --channel telegram --session api
```

Você também pode fazer isso a partir da [TUI de seleção de daemon](run-as-daemon.md#the-daemon-picker-tui):
pressione `c` em um daemon e siga as instruções.

Isso produz um bloco de configuração:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

A **whitelist** restringe quem o bot responde (`@username` do Telegram ou id numérico
de usuário). Deixe-a vazia para responder a todos — não recomendado, já que cada
mensagem gasta tokens do modelo.

Reinicie o daemon para aplicar:

```bash
veles daemon restart
```

## Opção B — executar um gateway independente

Se você prefere um processo separado (em vez do canal interno do daemon), execute:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## Gerenciar sessões de chat

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Limitação multimodal

Enviar uma **foto ou mensagem de voz** atualmente retorna um aviso de "não configurado".
O Veles define os protocolos de adaptador `VisionAdapter` / STT e um registro
(`modules/vision.py`, `modules/stt.py`), mas **nenhum adaptador concreto é distribuído e nenhum
é registrado na inicialização do daemon**, então imagens e áudio ainda não são analisados. O chat de texto
funciona plenamente. Veja a [referência de provedores](../reference/providers.md#multimodal-status-vision--speech-to-text).
