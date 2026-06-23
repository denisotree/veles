# Как запустить Veles как демон

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

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
[provider]
default = "ollama"            # provider name
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
