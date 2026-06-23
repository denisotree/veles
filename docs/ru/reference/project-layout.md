# Структура проекта и состояние

> 🌐 **Языки:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · **Русский** · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

Что создаёт `veles init`, где Veles хранит состояние и схема памяти проекта.

## Что создаёт `veles init`

Контентная половина зависит от выбранного layout-пакета (`--layout`,
по умолчанию `llm-wiki`); половина состояния в `.veles/` везде одинакова.

```
my-project/                  # veles init  (раскладка llm-wiki по умолчанию)
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # raw, immutable source material (agent-readonly)
├── wiki/                    # the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/ sources/
└── .veles/                  # project state (do not commit; machine-managed)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessions, turns, insights, rules, telemetry
    ├── memory/              # собственные артефакты памяти агента:
    │   ├── LOG.md           #   append-only журнал системных операций
    │   ├── insights/        #   отрендеренные представления строк `insights`
    │   ├── sessions/        #   сводки компакций
    │   └── proposals/       #   предложения подпроектов / promote-навыков
    ├── jobs/                # вывод запланированных задач
    └── skills/              # проектные навыки
```

С `--layout notes` контентная половина — один каталог `notes/`; с
`--layout bare` контент-скаффолда нет вовсе. `wiki/INDEX.md` (каталог по
требованию) генерируется по мере роста вики; `config.toml`, `tools/` и `plans/`
появляются под `.veles/`, как только вы что-то настроите, агент напишет
инструмент или вы запустите цель.

## Каталоги состояния

| Путь | Область | В коммите? |
|---|---|---|
| `<project>/AGENTS.md` + контент раскладки (`wiki/`, `sources/`, `notes/`, …) | Контент проекта | **Да** — это ваша база знаний |
| `<project>/.veles/` | Машинное состояние проекта (память, конфигурация, локальные skills/tools) | Нет |
| `~/.veles/` | User-global: `config.toml`, гранты доверия, межпроектные skills/tools, layout-пакеты, кэш моделей, локали | Нет |

`VELES_USER_HOME` переопределяет `~` для пользовательского глобального дерева (тесты, песочницы).

## Память проекта (`.veles/memory.db` + `.veles/memory/`)

Память проекта Veles — это **структурированный артефакт**, отдельный от вашего
контента и независимый от раскладки. База SQLite (режим WAL) — источник истины;
`.veles/memory/` хранит человекочитаемую сторону (представления инсайтов,
дайджесты сессий, предложения, журнал системных операций). Ключевые таблицы:

| Таблица | Содержит |
|---|---|
| `sessions`, `turns` | История разговоров (одна строка на ход) |
| `turns_fts` | Полнотекстовый индекс по ходам (питает `veles sessions search`) |
| `insights`, `insights_fts`, `insight_refs` | Выученные инсайты (канонические строки; markdown-представления регенерируемы) + связи дедупликации |
| `rules`, `rules_fts` | Правила формата/do/don't/предпочтений, инжектируемые в стабильный промпт |
| `skills`, `skill_uses`, `skill_tool_refs` | Реестр skills + телеметрия + связи с инструментами |
| `tools`, `tool_uses` | Реестр tools + телеметрия (счётчики использований/успехов/ошибок) |
| `project_tree` | Кэшированная карта файлов проекта + семантические теги для ранжирования релевантности |

См. [Память проекта и цикл обучения](../explanation/project-memory-and-learning-loop.md)
о том, как они записываются и отзываются.

## Layout-пакеты

`veles init --layout {llm-wiki|notes|bare|<custom>}` выбирает раскладку
контента; пакет владеет скаффолдом, шаблоном AGENTS.md, записываемыми зонами и
тем, активен ли wiki-движок (wiki-инструменты, инъекция INDEX в промпт,
wiki-recall). См.
[layout-пакеты и LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
