# Как запускать долгие задачи: цели, задания, dreaming, исследования

> 🌐 **Языки:** [English](../../en/how-to/long-running-tasks.md) · [简体中文](../../zh-CN/how-to/long-running-tasks.md) · [繁體中文](../../zh-TW/how-to/long-running-tasks.md) · [日本語](../../ja/how-to/long-running-tasks.md) · [한국어](../../ko/how-to/long-running-tasks.md) · [Español](../../es/how-to/long-running-tasks.md) · [Français](../../fr/how-to/long-running-tasks.md) · [Italiano](../../it/how-to/long-running-tasks.md) · [Português (BR)](../../pt-BR/how-to/long-running-tasks.md) · [Português (PT)](../../pt-PT/how-to/long-running-tasks.md) · **Русский** · [العربية](../../ar/how-to/long-running-tasks.md) · [हिन्दी](../../hi/how-to/long-running-tasks.md) · [বাংলা](../../bn/how-to/long-running-tasks.md) · [Tiếng Việt](../../vi/how-to/long-running-tasks.md)

Помимо одиночных промптов, Veles может преследовать многошаговые **цели** с
бюджетами, выполнять **запланированные задания**, **dream** для консолидации
памяти, **исследовать** веб параллельно и раскладывать работу между **manager** и
суб-агентами.

## Цели — задачи с бюджетами и контрольными точками

Цель — это задача на длинном горизонте с явными ограничениями и журналом прогресса:

```bash
veles goal start "Draft a competitor analysis report" \
  --done-when "report.md exists and cites >=3 sources" \
  --max-steps 30 --max-cost-usd 5 --max-wall-time-s 3600

veles goal list
veles goal show <id>
veles goal checkpoint <id> "Outlined sections; cited 2 sources" --cost-usd 0.40
veles goal pause <id> ; veles goal resume <id>
veles goal done <id> --evidence report.md
veles goal cancel <id> --reason "scope changed"
```

В TUI режим запуска **goal** (переключается через `Shift+Tab`) управляет тем же
конечным автоматом интерактивно: он расспрашивает вас, подтверждает план,
выполняет и проверяет.

## Задания — запуски агента по расписанию

Запланировать запуск промпта по cron-выражению, по интервалу или один раз в
заданное время:

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # run on the next tick
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

`--schedule` принимает cron-выражение, `<N><s|m|h|d>` (например, `30m`) или
ISO-метку времени. Задания выполняются, когда daemon запущен, либо запустите их все
сразу синхронно:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

Доставить вывод задания в канал можно через `--deliver-to telegram:<chat_id>`.

## Dreaming — фоновая консолидация памяти

`dream` извлекает инсайты, дедуплицирует навыки, предлагает повышения и проверяет
вики линтером — поддерживая память в актуальном состоянии без вашего ожидания:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

Запущенный daemon видит сны автоматически, когда простаивает.

## Исследования — параллельное веб-расследование

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles раскладывает вопрос, исследует разные ракурсы параллельно и синтезирует
отчёт со ссылками.

## Режим manager — разложить любой промпт

Включить многоагентную декомпозицию для одного запуска (manager порождает
суб-агентов explorer / writer / advisor и никогда не пишет финальный ответ сам):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

См. [многоагентная оркестрация](../explanation/multi-agent-orchestration.md).
