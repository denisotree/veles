# Как направлять задачи на разные модели

> 🌐 **Языки:** [English](../../en/how-to/per-task-routing.md) · [简体中文](../../zh-CN/how-to/per-task-routing.md) · [繁體中文](../../zh-TW/how-to/per-task-routing.md) · [日本語](../../ja/how-to/per-task-routing.md) · [한국어](../../ko/how-to/per-task-routing.md) · [Español](../../es/how-to/per-task-routing.md) · [Français](../../fr/how-to/per-task-routing.md) · [Italiano](../../it/how-to/per-task-routing.md) · [Português (BR)](../../pt-BR/how-to/per-task-routing.md) · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · **Русский** · [العربية](../../ar/how-to/per-task-routing.md) · [हिन्दी](../../hi/how-to/per-task-routing.md) · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

Veles не привязан к одной модели. Каждая внутренняя **задача** может использовать
свой `provider:model` — дешёвую модель для компрессии контекста, сильную для
основного агента, vision-модель для изображений. Это система *ансамблевой
маршрутизации*.

## Типы задач

| Задача | Используется для |
|---|---|
| `default` | Основной цикл агента |
| `curator` | Консолидация сессий → wiki |
| `compressor` | Компрессия контекста скользящим окном |
| `insights` | Извлечение инсайтов после запуска |
| `skills` | Выполнение навыков |
| `advisor` | Самопроверка `advisor_review` |
| `vision` | `image_describe` (когда подключён vision-адаптер) |
| `embedding` | Сходство для `veles skill dedup` |

## Посмотреть текущую маршрутизацию

```bash
veles route show
```

Это печатает разрешённый `provider:model` для каждой задачи и метку `source`,
указывающую, какой слой принял решение.

## Закрепить задачу за моделью

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Эти команды записывают `[routing.tasks]` в `<project>/.veles/config.toml`:

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

Маршрутизацию можно выразить прозой в `AGENTS.md` (например, «использовать дешёвую
модель для компрессии»). Veles разбирает их в автогенерируемый `routing.nl.toml`:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Явные записи `[routing.tasks]` всегда побеждают подсказки на естественном языке.

## Порядок разрешения

Для каждой задачи побеждает первый слой, дающий спецификацию:

1. project `[routing.tasks][task]`
2. project `[routing.tasks].default`
3. project NL-подсказка (`routing.nl.toml`)
4. project `[engine]` база
5. user `[routing.tasks][task]` / `.default`
6. user `[user] default_provider` + `default_model`

Если ничего из этого не разрешилось, **жёстко зашитого запасного варианта нет** —
задача остаётся незаданной, и её вызывающая сторона деградирует (пропускает
функцию) или выдаёт явную ошибку, вместо того чтобы молча обратиться к облачной
модели.

(`embedding` пропускает catch-all-слои — чат-модель не является моделью
эмбеддингов — поэтому на неё отвечает только явный `[routing.tasks].embedding`.)
