# Многоагентная оркестрация

> 🌐 **Языки:** [English](../../en/explanation/multi-agent-orchestration.md) · [简体中文](../../zh-CN/explanation/multi-agent-orchestration.md) · [繁體中文](../../zh-TW/explanation/multi-agent-orchestration.md) · [日本語](../../ja/explanation/multi-agent-orchestration.md) · [한국어](../../ko/explanation/multi-agent-orchestration.md) · [Español](../../es/explanation/multi-agent-orchestration.md) · [Français](../../fr/explanation/multi-agent-orchestration.md) · [Italiano](../../it/explanation/multi-agent-orchestration.md) · [Português (BR)](../../pt-BR/explanation/multi-agent-orchestration.md) · [Português (PT)](../../pt-PT/explanation/multi-agent-orchestration.md) · **Русский** · [العربية](../../ar/explanation/multi-agent-orchestration.md) · [हिन्दी](../../hi/explanation/multi-agent-orchestration.md) · [বাংলা](../../bn/explanation/multi-agent-orchestration.md) · [Tiếng Việt](../../vi/explanation/multi-agent-orchestration.md)

Для сложной работы Veles может разбить задачу между **менеджером** и
специализированными субагентами-**воркерами**, вместо того чтобы делать всё в одном
контексте. Эта страница объясняет модель; чтобы включить её, см.
[режим менеджера](../how-to/long-running-tasks.md).

## Форма

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- **Менеджер** планирует декомпозицию и координирует — но он **не** пишет финальный
  результат сам.
- **Воркеры** имеют системные промпты под конкретную роль: `explorer` собирает,
  `writer` производит ответ, `advisor` рецензирует. Набор расширяем.
- В конце менеджер пишет короткий отчёт в память.

## Никакого испорченного телефона

Ключевое правило: промежуточные артефакты доходят до синтезатора **дословно**, а не
в пересказе менеджера. Находки explorer передаются writer напрямую, так что детали
не теряются через цепочку сводок. Именно это заставляет декомпозицию добавлять
качество, а не размывать его.

## Почему «менеджер никогда не пишет»

Если бы координатор ещё и писал ответ, у него был бы соблазн срезать путь мимо
воркеров и потерять выгоду от специализации. Удержание синтеза в выделенном
`writer` (которому подаются дословные входные данные) обеспечивает разделение
труда. Veles делает это рантайм-гарантией.

## Когда это помогает — а когда нет

Декомпозиция окупается на широких или многогранных задачах (провести аудит этой
кодовой базы, исследовать этот вопрос с нескольких сторон). Для быстрого запроса в
одном контексте она лишь добавляет накладные расходы — поэтому режим менеджера
**включается явно** и по умолчанию выключен (`veles run --manager` или
`VELES_MANAGER_MODE=1`).
