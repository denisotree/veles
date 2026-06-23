# Первые шаги

> 🌐 **Languages:** **English** · [Русский](../../ru/tutorials/getting-started.md)

В этом руководстве вы установите Veles, дадите ему API-ключ, создадите первый
проект и запустите первый промпт. Около 10 минут. В итоге у вас будет рабочий
проект Veles, с которым можно общаться.

## Требования

- **Python 3.13+** (Veles требует `>=3.13`).
- API-ключ для LLM. Мы используем **OpenRouter** (провайдер по умолчанию);
  подойдёт и любой из [других провайдеров](../reference/providers.md), включая
  полностью локальные, не требующие ключа.

## 1. Установка

Veles устанавливается как глобальная команда `veles` через [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

Чтобы обновиться позже: `uv tool upgrade veles-ai`.

## 2. Дайте Veles API-ключ

Получите ключ на [openrouter.ai](https://openrouter.ai) и экспортируйте его:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Можно также сохранить его в keychain ОС, чтобы не экспортировать заново в каждой
сессии shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(Предпочитаете полностью локальную настройку без ключа? Установите
[Ollama](https://ollama.com), выполните `ollama pull qwen3:4b-instruct` и
используйте `--provider ollama` ниже.)

## 3. Создайте первый проект

Проект Veles — это просто каталог со служебной папкой `.veles/`. Создайте его:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Это создаёт `AGENTS.md` (контекст вашего проекта), `sources/` и `wiki/`
(раскладка [LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) по умолчанию) и
`.veles/` (машинное состояние). См. [раскладку проекта](../reference/project-layout.md).

## 4. Запустите первый промпт

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles загружает контекст вашего проекта, вызывает модель и печатает ответ. Ход
сохраняется в память проекта.

Добавьте `--stream`, чтобы видеть токены по мере их поступления, или `--verbose`
для прогресса по каждому ходу:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Откройте интерактивный REPL

Для многоходового разговора откройте TUI:

```bash
veles tui
```

Введите сообщение и нажмите Enter. Полезные клавиши: `Ctrl+D` для выхода,
`Shift+Tab` для переключения [режимов запуска](../explanation/modes.md), `/help`
для списка слэш-команд. Полный список в [справочнике TUI](../reference/tui.md).

## 6. Посмотрите, что Veles запомнил

Каждый запуск сохраняется. Просматривайте и ищите свои сессии:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Куда дальше

- **[Создание базы знаний](building-a-knowledge-base.md)** — загружайте источники
  в wiki и задавайте вопросы по ним.
- **[Настройка провайдеров](../how-to/configure-providers.md)** — переключитесь на
  Anthropic, OpenAI, Gemini или полностью локальную модель.
- **[Обзор архитектуры](../explanation/architecture.md)** — поймите, что Veles
  делает под капотом.
