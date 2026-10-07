# Как настроить провайдеров

> 🌐 **Языки:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · **Русский** · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

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
[engine]
provider = "openrouter"                # provider name
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

Вызов инструментов **определяется** по тому, что сообщает сервер. Принудительно
включается `VELES_LOCAL_TOOLS=1` (выключается `=0`).

Переопределите эндпоинты, если ваш сервер не на порту по умолчанию:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Добавить свой провайдер

Любой размещённый OpenAI-совместимый API или ваш собственный сервер становится
провайдером через запись в `~/.veles/providers.toml` — без кода. Id — имя таблицы:

```toml
[providers.groq]
kind = "openai-api"                          # размещённый API; нужен ключ
label = "Groq"                               # как показывать в мастерах (необязательно)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # ваш сервер; ключ необязателен
base_url = "http://localhost:1234/v1"
```

Дальше он работает как встроенный:

```bash
veles secret set GROQ_API_KEY      # в keychain, туда, где его читает запись groq
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| Ключ | Значение |
|---|---|
| `kind` | `openai-api` (размещённый API) или `local` (ваш сервер) |
| `base_url` | OpenAI-совместимый эндпоинт, оканчивающийся на `/v1` (или аналог у провайдера) |
| `base_url_env` | переменная окружения, которая, если задана, переопределяет `base_url` |
| `key_env` | имена переменных окружения с ключом; сначала проверяется keychain |
| `label`, `tagline` | как мастера показывают провайдер |
| `tools` | `auto` (по умолчанию), `on` или `off` — получает ли модель вызовы инструментов |

Запись со встроенным id (`[providers.ollama]`) меняет настройки этого провайдера —
например, `base_url`, — но не его тип. О сломанном файле сообщается один раз, и Veles
продолжает со встроенными провайдерами; `veles doctor` показывает, что в нём не так.

Отправные точки для распространённых API — **не проверены командой Veles**, сверяйте
актуальный эндпоинт с документацией провайдера:

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## Делегирование подписке Claude / ChatGPT / Google

Если у вас аутентифицирован CLI `claude`, Veles может им управлять:

```bash
veles run --provider claude-cli "..."
```

Для подписки ChatGPT установите Codex CLI и один раз войдите (`codex login`):

```bash
veles run --provider codex --model gpt-6-luna "..."
veles models codex      # модели, доступные вашему аккаунту
```

Для подписки Google один раз установите Antigravity CLI (`agy`) и войдите в него, затем
назовите провайдер — модуль `antigravity-cli` установится из подключённых реестров при
этом же запуске:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
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
