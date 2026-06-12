# Как направлять задачи на разные модели

> 🌐 **Языки:** [English](../../en/how-to/per-task-routing.md) · **Русский**

Veles не привязан к одной модели. Каждая внутренняя **задача** может использовать
свою пару `provider:model` — дешёвую модель для сжатия контекста, мощную для
основного агента, vision-модель для изображений. Это система *ensemble routing*.

## Типы задач

| Задача | Применяется для |
|---|---|
| `default` | Основной цикл агента |
| `curator` | Консолидация сессии → wiki |
| `compressor` | Сжатие контекста по скользящему окну |
| `insights` | Извлечение инсайтов после запуска |
| `skills` | Выполнение навыков |
| `advisor` | Самопроверка `advisor_review` |
| `vision` | `image_describe` (когда подключён vision-адаптер) |
| `embedding` | Сходство в `veles skill dedup` |

## Просмотр текущей маршрутизации

```bash
veles route show
```

Команда печатает разрешённую пару `provider:model` для каждой задачи и метку
`source`, указывающую, какой слой её определил.

## Закрепление задачи за моделью

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Это записывает `[routing.tasks]` в `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Сброс

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Подсказки на естественном языке в AGENTS.md

Маршрутизацию можно выразить прозой в `AGENTS.md` (например, «use a cheap model for
compression»). Veles разбирает такие подсказки в автоматически генерируемый
`routing.nl.toml`:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Явные записи `[routing.tasks]` всегда имеют приоритет над NL-подсказками.

## Порядок разрешения

Для каждой задачи побеждает первый слой, который выдаёт спецификацию:

1. проектный `[routing.tasks][task]`
2. проектный `[routing.tasks].default`
3. проектная NL-подсказка (`routing.nl.toml`)
4. проектная база `[provider]`
5. пользовательский `[routing.tasks][task]` / `.default`
6. пользовательские `[user] default_provider` + `default_model`
7. встроенное значение по умолчанию для этой задачи

(`embedding` пропускает универсальные правила — chat-модель не является
embedding-моделью.)
