# Как управлять навыками, инструментами и модулями

> 🌐 **Языки:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · **Русский** · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles накапливает возможности со временем. **Навыки** (skills) — это переиспользуемые
рабочие процессы, **инструменты** (tools) — исполняемые действия, **модули** (modules) —
опциональные плагины. Каждый существует в двух областях: проектной
(`<project>/.veles/`) и пользовательской глобальной (`~/.veles/`). О концепциях см.
[навыки и инструменты](../explanation/skills-and-tools.md).

## Навыки

Навык — это `SKILL.md` (frontmatter + тело промпта), который агент может вызывать
как инструмент.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Повышение / понижение между областями

Навык, доказавший пользу в одном проекте, можно перенести в пользовательскую область,
чтобы его видел каждый проект (или наоборот):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Поиск дубликатов и кандидатов на повышение

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Инструменты

Инструменты каталогизированы в `memory.db` проекта вместе с телеметрией
использования. Veles может писать собственные инструменты в процессе работы; вы
управляете ими через:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Чувствительные инструменты (`run_shell`, `write_file`, `fetch_url`, …)
регулируются [лестницей доверия](security-and-permissions.md).

## Модули

Модуль — это Python-код (`module.toml` + точка входа), который выполняется
внутри Veles: добавляет опциональные возможности (провайдеры памяти,
embeddings, vision, STT), не раздувая ядро. Установка по умолчанию требует
подтверждения, а загружается модуль при каждом запуске только пока его файлы
совпадают с тем, что вы одобрили (см. [держать установленное в
порядке](extension-registries.md#держать-установленное-в-порядке)).

```bash
veles module list                              # обе области, колонка `scope`
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # установка в ~/.veles/modules/, для всех проектов
veles module show <name> [--user]
veles module remove <name> [--user]
veles module approve <name> [--user]
```

Модули, как навыки и инструменты, существуют в двух областях: проектной
(`<project>/.veles/modules/`) и пользовательской глобальной
(`~/.veles/modules/`, грузится в каждом проекте). Пользовательский модуль
проходит тот же гейт одобрения, что и проектный. Если модуль с одним именем
есть и в проекте, и на уровне пользователя, грузится проектный, а про
пользовательский выводится предупреждение о том, что он перекрыт; два модуля
с одинаковым именем в одной области — грузится первый (по сортировке
каталога), остальные пропускаются с предупреждением.

### Написать модуль, добавляющий провайдер памяти

Точка входа модуля `register(api)` может вызвать
`api.add_memory_provider(name, factory)`, чтобы подключить внешний источник
памяти к recall. `name` должно совпадать с секцией `[memory.external.<name>]`
в `~/.veles/config.toml`; `factory` вызывается с этой секцией (`dict`) и
должна вернуть объект, реализующий протокол `MemoryProvider`
(`veles.core.memory.provider`), либо `None`, чтобы пропустить провайдер:

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # запрос к внешнему хранилищу, вернуть объекты RecallHit


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

Провайдер, который дополнительно реализует `ingest(title, body, *,
insight_id) -> bool` (протокол `IngestingMemoryProvider`), получает и записи
Veles, а не только чтение. Если два модуля регистрируют одно и то же имя
провайдера, второй `register()` падает — этот модуль пропускается с
предупреждением, ничего частично не остаётся зарегистрированным. Секция,
настроенная в `config.toml`, чей модуль не установлен, печатает одно
предупреждение с командой установки; recall продолжает работать без него.

В реестре уже есть готовые модули-провайдеры Honcho, Mem0 и Supermemory —
ставятся командой `veles registry install --user {honcho,mem0,supermemory}`,
затем нужно выполнить команду `uv tool install veles-ai --with '<package>'`,
которую печатает установка (каждый модуль объявляет SDK — `mem0ai>=2.0`,
`honcho-ai>=2.5`, `supermemory>=3.62` — который сам Veles не ставит), и
заполнить соответствующую секцию `[memory.external.<name>]`:

- **mem0**: `api_key`, `user_id`, опционально `agent_id` (recall захватывает
  и память этого агента) и `host`. Телеметрия SDK по умолчанию выключена;
  каждый recall делает один дополнительный запрос `GET /v1/ping/`.
- **supermemory**: `api_key`, опционально `user_id` (передаётся как
  `container_tag` поиска) и `base_url`.
- **honcho**: `api_key`, `workspace_id`, опционально `peer_id` (искать
  только сообщения этого peer) и `base_url`. Каждый recall делает
  get-or-create воркспейса — `workspace_id` создаётся, если его ещё нет.

## Поиск новых

Ищите в подключённых реестрах расширений и ставьте проверенные навыки,
инструменты и модули — см. [Установка расширений из реестров](extension-registries.md):

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
veles registry install <name>
```
