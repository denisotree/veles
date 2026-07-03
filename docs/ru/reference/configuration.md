# Справочник по конфигурации

> 🌐 **Языки:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · **Русский** · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

Veles настраивается двумя файлами TOML и набором служебных каталогов. Секреты
(API-ключи, токены ботов) **никогда** не записываются в эти файлы — они хранятся
в keychain ОС или в переменных окружения (см. [переменные окружения](environment-variables.md)).

## Где хранится состояние

| Путь | Область | Содержимое |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, trust-разрешения, навыки/инструменты между проектами, кэш моделей, локали, реестр |
| `<project>/.veles/` | Project-local | `project.toml`, `config.toml`, `memory.db`, навыки/инструменты проекта, планы, runtime-артефакты |
| `<project>/AGENTS.md` | Project | Контекстный файл, внедряемый в агента (симлинкуется на `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Project | Пользовательский контент (раскладка LLM-Wiki по умолчанию) |

`VELES_USER_HOME` перенаправляет `~` (так что состояние пользователя попадёт в
`<override>/.veles/`). Полное дерево см. в [раскладке проекта](project-layout.md).

---

## Конфиг пользователя — `~/.veles/config.toml`

Пишется мастером первичной настройки; можно безопасно редактировать вручную.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Ключ | Тип | Назначение |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Локаль для строк интерфейса (переопределяется через `VELES_LOCALE`) |
| `[user] default_provider` | string | Провайдер, используемый, когда он не задан явно |
| `[user] default_model` | string | Модель, используемая, когда она не задана явно |
| `[user] tui_theme` | string | Цветовая тема TUI по умолчанию |
| `[permissions] <tool>` | policy | Политика прав по инструментам (см. [trust и песочница](../explanation/trust-and-sandbox.md)) |

---

## Конфиг проекта — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                              # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### Секции

| Секция | Назначение |
|---|---|
| `[engine]` | Базовый провайдер (`provider` = имя провайдера) + модель (`model` = id модели) для основного агента и каскада маршрутизации |
| `[routing.tasks]` | Переопределения `provider:model` по задачам — см. [маршрутизацию по задачам](../how-to/per-task-routing.md) |
| `[permissions]` | Политика прав по инструментам (область проекта) |
| `[daemon]` | Привязка + автозапуск неименованного/«default» демона |
| `[daemon.<name>]` | Именованная сессия демона (собственные model/provider/host/port/mode) |
| `[channels.<type>]` | Канал, обслуживаемый неименованным демоном (например, `telegram`) |
| `[daemon.<name>.channels.<type>]` | Канал, привязанный к именованной сессии демона |
| `[mcp.servers.<name>]` | Внешний MCP-сервер (источник инструментов) |

Типы задач для `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> Подсказки маршрутизации на естественном языке в `AGENTS.md` разбираются в
> автогенерируемый `routing.nl.toml`; явные записи `[routing.tasks]` всегда имеют
> приоритет. Запустите `veles route refresh` для повторного разбора. См.
> [маршрутизацию по задачам](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` содержит неизменяемые метаданные проекта (`name`,
`created_at`, `schema_version`, `layout`). Обычно его не редактируют вручную.

---

## AGENTS.md

Контекстный файл проекта в корне проекта. Он внедряется в системный промпт агента
при запуске и симлинкуется на `CLAUDE.md` и `GEMINI.md`, чтобы запущенный в этом
каталоге CLI `claude` или `gemini` подхватывал тот же контекст.

Держите его небольшим — вспомогательные `.md`-файлы (например, `wiki/INDEX.md`)
загружаются по требованию. Проверьте обязательные секции командой
`veles schema validate`. См. [layout-пакеты и LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
