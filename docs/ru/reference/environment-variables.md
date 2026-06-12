# Переменные окружения

> 🌐 **Языки:** [English](../../en/reference/environment-variables.md) · **Русский**

Veles читает их во время выполнения. API-ключи и токены лучше хранить в OS-keychain
(`veles secret set …`); переменные окружения — это резервный вариант и переопределение.

## API-ключи провайдеров

Каскад поиска API-ключа: OS-keychain (проектная область) → OS-keychain (область по умолчанию)
→ переменная окружения.

| Переменная | Провайдер | Примечания |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Провайдер по умолчанию |
| `ANTHROPIC_API_KEY` | anthropic | Прямой Anthropic API |
| `OPENAI_API_KEY` | openai | Прямой OpenAI API |
| `GEMINI_API_KEY` | gemini | Основной ключ для Google Gemini |
| `GOOGLE_API_KEY` | gemini | Резервный для Google Gemini |

`claude-cli` и `gemini-cli` аутентифицируются через свои бинарники — без env-переменной.

## Локальные провайдеры

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Эндпоинт Ollama |
| `OLLAMA_HOST` | follows `OLLAMA_BASE_URL` | Хост Ollama для эмбеддингов |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Эндпоинт сервера llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (required) | Эндпоинт для провайдера `openai-compat` |
| `VELES_LOCAL_TOOLS` | off | Включить вызов инструментов на локальных провайдерах (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | provider default | Переопределить модель эмбеддингов Ollama |

## Каналы и демон

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Токен Telegram-бота для `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | Базовый URL демона, используемый шлюзами каналов |
| `VELES_DAEMON_TOKEN` | — | Bearer-токен для аутентификации демона |

## Пути и локаль

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `VELES_USER_HOME` | `~` | Переопределить домашний каталог, содержащий `~/.veles/` (состояние, кэш, индекс keychain) |
| `VELES_HOME` | — | Устаревший псевдоним для `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Переопределить путь реестра мультипроектности |
| `VELES_LOCALE` | `[user] language` or `en` | Переопределить активную локаль UI на один запуск |
| `VELES_LOG_LEVEL` | `INFO` | Подробность логов демона (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Переопределить имя файла конфигурации (тестирование) |

## Поведение и флаги функций

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `VELES_NO_WIZARD` | off | Пропустить мастер первоначальной настройки (также нужен TTY) |
| `VELES_MANAGER_MODE` | off | Принудительно включить мультиагентного менеджера для `veles run` (`1` вкл / `0` kill switch) |
| `VELES_FENCED_TOOLS` | off | Запускать инструменты по огороженному/песочничному пути выполнения |
| `VELES_TRUST_AUTO_ALLOW` | off | Обойти лестницу доверия (CI / автопилот / предавторизованные субагенты) |
| `VELES_SANDBOX_ROOTS` | project + `~/.veles` | Переопределение корней песочницы чтения/записи через `:` |
| `VELES_FETCH_ALLOW_PRIVATE` | off | Разрешить инструментам обращаться к адресам RFC-1918 / приватным |
| `VELES_MEMORY_RERANK` | on | Векторный реранжинг отзыва памяти (`0`/`false` отключает) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Бэкенд веб-поиска для `research` и `web_search` |

## Реестры

| Переменная | Назначение |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Источник для `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Источник для `veles browse modules` |

## Внутренние / тестирование

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — внутренние; устанавливать их вам
не должно понадобиться.
