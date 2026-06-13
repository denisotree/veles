# Справочник CLI

> 🌐 **Языки:** [English](../../en/reference/cli.md) · **Русский**

Все команды, подкоманды и флаги Veles. Выполните `veles <command> --help`, чтобы
получить авторитетную, всегда актуальную сигнатуру — эта страница повторяет парсеры
аргументов в `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — пропустить мастер первоначальной настройки, даже если
  `~/.veles/config.toml` отсутствует (также управляется наличием TTY и `VELES_NO_WIZARD=1`).
- Без аргументов `veles` запускает интерактивный [TUI](tui.md).

Большинство команд агента принимают [общие флаги цикла агента](#shared-agent-loop-flags)
и [имена провайдеров](#provider-names), перечисленные внизу.

---

## Жизненный цикл проекта

### `veles init [name]`
Создать новый проект Veles в текущем каталоге (каталог состояния `.veles/`
+ `AGENTS.md` + контент-скаффолд выбранного layout-пакета).

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `name` (positional) | cwd basename | Имя проекта |
| `--layout <name>` | `llm-wiki` | Layout-пакет для контент-скаффолда (`llm-wiki`, `notes`, `bare` или кастомный пакет из `~/.veles/layouts/`) |
| `--force` | off | Пересоздать `.veles/`, даже если он уже существует |

### `veles schema {validate,edit,fix}`
Проверить или отредактировать `AGENTS.md` (файл контекста проекта).

- `validate` — проверить наличие обязательных секций H2.
- `edit` — открыть `AGENTS.md` в `$EDITOR` (по умолчанию `vi`), проверить при выходе.
- `fix` — интерактивно добавить недостающие секции через LLM-мастер.

### `veles self-doc [refresh|show]`
Сгенерировать и показать самодокументацию проекта (`wiki/self-doc/overview.md`).
Просто `veles self-doc` показывает текущую страницу; `refresh` перегенерирует её.

### `veles doctor`
Запустить проверки состояния пользовательского глобального состояния и активного
проекта. Работает как с активным проектом, так и без него.

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `--json` | off | Выдать отчёт в формате JSON |
| `--strict` | off | Завершиться с ненулевым кодом при любом предупреждении (для CI) |

### `veles export {full,template} <path>`
Упаковать проект в бандл `.tar.gz`. См. [Резервное копирование и обмен](../how-to/backup-and-share.md).

- `full <path>` — весь проект (`.veles/` + `AGENTS.md`), без рантайм-эфемериды.
- `template <path>` — очищенное подмножество (схема + skills + modules + не-сессионные
  страницы вики); удаляет `memory.db`, `sources/`, `sessions/`, гранты `trust` и
  редактирует PII в тексте.

### `veles import <path>`
Восстановить бандл, созданный командой `veles export`.

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `path` (positional) | — | Путь к бандлу (`.tar.gz`) |
| `--into <dir>` | cwd | Целевой каталог |
| `--force` | off | Перезаписать существующий `.veles/` в целевом месте |

---

## Запуск агента

### `veles run "<prompt>"`
Выполнить один промпт от начала до конца с сохранением памяти и триггерами
куратора/обучения. Принимает все [общие флаги цикла агента](#shared-agent-loop-flags), а также:

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `--resume <session_id>` | new session | Продолжить существующую сессию |
| `--manager` | off | Декомпозировать через мультиагентного менеджера (также `VELES_MANAGER_MODE=1`) |
| `--plan` | off | Режим планирования: чтение/поиск/черновики разрешены, мутации заблокированы |
| `--no-agents-md` | off | Не вставлять `AGENTS.md` в системный промпт |
| `--no-index` | off | Не вставлять `wiki/INDEX.md` |
| `--no-compress` | off | Отключить компрессию контекста скользящим окном |
| `--no-curator` | off | Отключить триггеры куратора для этого запуска |
| `--no-insights` | off | Отключить извлечение инсайтов после запуска |
| `--no-proposer` | off | Отключить автотриггер предложения подпроектов |
| `--no-route-refresh` | off | Отключить обновление NL-маршрутизации из `AGENTS.md` |
| `--no-suggest-promote` | off | Отключить советчик автопромоушена |
| `--compressor-model <id>` | routed | Переопределить модель компрессии |
| `--compress-threshold-tokens <n>` | `50000` | Размер истории, запускающий компрессию |

### `veles tui`
Открыть интерактивный REPL. См. [Справочник по TUI](tui.md). Принимает общие флаги
цикла агента, `--resume`, перечисленные выше флаги `--no-*` для инъекции/компрессии, а также:

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `--theme <name>` | config or `everforest` | Цветовая тема (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
Прочитать источник (локальный файл или URL `http(s)://`) и синтезировать из него
страницу вики. Принимает общие флаги цикла агента.

### `veles curate`
Выполнить один проход куратора: уплотнить необработанные сессии в страницы `wiki/sessions/`.

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `--limit <n>` | a small default | Макс. число сессий для обработки за запуск |

Плюс общие флаги цикла агента.

### `veles research "<question>"`
Глубокое исследование: декомпозиция на подвопросы → параллельное исследование сети →
синтез отчёта со ссылками.

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `--max-subquestions <n>` | `4` | Параллельные направления исследования |

Плюс общие флаги цикла агента.

### `veles dream`
Выполнить один фоновый цикл консолидации памяти (инсайты → дедуп skills → предложения
промоушена → линт вики, опционально LLM-консолидация).

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `--include-consolidation` | off | Запустить дорогую LLM-консолидацию (нужен API-ключ) |
| `--dry-run` | off | Выполнить все шаги, но пропустить запись в `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | Пропустить отдельные шаги |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | Переопределить модель консолидации |
| `--provider <name>` | `openrouter` | Провайдер для субагента консолидации |
| `--project-root <path>` | discover | Переопределение проекта |

---

## Знания: skills, tools, modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Подкоманда | Назначение |
|---|---|
| `list` | Список skills в активном проекте (с телеметрией) |
| `show <name>` | Вывести `SKILL.md` навыка |
| `add <source> [--name N] [--scope project\|user] [-y]` | Установить из git-URL или локального пути |
| `remove <name> [--scope project\|user] [-y]` | Удалить установленный навык |
| `promote <name> [--keep-telemetry]` | Скопировать проектный навык в пользовательскую область (`~/.veles/skills/`) |
| `demote <name> [-y]` | Скопировать пользовательский навык в активный проект |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Найти почти дублирующиеся skills |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | Список навыков, удовлетворяющих планке автопромоушена |

### `veles tool {list,show,promote}`

| Подкоманда | Назначение |
|---|---|
| `list` | Список tools, каталогизированных в `memory.db` этого проекта |
| `show <name>` | Вывести манифест инструмента + телеметрию |
| `promote <name> [-y]` | Переместить проектный инструмент в `~/.veles/tools/` (межпроектный) |

### `veles module {list,show,add,remove}`

| Подкоманда | Назначение |
|---|---|
| `list` | Список установленных modules |
| `show <name>` | Вывести манифест модуля |
| `add <source> [--name N] [-y]` | Установить модуль из git-URL или локального пути |
| `remove <name> [-y]` | Удалить установленный модуль |

### `veles browse {modules,skills} [query]`
Обзор курируемых реестров.

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `query` (positional) | `""` | Фильтр по подстроке |
| `--source <url>` | canonical | Переопределить источник реестра |
| `--json` | off | Выдать JSON |

---

## Сессии и память

### `veles sessions {list,show,delete,search}`

| Подкоманда | Назначение |
|---|---|
| `list [--limit n]` | Список недавних сессий (по умолчанию 20) |
| `show <session_id>` | Вывести полную историю ходов сессии |
| `delete <session_id>` | Удалить сессию и её ходы |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Полнотекстовый (FTS5) поиск по содержимому ходов |

---

## Мультипроектность

### `veles project {list,add,remove,switch}`

| Подкоманда | Назначение |
|---|---|
| `list` | Список зарегистрированных проектов, недавние первыми |
| `add <path> [--slug S]` | Зарегистрировать существующий каталог проекта |
| `remove <slug>` | Снять регистрацию проекта (файлы не трогаются) |
| `switch <slug>` | Вывести абсолютный путь проекта (используйте `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Подкоманда | Назначение |
|---|---|
| `init <subdir> [--name N] [--description D]` | Создать + зарегистрировать подпроект |
| `list` | Список подпроектов активного проекта |
| `switch <slug>` | Вывести абсолютный путь подпроекта |
| `remove <slug>` | Снять регистрацию подпроекта |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Обнаружить тематические кластеры и предложить подпроекты |

---

## Маршрутизация и модели

### `veles route {show,set,reset,refresh}`
Ансамблевая маршрутизация по задачам — какой `provider:model` обрабатывает каждый тип
задач (`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`). См. [маршрутизация по задачам](../how-to/per-task-routing.md).

| Подкоманда | Назначение |
|---|---|
| `show` | Вывести разрешённую таблицу маршрутизации для активного проекта |
| `set <task> <provider:model>` | Закрепить задачу за спецификацией |
| `reset [task]` | Сбросить одну задачу (или все) к значениям по умолчанию |
| `refresh [--force]` | Заново распарсить подсказки маршрутизации на естественном языке из `AGENTS.md` |

### `veles models <provider>`
Список моделей для провайдера. Облачные провайдеры (openrouter/openai/gemini)
кэшируются на 24ч; локальные провайдеры всегда живые.

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `provider` (positional) | — | Один из [имён провайдеров](#provider-names) |
| `--refresh` | off | Обойти дисковый кэш (только облачные) |
| `--json` | off | Выдать `{provider, source, models}` как JSON |

---

## Долгоиграющие задачи

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Долгосрочные цели с бюджетами и контрольными точками.

| Подкоманда | Назначение |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | Список целей |
| `show <id> [--json]` | Показать одну цель |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | Создать цель |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | Дописать прогресс |
| `pause <id>` / `resume <id>` | Пауза / возобновление |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Завершить / отменить |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Запланированные задания агента.

| Подкоманда | Назначение |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | Создать задание (schedule = cron, `<N><s\|m\|h\|d>` или ISO-таймстамп) |
| `list [--json]` / `show <id>` | Инспекция заданий |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Жизненный цикл |
| `history <id> [--limit n]` | Недавние запуски |
| `tick` | Синхронно выполнить все наступившие задания один раз (демон не нужен; принимает флаги цикла агента) |

---

## Безопасность и контроль доступа

### `veles trust {list,set,revoke,clear}`
Сохранённые гранты для чувствительных tools (`run_shell`, `write_file`, `fetch_url`, …).
См. [безопасность](../how-to/security-and-permissions.md).

| Подкоманда | Назначение |
|---|---|
| `list` | Показать гранты (пользовательская + проектная область) |
| `set <tool> [--scope project\|user]` | Выдать грант инструменту |
| `revoke <tool> [--scope project\|user\|both]` | Удалить грант |
| `clear [--scope project\|user\|all]` | Очистить гранты в области |

### `veles autopilot {enable,disable,status}`
Ограниченное по времени окно, в котором запросы лестницы доверия авторазрешаются.

| Подкоманда | Назначение |
|---|---|
| `enable --until <DUR>` | Открыть окно (`+30m`, `+2h`, `+1d` или ISO `2026-05-12T18:00:00Z`) |
| `disable` | Закрыть окно сейчас |
| `status` | Сообщить, активен ли автопилот |

### `veles secret {set,get,list,delete}`
Секреты на базе OS-keychain (API-ключи, токены ботов).

| Подкоманда | Назначение |
|---|---|
| `set <name> [value]` | Сохранить (опустите value для интерактивного / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Найти (по умолчанию резерв через env) |
| `list` | Показать, какие канонические секреты настроены |
| `delete <name>` | Удалить секрет |

---

## Демон и каналы

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Запуск/управление демоном HTTP+WS. Просто `veles daemon` открывает **выбор демона**
в TUI (проект → демоны → каналы). См. [запуск как демон](../how-to/run-as-daemon.md).

| Подкоманда | Назначение |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Запустить демон (по умолчанию отсоединяется) |
| `stop [--name N]` / `status [--name N]` | Остановить / инспектировать |
| `list` | Список демонов по всем проектам |
| `restart [target] [--name N]` | Остановить + перезапустить на том же host/port |
| `delete <target> [-y]` | Остановить + удалить из реестра |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Объявить именованную сессию демона |
| `session list [--all]` / `session delete <name>` | Управление именованными сессиями |
| `token add <name>` / `token list` / `token remove <name>` | CRUD bearer-токенов |

`start` также принимает общие флаги цикла агента; для демона `--model` /
`--provider` по умолчанию берутся из конфигурации проекта и фиксированы на всё время жизни демона.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
Внешние чат-шлюзы (Telegram, …), которые общаются с демоном. См.
[подключение Telegram](../how-to/connect-telegram.md).

| Подкоманда | Назначение |
|---|---|
| `list` | Список зарегистрированных платформ каналов + счётчики сессий |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | Запустить шлюз на переднем плане |
| `list-sessions [--channel C]` | Показать сопоставления `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | Забыть сопоставление (следующее сообщение начинается заново) |
| `add [--channel C] [--session S]` | Привязать канал к демону (мастер; учётные данные → keychain) |
| `remove <channel> [--session S]` | Удалить привязку канала |

---

## MCP (внешние серверы инструментов)

### `veles mcp {list,test}`
Инспекция внешних MCP-серверов, настроенных в `[mcp.servers.*]`. См.
[внешние MCP-серверы](../how-to/external-mcp-servers.md).

| Подкоманда | Назначение |
|---|---|
| `list [--connect-timeout f]` | Показать настроенные серверы, статус подключения, число инструментов |
| `test <server>` | Подключиться к одному серверу и вывести его инструменты |

---

## Общие флаги цикла агента

Принимаются командами `run`, `add`, `tui`, `curate`, `research`, `job tick` и `daemon
start`:

| Флаг | По умолчанию | Назначение |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: persisted) | ID модели |
| `--provider <name>` | `openrouter` | Провайдер (см. ниже) |
| `--max-tokens-total <n>` | `100000` | Совокупный бюджет токенов; `0` отключает |
| `--max-iterations <n>` | `30` | Макс. число итераций вызова инструментов за ход |
| `--stream` | off | Стримить ответ токен за токеном |
| `--verbose` / `-v` | off | Прогресс по ходам в stderr |
| `--project-root <path>` | discover from cwd | Работать с проектом в другом месте |

## Имена провайдеров

`openrouter` (по умолчанию) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Локальные провайдеры (`ollama`, `llamacpp`, `openai-compat`) не требуют API-ключа. См.
[справочник по провайдерам](providers.md) и [настройку провайдеров](../how-to/configure-providers.md).
