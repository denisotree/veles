# Как расширить Veles модулем

> 🌐 **Языки:** [English](../../en/how-to/extend-veles-with-modules.md) · **Русский**

Модуль добавляет что-то в Veles через **точки вклада**: его точка входа `register(api)`
вызывает `api.contribute(point, name, obj)`, а ядро Veles читает внесённое, а не
импортирует код модуля. Движок wiki (в публичном реестре) устроен именно так — это
обычный модуль.

```python
# __init__.py — точка входа, указанная в module.toml
from veles.sdk.contributions import Engine

from .blocks import my_prompt_blocks  # модуль может состоять из нескольких файлов


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

## Импортируйте Veles через `veles.sdk`

`veles.sdk` — публичная поверхность, на которую опирается модуль; внутренности Veles
можно менять, не ломая модули. Модуль реестра **обязан** импортировать Veles только
оттуда — `veles registry validate` отклоняет остальное (тесты исключены).

| Модуль | Что в нём |
|---|---|
| `veles.sdk` | `Project`, `load_project`, `current_project`, `current_origin`, помощники для текста/слагов/времени |
| `veles.sdk.contributions` | типы точек ниже, `CommandHost`, `contributions`, `active`, `engine_enabled` |
| `veles.sdk.tools` | декоратор `@tool`, `RiskClass`, `TOOLSETS`, защита путей и записи, `fetch_url`, `read_file` |
| `veles.sdk.memory` | `RecallHit`, протоколы провайдеров памяти, `append_memory_log`, `write_proposal`, `escape_query` |
| `veles.sdk.layout` | `find_layout`, `LayoutManifest`, `load_context_file`, подпроекты |
| `veles.sdk.jobs` | `submit_oneshot_job`, `spawn` (агенты-исполнители), ограничение глубины делегирования |

Точка входа загружается как пакет с корнем в каталоге модуля, поэтому свои файлы модуль
импортирует относительно (`from .wiki import Wiki`).

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
| `page_store` | `PageStore(write, read, engine=None)` | хранит страницы: `/save` (категория `queries`) и страницу самодокументации (`self-doc/overview`); без него они идут в память |
| `cli_command` | `CliCommand(help, add_arguments, run, run_flags=False)` | команда `veles <name>`; `run(args, project, host)`, где `host.run_agent(...)` прогоняет один ход агента так же, как `veles run` |
| `slash_command` | `SlashCommand(run, summary, usage, engine=None)` | команда REPL `/<name>`; `run(project, arg) -> SlashReply(text, submit_prompt, error)` |
| `scaffold` | `fn(root, manifest)` | выполняется при применении раскладки к проекту |
| `background_op` | `BackgroundOp(kind, toolset, run)` | вид фоновой задачи daemon; `run(job, *, spawn_agent, project)` |
| `memory` | фабрика (через `api.add_memory_provider`) | внешний провайдер памяти |

Объекты с полем `engine` сами проверяют свой движок; остальные, если должны работать
только при включённом движке, проверяют `veles.sdk.contributions.engine_enabled(project, "<name>")`.
Встроенные команды и slash-команды сохраняют свои имена — модуль не может занять
`veles run` или `/help`.

## Объявить, что вносит модуль реестра

В реестре `provides` в `extension.toml` перечисляет каждый вклад как `<point>:<name>`
(а хуки — как `hook:<name>`). `veles registry validate --run-code` загружает модуль и
сверяет список с тем, что `register()` действительно внёс. Команда, объявленная как
`cli_command:<name>`, — это ещё и способ подсказать установку, когда кто-то набирает её
без модуля.

```toml
[extension]
name = "my-engine"
kind = "module"
provides = ["engine:my-engine", "prompt:my-engine"]
requires_extensions = []   # полные ссылки на нужные расширения, например "public:official/wiki"
```
