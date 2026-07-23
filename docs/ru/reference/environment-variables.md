# Переменные окружения

> 🌐 **Языки:** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · [繁體中文](../../zh-TW/reference/environment-variables.md) · [日本語](../../ja/reference/environment-variables.md) · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · **Русский** · [العربية](../../ar/reference/environment-variables.md) · [हिन्दी](../../hi/reference/environment-variables.md) · [বাংলা](../../bn/reference/environment-variables.md) · [Tiếng Việt](../../vi/reference/environment-variables.md)

Veles читает их во время работы. API-ключи и токены лучше хранить в keychain ОС
(`veles secret set …`); переменные окружения — это запасной вариант и средство
переопределения.

## API-ключи провайдеров

Каскад поиска API-ключа: keychain ОС (область проекта) → keychain ОС (область
default) → переменная окружения.

| Переменная | Провайдер | Примечания |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Провайдер по умолчанию |
| `ANTHROPIC_API_KEY` | anthropic | Прямой API Anthropic |
| `OPENAI_API_KEY` | openai | Прямой API OpenAI |
| `GEMINI_API_KEY` | gemini | Основной ключ для Google Gemini |
| `GOOGLE_API_KEY` | gemini | Запасной ключ для Google Gemini |

`claude-cli` и `gemini-cli` аутентифицируются через собственные бинарники — без
переменных окружения.

## Локальные провайдеры

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Эндпоинт Ollama |
| `OLLAMA_HOST` | следует за `OLLAMA_BASE_URL` | Хост Ollama для эмбеддингов |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Эндпоинт сервера llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (обязательна) | Эндпоинт для провайдера `openai-compat` |
| `VELES_LOCAL_TOOLS` | выкл | Включить вызов инструментов на локальных провайдерах (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | по умолчанию провайдера | Переопределить модель эмбеддингов Ollama |

## Каналы и демон

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Токен Telegram-бота для `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | Базовый URL демона, используемый шлюзами каналов |
| `VELES_DAEMON_TOKEN` | — | Bearer-токен для аутентификации демона |

## Пути и локаль

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `VELES_USER_HOME` | `~` | Переопределить домашний каталог, где лежит `~/.veles/` (состояние, кэш, индекс keychain) |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Переопределить путь мультипроектного реестра |
| `VELES_LOCALE` | `[user] language` или `en` | Переопределить активную локаль интерфейса на один запуск |
| `VELES_LOG_LEVEL` | `INFO` | Подробность логов демона (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |

## Флаги поведения и возможностей

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `VELES_NO_WIZARD` | выкл | Пропустить мастер первичной настройки (также нужен TTY) |
| `VELES_MANAGER_MODE` | выкл | Принудительно включить мультиагентного менеджера для `veles run` (`1` вкл / `0` kill switch) |
| `VELES_VERIFY_MODE` | выкл | Принудительно включить проход verify→escalate для `veles run` (`1` вкл / `0` kill switch) |
| `VELES_FENCED_TOOLS` | выкл | Запускать инструменты по огороженному/песочному пути выполнения |
| `VELES_TRUST_AUTO_ALLOW` | выкл | Обойти trust-лестницу (CI / автопилот / предавторизованные подагенты) |
| `VELES_SANDBOX_ROOTS` | проект + `~/.veles` | Переопределение корней песочницы чтения/записи через разделитель `:` |
| `VELES_FETCH_ALLOW_PRIVATE` | выкл | Разрешить инструментам обращаться к адресам RFC-1918 / приватным |
| `VELES_WEB_SEARCH_BACKEND` | auto | Бэкенд веб-поиска для `research` и `web_search` |

## Реестры

| Переменная | Назначение |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Источник для `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Источник для `veles browse modules` |

## Внутренние / тестовые

| Переменная | Назначение |
|---|---|
| `VELES_BUNDLE_VERSION` | Внутренняя; устанавливать её вам не нужно |
| `VELES_REPL_SIMPLE` | Установите в `1`, чтобы принудительно включить простой построчный цикл REPL вместо полноэкранного приложения `prompt_toolkit` (запасной вариант для ограниченных терминалов) |
