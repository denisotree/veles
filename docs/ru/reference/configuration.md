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
request_timeout_s = 180                              # необязательно; сколько ждать один ответ
max_retries = 1                                      # необязательно; повторов на запрос

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
| `[engine]` | Базовый провайдер (`provider` = имя провайдера) + модель (`model` = id модели) для основного агента и каскада маршрутизации, плюс клиентские бюджеты `request_timeout_s` / `max_retries` |
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

### Сколько ждать ответа и сколько раз повторять

```toml
[engine]
request_timeout_s = 180
max_retries = 1
```

Оба ключа — параметры **клиента**, поэтому лежат плоско в `[engine]`, а не в
`[engine.request.<provider>]`: та секция — тело запроса, а таймаут в теле не ездит.

Без них таймаут выводится из id модели: reasoning-семейство получает 900 с,
вариант `flash`/`mini` того же семейства — 450 с, всё остальное — 120 с. Это
догадка, и догадка структурно слабая: **имя описывает семейство, а время ответа
определяет обслуживающий бэкенд.** Один и тот же id выдаёт 33 ток/с на одном
бэкенде и 0.8 ток/с на другом. Если выведенное число не подходит вашему прогону —
задайте своё; а чтобы оно означало одно и то же дважды, запиньте бэкенд (ниже).

`max_retries` важен по той же причине. Без него SDK повторяет дважды, то есть
таймаут в 450 с — это до 1350 с на один ход, чего хватит, чтобы выбить бюджет,
который выглядел щедрым. `0` — легитимное значение и не то же самое, что
отсутствие ключа.

Приоритет у обоих: явный аргумент в коде → `[engine]` → значение по модели.
Значение, не являющееся положительным числом (а для `max_retries` — неотрицательным
целым), обрывает запуск ошибкой `ConfigError` с именем файла.

**Область действия:** сегодня эти ключи читает только адаптер OpenRouter. Клиенты
Anthropic, OpenAI и Gemini строятся без обоих параметров и ключи игнорируют.

### Пиннинг бэкенда и другие ключи тела запроса

`[engine.request.<provider>]` передаётся в тело запроса этого провайдера
**дословно**. Veles не моделирует схему апстрима, поэтому всё, что провайдер
принимает, работает сразу — не дожидаясь, пока Veles об этом узнает:

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

Ключ секции — **имя провайдера** (`openrouter`, `anthropic`, `openai`, `gemini`,
`ollama`, `llamacpp`, `openai-compat`), чтобы один конфиг проекта пережил смену
бэкенда: блок `provider` от OpenRouter, отправленный в llama.cpp, — это 400,
поэтому каждый бэкенд читает только свою подсекцию. Без объявленной секции
запросы байт в байт те же, что и раньше.

**Когда это нужно: воспроизводимые замеры.** Релей вроде OpenRouter раздаёт одну
модель по множеству бэкендов с разной квантизацией, поэтому два прогона на одном
и том же входе могут разойтись по причинам, не связанным со входом.
Sticky-routing по `session_id` удерживает один разговор на одном бэкенде, но
ничего не говорит о том, на **каком**.

Пиньте по `order`, а не по `quantizations`. На 18.09.2026 у
`z-ai/glm-5.3-flash` 29 эндпоинтов: 16 на `fp8`, 3 на `fp4`, один `nvfp4`,
**9 не объявляют квантизацию вообще** и ни одного на `bf16`. То есть
`quantizations = ["fp8"]` оставляет 16 кандидатов с контекстным окном от 262144
до 1310720 токенов, тогда как `order` из одного элемента плюс
`allow_fallbacks = false` определяет бэкенд однозначно. Список эндпоинтов
модели:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

Держите пин только в замерочном проекте — проду нужен sticky-routing, который
сохраняет доступность и fallback.

**Как проверить, что пин держался.** Каждый вызов модели записывает в
`.veles/traces.jsonl` и намерение, и результат: `request_extra` — что отправили,
`upstream_provider` — кто ответил. Одна строка на прогон говорит всё:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

Больше одной строки — прогон смешал бэкенды. Те же записи несут
`reasoning_tokens` (сколько бюджета ушло в размышление) и `est_cost_usd`
(фактическая стоимость по данным апстрима, когда он её сообщает).

**Ошибки намеренно громкие.** Опечатка в имени провайдера или в пути секции
(`[engine.reqest.…]`) прерывает прогон с `ConfigError`, называющим файл и
известные провайдеры: пин, который молча не доехал до провода, обесценил бы
замер, ради которого его и написали. Ключи **внутри** подсекции провайдера Veles
не проверяет, потому что их проверяет апстрим: OpenRouter отвечает
`400 provider: Unrecognized key: "quantization"` на неизвестный ключ и
`404 No endpoints found …` на значение, под которое ничего не подходит.

### Сколько хранятся транскрипты

**Ничего не удаляется, пока вы об этом не попросите.** `turn_retention_days`
по умолчанию равен `0` — все ходы разговора хранятся вечно. Задайте число дней,
чтобы поставить потолок для `memory.db`:

```toml
[memory]
turn_retention_days = 90   # 0 (по умолчанию) — хранить всё
```

Когда включено, сырые ходы старше этого срока удаляются, а **инсайты** и
правила, извлечённые из них, хранятся вечно независимо от настройки. Транскрипт —
сырьё, инсайты — то, ради чего его читали.

Удаление требует выполнения **двух** условий сразу: транскрипт старше окна **и**
куратор уже обработал эту сессию. Сессия, до которой куратор не дошёл, не
чистится никогда, каким бы ни был её возраст, — иначе транскрипт был бы
уничтожен раньше, чем из него что-то извлекли.

Цена включения: `veles sessions search` находит текст только внутри окна.
`veles sessions list` по-прежнему показывает старые прогоны, потому что строки
сессий (id, заголовок, время) сохраняются — уходят только тела сообщений.
Чистка выполняется во время `veles dream`, после извлечения инсайтов.

### Ротация логов

`traces.jsonl` и `events.jsonl` ротируются на 50 МБ в `<имя>.<unix_ts>`, при этом
сохраняются **10** последних ротаций — более старые удаляются при следующей
ротации. Раньше они хранились вечно.

При обычных объёмах настраивать ничего не нужно: при ~530 байтах на запись trace
и ~1.1 КБ событий на ход агента до первой ротации годы. Настройка существует
потому, что неограниченный рост без политики — это утечка, которую придётся
обнаруживать тому, кому достанется машина.

### Изображения

Фотография, присланная в канал, описывается до начала хода — моделью, на которую
указывает `[routing.tasks].vision`, а без явного маршрута это ваша модель из
`[engine]`. Мультимодальному движку поэтому не нужна никакая настройка.

`[vision] mode` выбирает конвейер:

- `model` (по умолчанию) — изображение описывает vision-модель.
- `ocr` — только Tesseract. Локально, бесплатно, без вызова LLM; хорошо для
  сканов текста.
- `ocr+model` — сначала дословный текст, затем описание модели.
- `off` — ничего не читается; файл всё равно сохраняется, и агент может сам
  вызвать `image_describe` / `image_ocr`, если захочет.

Задавайте `[vision] model`, когда движок работает только с текстом. Подойдёт
любой провайдер с поддержкой зрения, включая локальный сервер: `ollama:llava`,
`llamacpp:…`, `openai-compat:…`.

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
