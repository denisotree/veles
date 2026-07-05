# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <b>Русский</b> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**Минималистичный фреймворк CLI-агента, который умнеет с каждой сессией.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles TUI — задайте вопрос и получите ответ, опирающийся на собственную память проекта" width="800">
</p>

В отличие от чат-инструментов, которые каждый раз начинают с чистого листа, Veles ведёт **структурированную проектную память** — инсайты, правила и выверенные знания, которые накапливаются между сессиями и делают агента тем полезнее, чем дольше вы им пользуетесь. То, как организован ваш *контент*, можно подключать как плагин: по умолчанию — LLM-вики в стиле Карпати, плоские заметки или вовсе без структуры для репозиториев с кодом. Сделано чисто: без god-файлов, без вендорлока, без облачной синхронизации.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # интерактивный REPL (TUI; просто `veles` без подкоманды)
```

---

## Почему Veles?

**Накопительная память** — каждая сессия дистиллируется Куратором в проектную память (инсайты, поведенческие правила, дайджесты сессий в `.veles/`). Агент автоматически вспоминает релевантные факты и прошлые решения — вам больше не нужно заново объяснять один и тот же контекст. Память работает при *любой* раскладке контента.

**Подключаемые раскладки контента** — `veles init` по умолчанию разворачивает LLM-вики в стиле Карпати; `--layout notes` даёт плоский каталог заметок; `--layout bare` не добавляет вообще никакой структуры (идеально для репозиториев с кодом). Свои пакеты раскладок — это один TOML-файл в `~/.veles/layouts/`.

**Маршрутизация, независимая от провайдера** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp или ваша подписка на CLI `claude`/`gemini`. Разные типы задач (планирование, сжатие, инсайты) можно направлять на разные модели.

**Накапливающиеся навыки** — переиспользуемые промпт-блоки становятся инструментами агента. Повысьте навык с уровня проекта до глобального пользовательского — и он доступен везде. Встроенный дедуп находит почти одинаковые навыки до того, как они разойдутся.

**Local-first + песочница** — никакой телеметрии, никакой облачной синхронизации. Агент видит только каталог активного проекта. Лестница доверия запрашивает подтверждение на каждый чувствительный вызов инструмента; для CI можно выдать права заранее.

**Модульность, а не монолит** — минимальное ядро (память, цикл агента, протокол провайдера, реестр инструментов). Всё остальное — TUI, демон, шлюз Telegram, глубокое исследование, планировщик задач — это опциональный загружаемый модуль.

---

## Быстрый старт

**Требования:** Python 3.13+, macOS / Linux (Windows — по мере возможностей). Сначала установите [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

Или откройте интерактивный TUI (голый `veles` делает то же самое):

```bash
veles
```

При первом запуске мастер настройки спросит предпочитаемый язык, провайдера и название проекта.

---

## Провайдеры

| Провайдер | Переменная окружения | Примечания |
|---|---|---|
| **OpenRouter** *(рекомендуется)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — один ключ, сотни моделей |
| Anthropic | `ANTHROPIC_API_KEY` | Прямой API |
| OpenAI | `OPENAI_API_KEY` | Прямой API |
| Gemini | `GEMINI_API_KEY` или `GOOGLE_API_KEY` | Прямой API |
| `claude` CLI | — | Использует вашу подписку Claude; ключ API не нужен |
| `gemini` CLI | — | Использует вашу подписку Gemini; ключ API не нужен |
| Ollama | — | Локальные модели, `http://localhost:11434/v1` |
| llamacpp | — | Локальные модели, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | Любой OpenAI-совместимый эндпоинт |

Переопределение для конкретного запуска:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

Хранить ключи API в системном хранилище ключей вместо переменных окружения:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## Основной рабочий процесс

### Выберите раскладку контента

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

Собственная память агента (инсайты, правила, дайджесты сессий в `.veles/`) работает одинаково при любой раскладке. Свои пакеты — это один `layout.toml` в `~/.veles/layouts/<name>/`.

### Соберите базу знаний (раскладка llm-wiki)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="База знаний Veles — добавьте источник в вики-страницу, затем задайте вопрос и получите ответ со ссылкой на неё" width="800">
</p>

Куратор запускается автоматически после сессий. Извлечение инсайтов улавливает фразы вроде «always prefer X» или «never do Y» и записывает их как постоянные проектные инсайты.

### Глубокое исследование

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

Раскладывает вопрос на параллельные подвопросы, исследует каждый и синтезирует структурированный отчёт.

### Долгоживущие цели

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### Задачи по расписанию

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## Маршрутизация моделей (ансамбли)

Направляйте разные типы задач на разные модели — настройте один раз и забудьте.

**Через CLI:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**Через естественный язык в `AGENTS.md`:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## Навыки и модули

**Навыки** — это переиспользуемые промпт-блоки (`SKILL.md`), которые автоматически становятся инструментами агента.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**Модули** — это Python-плагины, которые могут подключаться к жизненному циклу агента (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) и накладывать вето на вызовы инструментов.

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## TUI

```bash
veles                        # новая сессия (bare `veles` запускает TUI)
veles -c                     # продолжить последнюю сессию проекта
veles --resume <id>          # возобновить конкретную сессию
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="Veles TUI — слэш-инспекторы (/status, /context), переключение режимов и палитра команд" width="800">
</p>

Слэш-команды показывают всё вживую — `/status`, `/tokens`, `/context`, `/mode`, `/help` — а `Shift+Tab` циклически переключает режимы (auto / planning / writing / goal).

| Клавиша | Действие |
|---|---|
| `Enter` | Отправить сообщение |
| `Shift+Enter` | Перенос строки в редакторе |
| `Ctrl+I` | Переключить инспектор активности инструментов |
| `Ctrl+R` | Оверлей выбора сессии |
| `Ctrl+G` | Открыть `$EDITOR` для текущего черновика |
| `Tab` | Автодополнение слэш-команд |
| `Ctrl+D` | Выход |

Слэш-команды: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` и другие.

---

## Демон + Telegram

Запускайте Veles как постоянный демон с HTTP/WebSocket API. В свежем каталоге проекта `veles daemon start` проведёт вас через настройку — инициализирует проект, включит демон и **подключит канал**: сначала выберите *тип* канала (Telegram — единственная платформа на сегодня, но этот выбор и есть тот шов, через который регистрируются новые каналы), затем заполните поля этого канала (токен бота, белый список). Открывать TUI заранее не нужно.

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — мастер, который поднимает демон и подключает канал Telegram (сначала тип канала, затем его токен и белый список)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

Голый `veles daemon` открывает живую панель управления — дерево проект → демоны → каналы. Запускайте, останавливайте, перезапускайте или удаляйте демоны и добавляйте/удаляйте каналы (тот же поток «сначала тип канала», клавиша `c`) по всем проектам — целиком с клавиатуры:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — TUI панели управления: дерево проект → демоны → каналы с запуском/остановкой/перезапуском/удалением и встроенным управлением каналами" width="800">
</p>

Тот же мастер каналов доступен и отдельно (`veles channel add`) на уже работающем проекте.

Эндпоинты API: `POST /v1/runs` для отправки промпта, `WS /v1/runs/{id}/events` для стриминга ответа, `GET /v1/sessions` для списка сессий. Все, кроме `GET /v1/health`, требуют `Authorization: Bearer <token>` (выпустите токен через `veles daemon token add <name>`).

Каждый пользователь Telegram получает постоянную сессию. Используйте `veles channel list-sessions` / `reset-session` для управления привязками.

---

## Мультипроект

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## Доверие и безопасность

Каждый чувствительный вызов инструмента (выполнение shell, запись файлов, загрузка URL) запрашивает подтверждение:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

Выдача прав заранее для CI или длительных автономных запусков:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

Агент видит только каталог активного проекта — другие проекты, выходы через симлинки и обход через `..` заблокированы.

---

## Экспорт / импорт

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## Справочник по CLI

| Команда | Назначение |
|---|---|
| `veles init [name]` | Создать новый проект |
| `veles run "<prompt>"` | Однократный запуск агента |
| `veles` | Интерактивный TUI REPL (без подкоманды) |
| `veles add <file\|url>` | Добавить источник → вики-страница |
| `veles research "<question>"` | Глубокое многостороннее исследование |
| `veles curate` | Консолидировать сессии в вики |
| `veles sessions {list,show,delete,search}` | Управление сессиями |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | Управление навыками |
| `veles tool {list,show,promote}` | Управление инструментами |
| `veles module {list,add,remove}` | Управление плагинами |
| `veles route {show,set,reset,refresh}` | Маршрутизация моделей |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Долгосрочные цели |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Задачи по расписанию |
| `veles dream` | Фоновый цикл консолидации памяти |
| `veles project {list,add,remove,switch}` | Реестр мультипроектов |
| `veles subproject {init,list,switch,remove,suggest}` | Дочерние проекты |
| `veles trust {list,set,revoke,clear}` | Выданные права доверия |
| `veles autopilot {enable,disable,status}` | Временный обход доверия |
| `veles secret {set,get,list,delete}` | Секреты в системном хранилище ключей |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | HTTP/WS демон |
| `veles channel {run,list-sessions,reset-session}` | Шлюз внешних каналов |
| `veles mcp {list,test}` | Внешние MCP-серверы |
| `veles models <provider>` | Список моделей провайдера |
| `veles doctor` | Проверки работоспособности |
| `veles export / import` | Резервное копирование и перенос проекта |

У каждой команды есть `--help`.

---

## Документация

Полная документация — организована по Diátaxis (учебники · практические руководства · справочник · пояснения):

- **Русский:** [`docs/ru/index.md`](docs/ru/index.md)

Другие языки: переключатель 🌐 вверху любой страницы документации.

---

## Участие в разработке

Вклад очень приветствуется — Veles **создан для расширения**. Ядро остаётся небольшим (цикл агента + проектная память + протокол провайдера); почти всё остальное — это подключаемая точка расширения, поэтому добавление возможности редко требует трогать ядро:

- **Адаптеры провайдеров** (`src/veles/adapters/`) — подключите новый бэкенд модели.
- **Навыки** — переиспользуемые промпт-блоки и инструменты с наследованием через `extends:`, повышаемые с уровня проекта до глобального пользовательского.
- **Инструменты** — типизированный Python, который агент пишет и переиспользует, в `<project>/.veles/tools/`.
- **Пакеты раскладок** — один `layout.toml` в `~/.veles/layouts/<name>/` задаёт целую раскладку контента.
- **Хуки модулей** — наблюдаемость, логирование и политики через хуки `pre_turn` / `post_turn` (`src/veles/core/modules.py`).
- **Каналы и MCP-серверы** — новые шлюзы и внешние источники инструментов.
- **Локали** — переводы в `src/veles/locales/`.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

Кодовая база намеренно декомпозирована — единая ответственность, никаких god-файлов. Перед открытием PR прочитайте [`CONTRIBUTING.md`](CONTRIBUTING.md) для соглашений и [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Хорошие первые вклады: адаптеры провайдеров, навыки рабочих процессов, хуки модулей и файлы локалей.

---

## Лицензия

Apache 2.0 с патентным грантом — см. [`LICENSE`](LICENSE) и [`NOTICE`](NOTICE).
