# Layout-пакеты и LLM-Wiki

> 🌐 **Языки:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · **Русский** · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

**Layout-пакет** (layout pack) определяет, как организован *пользовательский
контент* проекта — какие каталоги существуют, в какие из них агент может писать и
какие операции он предлагает. По умолчанию это **LLM-Wiki**. Это опция контента,
**а не** базовый принцип Veles.

## Что такое layout-пакет

Layout-пакет — это каталог с манифестом `layout.toml` (плюс опциональные файлы
навыков и шаблонов). Манифест объявляет:

- **Записываемые зоны** — каталоги, в которые агент может писать контент
  (проверяется при каждом `write_file`).
- **Зоны только для чтения** — материал, который агент читает, но никогда не изменяет.
- **Операции** — именованные рабочие процессы, поставляемые как навыки внутри пакета.
- **Скаффолд** (`[layout.scaffold]`) — что создаёт `veles init`: каталоги и
  опциональный шаблон `AGENTS.md` (подставляется `{name}`).
- **Движки** (`[layout.engines]`) — какую базовую контент-механику активирует
  пакет. Сегодня движок один: `wiki`. Без него в проекте нет wiki-инструментов,
  wiki-recall и инъекции INDEX.
- **Контекстный файл** (`context_file`) — файл, инжектируемый в стабильную часть
  системного промпта агента (LLM-Wiki использует `INDEX.md`).

## Встроенные пакеты

| Пакет | Что создаёт `veles init --layout <name>` |
|---|---|
| `llm-wiki` *(по умолчанию)* | [LLM-Wiki в стиле Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (только чтение), `wiki/` (агент пишет), `INDEX.md` инжектируется в промпт, навыки `ingest`/`query`/`lint`, движок wiki включён. |
| `notes` | Один плоский каталог `notes/`, в который пишет агент. Без wiki-механики. |
| `bare` | Вообще без контент-скаффолда — для кодовых репозиториев и свободной работы. Запись разрешена внутри корня проекта (по-прежнему через trust ladder). |

## Кастомные раскладки

Положите пакет в `~/.veles/layouts/<name>/layout.toml` (user-global) или
`<project>/.veles/layouts/<name>/` (проектный; перекрывает user- и builtin-пакеты
с тем же именем) и выполните `veles init --layout <name>`. Встроенный `notes` —
минимальный пример для копирования. Конвенции можно дополнительно описать в
`AGENTS.md` — раскладка обеспечивает зоны, AGENTS.md направляет поведение.

## Чем она *не* является

Раскладка управляет **только вашим контентом**. Собственная проектная память
Veles — `memory.db` плюс дерево артефактов `.veles/memory/` (инсайты, дайджесты
сессий, предложения, журнал системных операций) — системная и работает одинаково
под любой раскладкой. Переключение раскладок никогда не затрагивает цикл
обучения, сессии или реестры. См. [архитектуру](architecture.md) и
[структуру проекта](../reference/project-layout.md).
