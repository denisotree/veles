# Как подключить канал Telegram

> 🌐 **Языки:** [English](../../en/how-to/connect-telegram.md) · **Русский**

Общайтесь с проектом Veles из Telegram. Канал — это шлюз, который пересылает
сообщения [демону](run-as-daemon.md) и стримит ответы обратно. Каждый чат получает
свою собственную сессию диалога.

## Предварительные требования

- Запущенный демон (см. [запуск как демон](run-as-daemon.md)).
- Токен Telegram-бота от [@BotFather](https://t.me/BotFather).

## Вариант A — подключение через мастер (рекомендуется)

Из проекта запустите мастер канала; он записывает конфигурацию и сохраняет токен в
системном keychain:

```bash
veles channel add --channel telegram
```

Или подключитесь к конкретной именованной сессии демона:

```bash
veles channel add --channel telegram --session api
```

Это же можно сделать из [TUI-панели выбора демонов](run-as-daemon.md): нажмите `c`
на демоне и следуйте подсказкам.

Это создаёт блок конфигурации:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

**Whitelist** ограничивает, кому бот отвечает (Telegram `@username` или числовой
user id). Оставьте его пустым, чтобы отвечать всем — не рекомендуется, поскольку
каждое сообщение тратит токены модели.

Перезапустите демон, чтобы применить:

```bash
veles daemon restart
```

## Вариант B — запуск отдельного шлюза

Если вы предпочитаете отдельный процесс (вместо канала внутри демона), запустите:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## Управление сессиями чатов

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## Ограничение мультимодальности

Отправка **фото или голосового сообщения** в настоящее время возвращает уведомление
«not configured». Veles определяет протоколы адаптеров `VisionAdapter` / STT и
реестр (`modules/vision.py`, `modules/stt.py`), но **ни один конкретный адаптер не
поставляется и не регистрируется при старте демона**, поэтому изображения и аудио
пока не анализируются. Текстовый чат работает полностью. См.
[справочник по провайдерам](../reference/providers.md).
