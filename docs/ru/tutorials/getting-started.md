# Первые шаги

> 🌐 **Языки:** [English](../../en/tutorials/getting-started.md) · **Русский**

В этом туториале вы установите Veles, зададите ему API-ключ, создадите первый проект
и выполните первый запрос. Примерно 10 минут. В итоге у вас будет рабочий проект
Veles, с которым можно общаться.

## Предварительные требования

- **Python 3.13+** (Veles требует `>=3.13`).
- LLM API-ключ. Мы будем использовать **OpenRouter** (провайдер по умолчанию); подойдёт
  и любой из [других провайдеров](../reference/providers.md), включая полностью
  локальные без ключа.

## 1. Установка

Veles устанавливается как глобальная команда `veles` через [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

Чтобы обновить позже: `uv tool install . --reinstall`.

## 2. Задайте Veles API-ключ

Получите ключ на [openrouter.ai](https://openrouter.ai) и экспортируйте его:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Можно также сохранить его в связке ключей ОС, чтобы не экспортировать заново в каждой
оболочке:

```bash
veles secret set OPENROUTER_API_KEY
```

(Предпочитаете полностью локальную конфигурацию без ключа? Установите [Ollama](https://ollama.com),
выполните `ollama pull qwen3:4b-instruct` и используйте `--provider ollama` ниже.)

## 3. Создайте первый проект

Проект Veles — это просто каталог с папкой состояния `.veles/`. Создайте его:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Эта команда создаёт `AGENTS.md` (контекст вашего проекта), `sources/` и `wiki/`
([стандартный layout LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)) и
`.veles/` (машинное состояние). См. [структуру проекта](../reference/project-layout.md).

## 4. Выполните первый запрос

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles загружает контекст вашего проекта, вызывает модель и выводит ответ. Этот ход
сохраняется в память проекта.

Добавьте `--stream`, чтобы видеть токены по мере поступления, или `--verbose` для
прогресса по каждому ходу:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Откройте интерактивный REPL

Для многоходового диалога откройте TUI:

```bash
veles tui
```

Введите сообщение и нажмите Enter. Полезные клавиши: `Ctrl+D` для выхода, `Shift+Tab`
для переключения [режимов запуска](../explanation/modes.md), `/help` для списка
slash-команд. Полный список — в [справочнике по TUI](../reference/tui.md).

## 6. Посмотрите, что Veles запомнил

Каждый запуск сохраняется. Просмотрите и найдите свои сессии:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Что дальше

- **[Построение базы знаний](building-a-knowledge-base.md)** — загрузите источники
  в wiki и задавайте вопросы по ним.
- **[Настройка провайдеров](../how-to/configure-providers.md)** — переключитесь на
  Anthropic, OpenAI, Gemini или полностью локальную модель.
- **[Обзор архитектуры](../explanation/architecture.md)** — поймите, что Veles
  делает под капотом.
