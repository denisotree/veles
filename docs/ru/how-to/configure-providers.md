# Как настроить провайдеров

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/configure-providers.md)

Переключайте Veles между OpenRouter, Anthropic, OpenAI, Gemini, локальными
моделями или подпиской на CLI. Полный список провайдеров:
[справочник провайдеров](../reference/providers.md).

## Выбор провайдера на одну команду

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Задать значение по умолчанию для проекта

Укажите базу в `<project>/.veles/config.toml`:

```toml
[provider]
default = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

Или user-global значение по умолчанию в `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Указать API-ключ

Облачным провайдерам нужен ключ. Сохраните его один раз в keychain ОС:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…или экспортируйте [переменную окружения](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Порядок поиска: keychain (область проекта) → keychain (default) → переменная
окружения. Ключи **никогда** не записываются в файлы конфигурации.

## Использование полностью локальной модели (без ключа)

Установите [Ollama](https://ollama.com), скачайте модель и укажите её Veles:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

Вызов инструментов **по умолчанию выключен** на локальных провайдерах. Включите
его, когда выберете модель, поддерживающую инструменты:

```bash
export VELES_LOCAL_TOOLS=1
```

Переопределите эндпоинты, если ваш сервер не на порту по умолчанию:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Делегирование подписке на CLI Claude / Gemini

Если у вас аутентифицирован CLI `claude` или `gemini`, Veles может им управлять:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

API-ключ не нужен — аутентификацию выполняет сам CLI.

## Список доступных моделей

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## Дальше

- [Направляйте разные задачи на разные модели](per-task-routing.md) — дешёвая
  модель для компрессии, сильная для планирования.
