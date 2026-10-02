# Как расширить Veles модулем

> 🌐 **Языки:** [English](../../en/how-to/extend-veles-with-modules.md) · **Русский**

Модуль добавляет что-то в Veles через **точки вклада**: его точка входа `register(api)`
вызывает `api.contribute(point, name, obj)`, а ядро Veles читает внесённое, а не
импортирует код модуля. Встроенный движок wiki устроен именно так — это обычный модуль.

```python
# my_engine.py — точка входа, указанная в module.toml
from veles.core.contributions import Engine


def register(api) -> None:
    api.contribute("engine", "my-engine", Engine("my-engine"))
    api.contribute("prompt", "my-engine", my_prompt_blocks)
```

`name` уникален в пределах точки, включая встроенные модули Veles. Модуль, который вносит
в неизвестную точку, передаёт объект не того вида или повторяет имя, уже занятое другим
модулем (встроенным или нет), не загружается, а остальной Veles продолжает работать.
Recall резервирует `insights`, `turns`, `about` и `extra`; `BackgroundOp` и `DreamStep`
вносятся под своим `kind`/`name`. Вклад, бросивший исключение при вызове, пропускается с
предупреждением.

## Точки вклада

| Точка | Объект | Что с ним делает ядро |
|---|---|---|
| `engine` | `Engine(name)` | раскладка с `[layout.engines] <name> = true` включает его для проекта |
| `tool` | `ToolSet(load, tools, engine=None)` | `load()` регистрирует функции `@tool`; с `engine` — только там, где движок включён |
| `recall` | `fn(project, query, *, limit) -> list[RecallHit]` | добавляет попадания в recall памяти |
| `prompt` | `fn(project, *, include_index) -> list[str]` | добавляет блоки в стабильную (кэшируемую) часть системного промпта |
| `dream_step` | `DreamStep(name, run, skip_flag)` | `run(project, result, *, dry_run)` внутри цикла dream |
| `curator_target` | `CuratorTarget(engine, prepare, instructions, persist_tools)` | куда агент curator сохраняет сессию |
| `subproject_source` | `PageSource(pages, engine=None)` | страницы для кластеризации подпроектов и счётчика в self-doc |
| `self_doc` | `fn(project, content) -> путь или None` | забирает страницу самодокументации (иначе `.veles/memory/self-doc.md`) |
| `scaffold` | `fn(root, manifest)` | выполняется при применении раскладки к проекту |
| `background_op` | `BackgroundOp(kind, toolset, run)` | вид фоновой задачи daemon; `run(job, *, spawn_agent, project)` |
| `memory` | фабрика (через `api.add_memory_provider`) | внешний провайдер памяти |

Объекты с полем `engine` сами проверяют свой движок; остальные, если должны работать
только при включённом движке, проверяют `veles.core.layout.engines.engine_enabled(project, "<name>")`.

## Объявить, что вносит модуль реестра

В реестре `provides` в `extension.toml` перечисляет каждый вклад как `<point>:<name>`
(а хуки — как `hook:<name>`). `veles registry validate --run-code` загружает модуль и
сверяет список с тем, что `register()` действительно внёс.

```toml
[extension]
name = "my-engine"
kind = "module"
provides = ["engine:my-engine", "prompt:my-engine"]
```
