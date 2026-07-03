# Как запустить Veles как демон

> 🌐 **Языки:** [English](../../en/how-to/run-as-daemon.md) · [简体中文](../../zh-CN/how-to/run-as-daemon.md) · [繁體中文](../../zh-TW/how-to/run-as-daemon.md) · [日本語](../../ja/how-to/run-as-daemon.md) · [한국어](../../ko/how-to/run-as-daemon.md) · [Español](../../es/how-to/run-as-daemon.md) · [Français](../../fr/how-to/run-as-daemon.md) · [Italiano](../../it/how-to/run-as-daemon.md) · [Português (BR)](../../pt-BR/how-to/run-as-daemon.md) · [Português (PT)](../../pt-PT/how-to/run-as-daemon.md) · **Русский** · [العربية](../../ar/how-to/run-as-daemon.md) · [हिन्दी](../../hi/how-to/run-as-daemon.md) · [বাংলা](../../bn/how-to/run-as-daemon.md) · [Tiếng Việt](../../vi/how-to/run-as-daemon.md)

Демон — это опциональный долгоживущий HTTP+WS-сервер, который выставляет агента в
виде API — основа для [каналов](connect-telegram.md) (Telegram, …),
запланированных [задач](long-running-tasks.md) и удалённого/headless-использования.

## Запуск и остановка

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` отсоединяется и возвращает вам shell. Для процесса в переднем плане
(systemd `Type=simple`, Docker, отладка) передайте `--foreground`. Переопределите
привязку:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

Модель и провайдер демона берутся из конфига проекта и **зафиксированы на всё
время его жизни** — задайте их до запуска:

```toml
# <project>/.veles/config.toml
[engine]
provider = "ollama"           # provider name
model = "qwen3:4b-instruct"   # model id
```

## Токены аутентификации

API-клиенты аутентифицируются bearer-токеном:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## Выбор демона (TUI)

Запустите `veles daemon` без подкоманды, чтобы открыть панель управления — дерево
демонов вашего проекта и каналов каждого демона:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Клавиши: `Enter` открывает лог демона; `s`/`t`/`r` — запуск/остановка/перезапуск;
`d` — удаление; `c`/`x` — добавить/удалить канал; `q` — выход.

## Несколько демонов на проект (именованные сессии)

Проект может одновременно запускать несколько демонов с разными моделями/портами.
Объявите именованную сессию, затем запустите её:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

У каждой именованной сессии собственный блок конфига `[daemon.<name>]` и
собственные каналы (`[daemon.<name>.channels.*]`).

## Список демонов по всем проектам

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## Дальше

- [Подключите канал Telegram](connect-telegram.md)
- [Запланируйте задачи](long-running-tasks.md)
