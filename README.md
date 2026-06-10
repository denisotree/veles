# Veles

Минималистичный агентский фреймворк: чистый декомпозированный код, компаундирующая память по каждому проекту, прозрачная автономия и открытые интерфейсы.

Veles не похож на «чатик с историей»: он ведёт **по каждому проекту персональную LLM-wiki** — структурированную базу знаний, которая накапливается с течением времени. Curator консолидирует сессии, lint ищет противоречия, embedding-distance отлавливает дубликаты скиллов, агент сам предлагает декомпозицию подпроектов, когда wiki разрастается. Никакого облака — всё локально, SQLite + файловая система.

---

## Содержание

- [Чем Veles отличается](#чем-veles-отличается)
- [Установка](#установка)
- [Первый запуск](#первый-запуск)
- [Структура проекта](#структура-проекта)
- [Базовые команды](#базовые-команды)
- [Безопасность](#безопасность)
- [Маршрутизация моделей (ensembles)](#маршрутизация-моделей-ensembles)
- [Скиллы и модули](#скиллы-и-модули)
- [TUI](#tui)
- [Daemon + каналы (Telegram)](#daemon--каналы-telegram)
- [Multi-project и подпроекты](#multi-project-и-подпроекты)
- [Памятка по командам](#памятка-по-командам)

---

## Чем Veles отличается

1. **Компаундирующая память.** По каждому проекту ведётся LLM-wiki: накопленные знания не переоткрываются на каждом запросе, а живут как структурированный артефакт. Curator консолидирует завершённые сессии в wiki непрерывно, lint ищет противоречия, telemetry скиллов влияет на их продвижение и архивацию.

2. **Двумерная декомпозиция.** Между проектами знания не смешиваются (sandbox). Внутри проекта агент сам видит смысловые кластеры в wiki и предлагает выделить подпроект — пользователь одобряет.

3. **Backend-агностичность + ансамбли.** OpenRouter, Anthropic, OpenAI, Gemini напрямую через API + `claude` / `gemini` CLI через подписку. Ансамбли (разные модели на разные типы задач) настраиваются типизированно (`routing.toml`) **или** на естественном языке прямо в `AGENTS.md` проекта.

4. **Модульность + open interfaces.** Минимальное ядро (память, learning loop, agent loop, провайдер-протокол, реестр инструментов). Всё остальное — опциональные модули и скиллы.

5. **Local-first + sandbox.** Агент видит только активный проект (с подпроектами) и `~/.veles`. Никаких других проектов, никаких сетевых вызовов мимо выбранного LLM. Trust ladder при каждой чувствительной операции.

---

## Установка

**Требования:** Python 3.13+, macOS/Linux. Windows — best-effort.

```sh
# 1. uv (если ещё нет)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Глобальная установка из директории с исходниками
cd /path/to/veles          # директория, где лежит pyproject.toml
uv tool install .

# 3. Проверка
veles --help
```

После `uv tool install .` команда `veles` доступна глобально в PATH — в любой директории, без `uv run`. `uv` создаёт изолированное venv и прописывает шим в `~/.local/bin/` (или эквивалент для вашей ОС).

Если нужна быстрая проверка без глобальной установки — `uv run veles --help` из директории с исходниками тоже работает.

При обновлении исходников запустите `uv tool install . --reinstall`, чтобы обновить глобальный шим.

**API-ключ** (минимум один):

| Провайдер   | Env var                              | Где взять                         |
|-------------|--------------------------------------|-----------------------------------|
| OpenRouter  | `OPENROUTER_API_KEY`                 | openrouter.ai (рекомендуется)     |
| Anthropic   | `ANTHROPIC_API_KEY`                  | console.anthropic.com             |
| OpenAI      | `OPENAI_API_KEY`                     | platform.openai.com               |
| Gemini      | `GEMINI_API_KEY` или `GOOGLE_API_KEY`| ai.google.dev                     |

OpenRouter — дефолтный провайдер; через него доступны и Claude, и GPT, и Gemini одним ключом. Альтернатива — подписка на `claude` или `gemini` CLI; в этом случае Veles запускает их как subprocess и работает координатором (`--provider claude-cli` / `--provider gemini-cli`).

---

## Первый запуск

```sh
export OPENROUTER_API_KEY=sk-or-v1-...
mkdir my-knowledge-base && cd my-knowledge-base

# Wizard: язык, провайдер по умолчанию, имя проекта.
# При первом запуске любой команды Veles предложит его пройти автоматически.
veles init my-kb

# Обычный запрос.
veles run "Изучи AGENTS.md и опиши проект в трёх предложениях."
```

После `veles init` появляется директория `.veles/` с конфигом проекта и `AGENTS.md` — короткий схема-файл, который агент видит в начале каждой сессии. Его стоит подредактировать под свой workflow:

```sh
veles schema edit            # открывает AGENTS.md в $EDITOR
veles schema validate        # проверяет, что обязательные секции на месте
```

---

## Структура проекта

```
my-kb/
├── AGENTS.md          # схема + конвенции + workflow проекта
├── INDEX.md           # каталог wiki (обновляется атомарно)
├── LOG.md             # append-only журнал: ## [date] op | description
├── sources/           # raw immutable источники (агент только читает)
│   └── <category>/
├── wiki/              # writable LLM-зона: единственное место, куда агент пишет
│   ├── concepts/
│   ├── entities/
│   ├── insights/      # выжимки из turn'ов
│   ├── sessions/      # компактификации сессий
│   ├── proposals/     # предложения от агента (подпроекты, promote скиллов)
│   └── queries/       # сохранённые ответы query/TUI /save
├── .veles/            # state (не в git): memory.db, telemetry, routing, ...
└── CLAUDE.md, GEMINI.md → AGENTS.md   # симлинки для совместимости
```

Это раскладка Karpathy LLM Wiki — три слоя (sources / wiki / schema), три операции (ingest / query / lint). Если пишешь другую структуру — опиши её в `AGENTS.md`, и Veles привяжет операции к твоим путям.

---

## Базовые команды

### Запуск + разговор

```sh
veles run "<prompt>"                       # одиночный запрос
veles run --resume <session_id> "<prompt>" # продолжить сессию
veles run --stream "<prompt>"              # streaming ответ в stdout
veles run --provider anthropic "<prompt>"  # выбрать провайдера явно
veles run --model anthropic/claude-opus-4-7 "<prompt>"
```

После запуска Veles печатает `<session=...>` — этот id можно использовать в `--resume`.

### Ingest / query / lint — LLM Wiki workflow

```sh
veles ingest paper.pdf                  # прочитать источник, записать wiki-страницу
veles ingest https://example.com/post   # PDF, текст, изображения (Tesseract OCR), web
veles query "что мы знаем про X?"       # ответ через wiki + memory recall
veles query "..." --save                # сохранить ответ как wiki-страницу
veles lint                              # детерминированный health-check wiki
veles lint --llm                        # дополнительно LLM-проход на противоречия
veles lint --save                       # отчёт в wiki/insights/lint-<UTC>.md
veles curate                            # явная консолидация сессий → wiki/sessions/
```

Curator работает непрерывно (idle pre-run + post-turn) автоматически. Insight extraction после каждого `veles run` ловит фразы вроде «запомни X», «никогда не делай Y» и пишет их в `wiki/insights/`.

### Сессии

```sh
veles sessions list                      # последние сессии
veles sessions show <id>                 # печать всех turn'ов
veles sessions delete <id>
veles sessions search "<query>"          # FTS5-поиск по содержимому turn'ов
veles sessions search "<q>" --since 7d --role user
```

### Wiki

```sh
veles wiki reindex                       # перестроить FTS5-индекс wiki/
```

---

## Безопасность

Veles разработан под автономную работу с осторожностью по умолчанию.

### Sandbox

Агент видит только:
- активный проект (CWD с подпроектами);
- user-global `~/.veles/` (скиллы, модули, конфиг).

Другие проекты из реестра — невидимы без явного переключения. Симлинки за пределы — отбрасываются. `..`-traversal — refuse.

### Trust ladder per-операция

При каждой sensitive-операции (`run_shell`, `write_file`, `fetch_url`) пользователь получает 4-option выбор:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once (this call only)
  [2] Always for this project
  [3] Always everywhere
  [4] Refuse
```

Решения 2/3 persist'ятся в `<project>/.veles/trust.json` или `~/.veles/trust.json`. Без TTY — refuse по умолчанию (CI-safe).

Программный CRUD:

```sh
veles trust list                         # текущие grant'ы (project + user scope)
veles trust set run_shell --scope user   # пред-grant без интерактива
veles trust revoke run_shell             # снять grant из обоих scope'ов
veles trust clear --scope all            # обнулить
```

### Autopilot — временный bypass

```sh
veles autopilot enable --until +2h       # 2 часа без trust-prompt'ов
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Каждый dispatch при активном autopilot пишется в `LOG.md` как `op="autopilot-<tool>"` для аудита. **Always-confirm операции** (удаление файлов, install module/skill, запись за пределы проекта) не bypass'ятся autopilot'ом — для них требуется явный `yes`.

---

## Маршрутизация моделей (ensembles)

Разные задачи (curator / insights / compressor / advisor / vision / embedding) могут идти к разным моделям.

### Типизированный TOML

```sh
veles route show                                    # текущая таблица
veles route set compressor anthropic:claude-haiku-4-5-20251001
veles route set vision openai:gpt-4o
veles route reset compressor                        # обратно к дефолту
```

### Natural-language override в AGENTS.md

В `AGENTS.md` достаточно написать:

```markdown
## Routing

Use Opus for planning and architecture. Default to Sonnet for everyday tasks.
Haiku is fine for compression and insight extraction.
Vision queries should go through gpt-4o.
```

И:

```sh
veles route refresh                                 # вручную распарсить хинты
```

После refresh: `veles route show` покажет источник каждой записи (`project` / `nl` / `default`). **Manual `veles route set` всегда побеждает NL-парсинг.** Auto-refresh запускается при `veles run` если AGENTS.md изменился — отдельный LLM-вызов раз в N дней, не на каждый turn.

### Advisor pattern

Базовая модель может вызвать `advisor_review` как инструмент в checkpoint'ах (план, архитектурное решение, финальный ответ). Маршрутизируется через task `advisor` — обычно идентичная или старшая модель.

---

## Скиллы и модули

### Скиллы (Skills)

Skill — это директория с `SKILL.md` (frontmatter + body) — переиспользуемый промт-блок. Скиллы автоматически становятся tools, доступными агенту.

```sh
veles skill list                                    # все скиллы + телеметрия
veles skill add <git-url>                           # установить из github
veles skill add ./local-path                        # установить из локальной директории
veles skill add ./auth-skill --scope user           # сразу в ~/.veles/skills/
veles skill remove <name>
veles skill promote <name>                          # project → user-level
veles skill demote <name>                           # user → project
veles skill dedup                                   # найти дубликаты (embedding/TF-IDF)
veles skill suggest-promote --save                  # предложить promotion на основе телеметрии
```

При промоушене скилл становится доступен **во всех** проектах пользователя.

### Модули (Plugins)

Модуль — Python-плагин с `module.toml` и hook-функцией, которая может перехватывать события агента (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`, `on_session_start`, `on_session_end`).

```sh
veles module list
veles module add <git-url-or-path>
veles module remove <name>
```

Pre-tool-call hook может **наложить veto** на dispatch — это user-side guard поверх trust ladder.

---

## TUI

Интерактивный Textual-приложение поверх агентского loop'а — `veles tui`. Hybrid layout: append-only scrollback с ассистент-ответами, сворачиваемый inspector с live tool-activity, multiline composer внизу.

```sh
veles tui                                           # новая сессия
veles tui --resume <session_id>                     # продолжить
```

Хоткеи:

```
Enter                 — отправить
Shift+Enter           — newline в composer
Ctrl+G                — открыть $EDITOR на текущем черновике
Tab                   — цикл по slash-командам (auto-complete)
Up / Down             — история (если composer пуст и нет очереди);
                        пуст и очередь не пуста → редактировать последний queued
Ctrl+I                — toggle inspector (thinking + tool-activity)
Ctrl+R                — overlay picker сессий
Ctrl+T                — overlay picker тем
Ctrl+D                — выход
Esc                   — закрыть overlay / отменить навигацию по истории
```

Слэш-команды:

```
/help                       — справка
/quit, /q, /exit            — выход
/clear                      — новая сессия (чистит scrollback)
/session                    — текущий session_id
/save <slug>                — последний ответ → wiki/queries/<slug>.md
/history [N]                — последние N сессий
/load [<session_id>]        — без аргумента: picker; иначе: переключиться
/show [N]                   — последние N сообщений текущей сессии
/wiki list                  — категории + counts
/wiki read <rel_path>       — отрендерить wiki-страницу
/wiki search <query>        — FTS5 поиск по wiki
/search <query>             — FTS5 поиск по всем turn'ам сессий
/model [<id>]               — без аргумента: picker; иначе: установить
/theme show|list|use [<n>]  — `use` без имени открывает picker
/schema validate|fix        — `fix` пока запускайте `veles schema fix` из шелла
/init                       — пока запускайте `veles init` из шелла
/self-doc                   — обновить self-документацию проекта
```

История ввода персистится в `~/.veles/tui_history.jsonl`. Approval/trust-prompts на sensitive tool dispatching открываются модальным overlay'ем (y/N для approval, 1-4 для trust ladder).

---

## Daemon + каналы (Telegram)

`veles daemon` — long-running процесс с HTTP+WebSocket API, чтобы внешние клиенты (TUI-клиенты, IDE-плагины, channel-модули) могли драйвить агент без re-exec'а CLI.

### Запустить daemon

```sh
veles daemon token add default           # создать bearer-токен (один раз)
veles daemon start                       # foreground, 127.0.0.1:8765 по умолчанию
veles daemon status                      # проверить статус в другом терминале
veles daemon stop                        # SIGTERM через PID-файл
```

API:
- `GET /v1/health` — без auth, статус.
- `POST /v1/runs` — submit prompt, возвращает `run_id`.
- `WS /v1/runs/{run_id}/events` — стримит `started → text_delta* → completed/error`.
- `GET /v1/sessions[?limit=N]` — список сессий.

Все endpoint'ы (кроме `/v1/health`) требуют `Authorization: Bearer <token>`.

### Telegram-бот поверх daemon

```sh
# 1. Создай бота через @BotFather, получи токен.
export TELEGRAM_BOT_TOKEN=...
export VELES_DAEMON_URL=http://127.0.0.1:8765
export VELES_DAEMON_TOKEN=vd_...

# 2. Запусти channel-процесс (требует уже запущенный daemon).
veles channel run --channel telegram
```

Каждое сообщение пользователя боту → новый turn в daemon. Маппинг chat_id ↔ session_id персистится в `~/.veles/channels/telegram-sessions.json` — разговор с ботом остаётся continuous между перезапусками.

```sh
veles channel list-sessions              # активные маппинги
veles channel reset-session <chat_id>    # начать с пользователем заново
```

В чате с ботом доступны команды `/start` (приветствие) и `/reset` (очистить mapping для текущего chat'а).

---

## Multi-project и подпроекты

Veles работает с несколькими проектами параллельно — каждый изолирован.

```sh
veles project list                       # все зарегистрированные проекты (slug + last_active)
veles project switch <slug>              # печатает абсолютный путь
cd $(veles project switch <slug>)        # переключиться cwd'ом
veles project add <path>                 # вручную зарегистрировать
veles project remove <slug>
```

Внутри одного `veles run` можно одноразово переключить активный проект через slash-prefix:

```sh
veles run "/project frontend сколько ошибок в last build?"
```

### Подпроекты

Внутри проекта можно делать вертикальную иерархию:

```sh
veles subproject init frontend           # <cwd>/frontend/.veles/
veles subproject list
veles subproject switch <slug>           # печатает абсолютный путь
veles subproject suggest                 # детектор кластеров в wiki (агент сам предлагает)
veles subproject suggest --save          # записать proposals в wiki/proposals/
```

`subproject suggest` ищет тематические кластеры (Jaccard над title-token'ами в `wiki/concepts` + `wiki/entities`) — когда видит 4+ страницы со схожими темами, предлагает выделить подпроект. Auto-trigger в `veles run` запускает детектор раз в 7 дней, proposals попадают в `wiki/proposals/` и подхватываются recall'ом.

---

## Перенос знаний между машинами

```sh
veles export full ./bundle.tar.gz        # bit-for-bit бэкап проекта
veles export template ./tmpl.tar.gz      # без sources/sessions/memory + PII-санитизация
veles import ./bundle.tar.gz --into ./new-cwd
```

**Full** — для миграции между своими машинами (включая memory.db, sessions, telemetry).
**Template** — для шаринга шаблона проекта (вычищены sources/sessions/memory/trust; emails/IPs/tokens заменены на placeholder'ы regex'ами; всё равно стоит вычитать вручную перед публикацией).

---

## Памятка по командам

| Команда                                  | Назначение                                                       |
|------------------------------------------|------------------------------------------------------------------|
| `veles init [name]`                      | Создать новый проект в cwd                                       |
| `veles run "<prompt>"`                   | Одиночный запрос                                                 |
| `veles tui`                              | Interactive REPL                                                 |
| `veles ingest <url\|file>`               | Записать wiki-страницу из источника                              |
| `veles query "<q>"`                      | Ответ через wiki + memory recall                                 |
| `veles lint`                             | Health-check wiki                                                |
| `veles curate`                           | Консолидация сессий → wiki                                       |
| `veles sessions {list,show,delete,search}` | Управление сессиями                                            |
| `veles wiki reindex`                     | Перестроить FTS5-индекс                                          |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | Управление скиллами                  |
| `veles module {list,add,remove}`         | Управление плагинами                                             |
| `veles route {show,set,reset,refresh}`   | Маршрутизация моделей                                            |
| `veles schema {validate,edit}`           | AGENTS.md schema check                                           |
| `veles project {list,add,remove,switch}` | Multi-project registry                                           |
| `veles subproject {init,list,switch,remove,suggest}` | Вертикальные подпроекты                              |
| `veles trust {list,set,revoke,clear}`    | Trust grant CRUD                                                 |
| `veles autopilot {enable,disable,status}`| Временный bypass trust ladder                                    |
| `veles export {full,template} <path>`    | Экспорт проекта                                                  |
| `veles import <path>`                    | Импорт проекта                                                   |
| `veles daemon {start,stop,status,token}` | HTTP+WS daemon                                                   |
| `veles channel run --channel telegram`   | Telegram-bot gateway                                             |

Для любой команды доступно `--help`:

```sh
veles run --help
veles skill add --help
```

---

## Конфигурация

- **Project-level state:** `<project>/.veles/`
  - `memory.db` — SQLite + FTS5 (сессии + turn-индекс).
  - `wiki/` — markdown-страницы (writable LLM-зона).
  - `routing.toml` — типизированная маршрутизация моделей.
  - `routing.nl.toml` — auto-generated из AGENTS.md natural-language hints.
  - `skills/`, `modules/` — project-local скиллы и плагины.
  - `trust.json` — project-scope grants.
  - `subprojects.json` — registry дочерних проектов.

- **User-global state:** `~/.veles/`
  - `config.toml` — wizard settings (язык, дефолтный провайдер).
  - `projects/registry.json` — multi-project registry.
  - `trust.json` — user-scope grants.
  - `autopilot.json` — autopilot window.
  - `skills/`, `modules/` — user-level (промоушенные) скиллы.
  - `daemon.tokens.json`, `daemon.pid`, `daemon.info.json` — daemon state.
  - `channels/*.json` — channel session mappings.

Override `~/.veles` через `VELES_USER_HOME=/path` (полезно в тестах / CI).

---

## Полезные env vars

| Env var                       | Эффект                                                          |
|-------------------------------|-----------------------------------------------------------------|
| `OPENROUTER_API_KEY` и др.    | API-ключи провайдеров                                           |
| `VELES_USER_HOME`             | Override `~/.veles` (CI, sandbox)                               |
| `VELES_TRUST_AUTO_ALLOW=1`    | Bypass trust ladder (CI, autopilot)                             |
| `VELES_NO_WIZARD=1`           | Skip first-run wizard                                           |
| `VELES_REGISTRY_PATH`         | Override path multi-project registry                            |
| `VELES_LIVE_TESTS=1`          | Включить live-API smoke tests                                   |

---

## Что дальше почитать

- **`AGENTS.md` проекта** — короткий схема-файл, который агент видит на каждой сессии. Подкрути под свой workflow.
- **`VISION.md`** — продуктовое видение Veles целиком (на русском).
- **`docs/adr/`** — архитектурные решения (ADR).

---

## Лицензия

Apache 2.0 (с patent grant). См. `LICENSE` и `NOTICE`.
