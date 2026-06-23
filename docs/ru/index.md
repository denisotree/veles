# Документация Veles

> 🌐 **Языки:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · **Русский** · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles — это минималистичный, local-first фреймворк CLI-агента. Вы указываете ему
на каталог проекта; он ведёт структурированную **проектную память**, **учится** на
ваших сессиях, работает с любым LLM-провайдером (облачным или локальным) и по ходу
работы накапливает переиспользуемые **навыки** (skills) и **инструменты** (tools).

Эта документация следует модели [Diátaxis](https://diataxis.fr/). Выберите
квадрант, соответствующий тому, что вам сейчас нужно.

## Начните отсюда

Если вы никогда не запускали Veles, пройдите два туториала по порядку:

1. **[Первые шаги](tutorials/getting-started.md)** — установите Veles, задайте API-ключ,
   создайте первый проект и выполните первый запрос.
2. **[Построение базы знаний](tutorials/building-a-knowledge-base.md)** — загрузите
   источники в LLM-Wiki, задавайте вопросы и консолидируйте сессии.

## Туториалы — учитесь на практике

- [Первые шаги](tutorials/getting-started.md)
- [Построение базы знаний](tutorials/building-a-knowledge-base.md)

## Инструкции — выполните задачу

- [Настройка провайдеров (облачных и локальных)](how-to/configure-providers.md)
- [Маршрутизация разных задач на разные модели](how-to/per-task-routing.md)
- [Запуск Veles в режиме демона](how-to/run-as-daemon.md)
- [Подключение Telegram-канала](how-to/connect-telegram.md)
- [Управление навыками, инструментами и модулями](how-to/manage-skills-and-tools.md)
- [Работа с несколькими проектами и подпроектами](how-to/multi-project-and-subprojects.md)
- [Безопасность: доверие, autopilot, секреты](how-to/security-and-permissions.md)
- [Длительные задачи: цели, задания, dreaming, исследования](how-to/long-running-tasks.md)
- [Подключение внешних MCP-серверов](how-to/external-mcp-servers.md)
- [Резервное копирование и обмен проектом](how-to/backup-and-share.md)

## Справочник — найдите нужное

- [Справочник по командам CLI](reference/cli.md)
- [Конфигурация (`config.toml`)](reference/configuration.md)
- [Переменные окружения](reference/environment-variables.md)
- [Провайдеры](reference/providers.md)
- [Горячие клавиши и slash-команды TUI](reference/tui.md)
- [Структура и состояние проекта](reference/project-layout.md)

## Концепции — поймите устройство

- [Обзор архитектуры](explanation/architecture.md)
- [Проектная память и цикл обучения](explanation/project-memory-and-learning-loop.md)
- [Навыки и инструменты как накапливаемая способность](explanation/skills-and-tools.md)
- [Режимы запуска](explanation/modes.md)
- [Многоагентная оркестрация](explanation/multi-agent-orchestration.md)
- [Layout-паки и LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Доверие и песочница](explanation/trust-and-sandbox.md)

---

Продуктовое видение и обоснование дизайна см. в `VISION.md` (в корне репозитория);
полную историю реализации — в `MILESTONES.md`. Они ориентированы на разработчиков —
а эта документация о том, как **пользоваться** Veles.
