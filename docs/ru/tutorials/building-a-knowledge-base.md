# Построение базы знаний

> 🌐 **Языки:** [English](../../en/tutorials/building-a-knowledge-base.md) · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · [日本語](../../ja/tutorials/building-a-knowledge-base.md) · [한국어](../../ko/tutorials/building-a-knowledge-base.md) · [Español](../../es/tutorials/building-a-knowledge-base.md) · [Français](../../fr/tutorials/building-a-knowledge-base.md) · [Italiano](../../it/tutorials/building-a-knowledge-base.md) · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · [Português (PT)](../../pt-PT/tutorials/building-a-knowledge-base.md) · **Русский** · [العربية](../../ar/tutorials/building-a-knowledge-base.md) · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · [বাংলা](../../bn/tutorials/building-a-knowledge-base.md) · [Tiếng Việt](../../vi/tutorials/building-a-knowledge-base.md)

В этом туториале вы превращаете проект Veles в живую базу знаний: загружаете несколько
источников, даёте Veles написать wiki-страницы, задаёте вопросы и консолидируете
изученное. Это стандартный рабочий процесс **LLM-Wiki**. Примерно 15 минут.

Сначала вам следует пройти [Первые шаги](getting-started.md).

## Идея

В проекте Veles есть две контентные зоны:

- `sources/` — сырой, неизменяемый материал, который вы ему даёте (доступен агенту
  только для чтения).
- `wiki/` — собственные, сгенерированные LLM знания агента (единственная зона, в
  которую он записывает контент).

Вы подаёте источники; Veles перегоняет их в связанные wiki-страницы; вы запрашиваете
wiki на естественном языке. Зачем это нужно — см.
[layout-пакеты и LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

## 1. Загрузите источник

`veles add` читает файл или URL и записывает wiki-страницу с его кратким изложением:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

Каждый вызов `add` создаёт страницу в `wiki/` и связывает её с графом wiki.

## 2. Наблюдайте, как растёт wiki

Посмотрите, что было записано:

```bash
ls wiki/concepts wiki/entities wiki/sources
```

Страницы перекрёстно ссылаются друг на друга. Подгружаемый по требованию каталог
`wiki/INDEX.md` хранит карту, которую агент загружает, когда она ему нужна (а не
монолитный дамп контекста).

## 3. Задавайте вопросы

Теперь запрашивайте свою базу знаний на естественном языке:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles ищет по wiki, читает релевантные страницы и отвечает — опираясь на то, что вы
загрузили, а не только на свои обучающие данные.

Для интерактивного диалога сделайте то же самое в TUI (`veles tui`).

## 4. Консолидируйте сессии

По мере работы накапливаются диалоги. Запустите куратора, чтобы уплотнить их в
устойчивые wiki-страницы и извлечь уроки:

```bash
veles curate
```

Это записывает страницы в `wiki/sessions/` и обновляет инсайты и правила проекта.
Veles также делает это автоматически со временем — см.
[проектную память и цикл обучения](../explanation/project-memory-and-learning-loop.md).

## 5. Поддерживайте wiki в порядке

Со временем страницы устаревают или становятся сиротами. Операция `lint` находит их:

```bash
veles run "lint"
```

(`ingest`, `query` и `lint` — это навыки, поставляемые с layout LLM-Wiki; вы вызываете
их через `veles run "<operation>"` или позволяете агенту вызвать их самому.)

## Что вы построили

Самоорганизующуюся базу знаний: на входе — источники, на выходе — связанные
wiki-страницы, запрашиваемые на естественном языке, которая становится аккуратнее по
мере того, как Veles её консолидирует. Отсюда:

- **[Управление навыками, инструментами и модулями](../how-to/manage-skills-and-tools.md)** —
  обучите Veles переиспользуемым рабочим процессам.
- **[Запуск в режиме демона](../how-to/run-as-daemon.md)** + **[подключение Telegram](../how-to/connect-telegram.md)** —
  общайтесь со своей базой знаний с телефона.
- **[Несколько проектов и подпроектов](../how-to/multi-project-and-subprojects.md)** —
  масштабируйтесь на множество баз знаний.
