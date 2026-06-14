# Справочник по конфигурации

> 🌐 **Языки:** [English](../../en/reference/configuration.md) · **Русский**

Veles настраивается двумя TOML-файлами и набором каталогов состояния. Секреты
(API-ключи, токены ботов) **никогда** не записываются в эти файлы — они живут в
OS-keychain или переменных окружения (см. [переменные окружения](environment-variables.md)).

## Где живёт состояние

| Путь | Область | Содержимое |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, гранты доверия, межпроектные skills/tools, кэш моделей, локали, реестр |
| `<project>/.veles/` | Project-local | `project.toml`, `config.toml`, `memory.db`, проектные skills/tools, планы, рантайм-артефакты |
| `<project>/AGENTS.md` | Project | Файл контекста, вставляемый в агента (симлинкуется на `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Project | Пользовательский контент (макет LLM-Wiki по умолчанию) |

`VELES_USER_HOME` переопределяет `~` (так что состояние пользователя попадает в
`<override>/.veles/`). См. [структуру проекта](project-layout.md) для полного дерева.

---

## Пользовательская конфигурация — `~/.veles/config.toml`

Записывается мастером первоначальной настройки; можно безопасно редактировать вручную.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
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
| `[user] language` | `"en"` \| `"ru"` | Локаль строк UI (переопределяется через `VELES_LOCALE`) |
| `[user] default_provider` | string | Провайдер, используемый когда не задан явно |
| `[user] default_model` | string | Модель, используемая когда не задана явно |
| `[user] tui_theme` | string | Цветовая тема TUI по умолчанию |
| `[permissions] <tool>` | policy | Политика разрешений по инструментам (см. [доверие и песочница](../explanation/trust-and-sandbox.md)) |

---

## Проектная конфигурация — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base for the main agent + routing

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
| `[provider]` | Базовый провайдер/модель для основного агента и каскада маршрутизации |
| `[routing.tasks]` | Переопределения `provider:model` по задачам — см. [маршрутизация по задачам](../how-to/per-task-routing.md) |
| `[permissions]` | Политика разрешений по инструментам (проектная область) |
| `[daemon]` | Привязка + автозапуск безымянного/"default" демона |
| `[daemon.<name>]` | Именованная сессия демона (своя model/provider/host/port/mode) |
| `[channels.<type>]` | Канал, обслуживаемый безымянным демоном (например, `telegram`) |
| `[daemon.<name>.channels.<type>]` | Канал, привязанный к именованной сессии демона |
| `[mcp.servers.<name>]` | Внешний MCP-сервер (источник инструментов) |

Типы задач для `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> Подсказки маршрутизации на естественном языке в `AGENTS.md` парсятся в
> автогенерируемый `routing.nl.toml`; явные записи `[routing.tasks]` всегда побеждают.
> Выполните `veles route refresh`, чтобы перепарсить. См.
> [маршрутизацию по задачам](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` хранит неизменяемые метаданные проекта (`name`,
`created_at`, `schema_version`, `layout`). Обычно вы не редактируете его вручную.

---

## AGENTS.md

Файл контекста проекта в корне проекта. Он вставляется в системный промпт агента
при старте и симлинкуется на `CLAUDE.md` и `GEMINI.md`, так что `claude` или
`gemini` CLI, запущенный в каталоге, подхватывает тот же контекст.

Держите его маленьким — вспомогательные `.md`-файлы (например, `wiki/INDEX.md`)
загружаются по требованию. Проверьте обязательные секции командой
`veles schema validate`. См. [layout-паки и LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
