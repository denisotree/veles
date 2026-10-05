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
| `veles.sdk.channels` | контракт канала: `PlatformSpec`, `ChannelContext`, `ChannelCaps`, `ChannelGateway`, `CredField`, `RunBackend`, `RunBackendError`, `SessionMap` |
| `veles.sdk.channel_checks` | проверки, которые тесты модуля канала гоняют на его spec: `check_builds_from_config`, `check_config_keys`, `check_delivers` |
| `veles.sdk.media` | адаптеры распознавания речи и зрения, которые канал использует для голоса и изображений |
| `veles.sdk.providers` | контракт LLM-провайдера: `ProviderSpec`, `ProviderContext`, типы ответа и база CLI-делегата (`CLIProvider`, `delegate_dir`, `veles_mcp_server`) |

Точка входа загружается как пакет с корнем в каталоге модуля, поэтому свои файлы модуль
импортирует относительно (`from .wiki import Wiki`).

## Что может входить в модуль

Один модуль может собрать всё, что нужно функции, — тогда он ставится и переиспользуется
целиком:

- **инструменты** — вклад `ToolSet` (см. ниже);
- **навыки** — `skills/<name>/SKILL.md` в каталоге модуля. Они подключаются в каждом
  проекте, который загружает модуль, ниже собственных навыков проекта и пользователя
  (ваш навык с тем же именем побеждает) и выше навыков раскладки. Править их нельзя: они
  часть одобренного дерева модуля, поэтому правка любого из них выключает весь модуль,
  пока его не одобрят снова;
- **движки контента, команды CLI, команды `/`, recall, блоки промпта и шаги dream, хуки,
  провайдеры памяти, платформы каналов** — точки вклада ниже;
- **строки** — `locales/<lang>.toml` в каталоге модуля, плоские ключи без заголовка
  таблицы. Veles подмешивает их под именем модуля: `hello = "Hi"` в модуле `telegram`
  — это `t("telegram.hello")`. Ключ, который определяет сам Veles, побеждает ключ
  модуля.

```text
my-suite/
  module.toml
  __init__.py          # register(api): наборы инструментов, команды, хуки…
  tools.py
  skills/
    triage/SKILL.md     # подключается как навык `triage`
```

### Комбинированные модули

Модуль может опираться на другие: перечислите нужные модули, раскладки и навыки в
`requires_extensions` его `extension.toml`. Установка ставит всю цепочку под одним
подтверждением, зависимости первыми, туда же, куда сам модуль (в проект или, с `--user`,
пользователю); если какая-то часть не встала, от этой установки ничего не остаётся.

```toml
# suite — переиспользует модуль `base`, который сам приносит навык `helper`
[extension]
name = "suite"
kind = "module"
requires_extensions = ["public:official/base"]

# base
[extension]
name = "base"
kind = "module"
requires_extensions = ["public:official/helper"]
```

`veles registry install suite` поставит `helper`, `base` и `suite`.

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
| `platform` | `PlatformSpec(build, caps, cred_fields, config_keys)` | платформа обмена сообщениями, которую daemon держит как канал (см. ниже) |
| `provider` | `ProviderSpec(label, build, …)` | LLM-провайдер в каталоге: `--provider <name>`, `veles models`, маршруты и мастера (см. ниже); встроенные id зарезервированы |

Объекты с полем `engine` сами проверяют свой движок; остальные, если должны работать
только при включённом движке, проверяют `veles.sdk.contributions.engine_enabled(project, "<name>")`.
Встроенные команды и slash-команды сохраняют свои имена — модуль не может занять
`veles run` или `/help`.

## Платформа канала

Модуль канала вносит `PlatformSpec` под именем платформы; daemon собирает по одному
шлюзу на каждый блок `[channels.<name>]` через `build(ctx)`:

```python
from veles.sdk.channels import ChannelCaps, ChannelContext, CredField, PlatformSpec


def _build(ctx: ChannelContext):
    # ctx.config: the channel block; ctx.secrets: the resolved secret fields;
    # ctx.backend: submit runs, stream events, answer prompts;
    # ctx.session_map: chat id → session; ctx.project
    return MyGateway(token=ctx.secrets["token"], backend=ctx.backend, sessions=ctx.session_map)


SPEC = PlatformSpec(
    build=_build,
    caps=ChannelCaps(asks_questions=True),  # the agent may ask the chat and wait
    cred_fields=(CredField("token", "Bot token", secret=True, required=True, env="MY_TOKEN"),),
    config_keys=frozenset({"room"}),  # other keys its block may hold
)


def register(api) -> None:
    api.contribute("platform", "mychat", SPEC)
```

У шлюза есть `start()`, `stop()` и `deliver(chat_id, text, thread_id=None)` — последний
нужен, чтобы запланированные задачи доходили до чата (`deliver_to = "mychat:<chat_id>"`).
Секретные поля лежат в keychain ОС: первое — в слоте `<platform>`, остальные — в
`<platform>.<key>`; их спрашивает `veles channel add`. Ключ в блоке, который не является
ни полем учётных данных, ни частью `config_keys`, считается опечаткой. Логгеры шлюза
пишут в лог daemon. Собственные тесты модуля проверяют spec через
`veles.sdk.channel_checks`, а в `extension.toml` он указывается как `provides =
["platform:mychat"]`.

## LLM-провайдер

Модуль-провайдер вносит `ProviderSpec` под id провайдера. `build(ctx)` получает
`ProviderContext` (`name`, `model`, `project`) и возвращает объект с
`create_message(messages, tools=None, *, model, max_tokens)` — и `stream_message` с
`list_models`, если умеет:

```python
from veles.sdk.providers import ProviderResponse, ProviderSpec, TokenUsage


class EchoProvider:
    name = "echo"
    supports_tools = False
    supports_streaming = False

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        return ProviderResponse(text=messages[-1].content, tool_calls=[], usage=TokenUsage())


SPEC = ProviderSpec(label="Echo", build=lambda ctx: EchoProvider(), model_list="live")


def register(api) -> None:
    api.contribute("provider", "echo", SPEC)
```

`model_list` задаёт, как его перечисляет `veles models`: `live` спрашивает
`list_models()` каждый раз, `cached` хранит список 24 часа, `curated` берёт таблицу
Veles. Провайдер, чей ключ лежит в keychain, называет свои переменные в `key_env` и
получает ключ сам.

**CLI-делегат** — агентный CLI в headless-режиме — наследует `CLIProvider` и описывает,
как собрать команду (`_build_cmd`), где её запускать (`_cwd`) и как читать поток событий
(`_new_state`); запуск, стриминг и ошибки общие. Его сборка `build_tool_aware` даёт CLI
инструменты Veles по MCP: запишите конфиг вокруг `veles_mcp_server(project)` внутри
`delegate_dir(project)` (каталог запущенного процесса, удаляется при выходе) и задайте
`mcp_tool_name` — как CLI называет MCP-инструмент, чтобы промпты называли инструменты
Veles именно так. Полный пример — `official/antigravity-cli` в публичном реестре. В
`extension.toml` провайдер указывается как `provides = ["provider:<id>"]`: тогда id в
конфиге, маршруте или `--provider` устанавливает модуль.

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
requires_extensions = []   # полные ссылки на нужные модули/раскладки/навыки, например "public:official/wiki"
```
