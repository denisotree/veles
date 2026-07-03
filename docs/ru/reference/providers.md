# Провайдеры

> 🌐 **Языки:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · **Русский** · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles не привязан к конкретному провайдеру. Передайте `--provider <name>` любой
команде агента или задайте провайдер по умолчанию в конфиге. ID моделей
используют собственные имена провайдера.

| Провайдер | Тип | API-ключ | Примечания |
|---|---|---|---|
| `openrouter` | Облачный шлюз | `OPENROUTER_API_KEY` | **По умолчанию.** Ретранслирует сотни моделей; ID моделей вида `anthropic/claude-sonnet-4.6` |
| `anthropic` | Облачный прямой | `ANTHROPIC_API_KEY` | API Claude Messages, prompt caching |
| `openai` | Облачный прямой | `OPENAI_API_KEY` | Chat completions GPT |
| `gemini` | Облачный прямой | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Подпроцесс | — (сессия CLI) | Делегирует локальному CLI `claude` в режиме JSON-stream |
| `gemini-cli` | Подпроцесс | — (сессия CLI) | Делегирует локальному CLI `gemini` |
| `ollama` | Локальный | нет | `OLLAMA_BASE_URL` (по умолчанию `http://localhost:11434/v1`) |
| `llamacpp` | Локальный | нет | `LLAMACPP_BASE_URL` (по умолчанию `http://localhost:8080/v1`) |
| `openai-compat` | Локальный/кастомный | нет | `OPENAI_COMPAT_BASE_URL` (обязателен, без значения по умолчанию) |

Провайдер по умолчанию: `openrouter`. **Жёстко зашитой модели по умолчанию нет** —
задайте её через мастер настройки, `[engine] model` или `--model` (иначе агент
сообщит «no model configured»). Маршруты по задачам наследуют `[engine]` как
базу, если не переопределены в `[routing.tasks]` — см.
[маршрутизацию по задачам](../how-to/per-task-routing.md).

## Локальные провайдеры

`ollama`, `llamacpp` и `openai-compat` не требуют API-ключа. Получите список
установленных моделей командой `veles models <provider>` (для локальных
провайдеров всегда актуальные данные).

**Вызов инструментов по умолчанию выключен** на локальных провайдерах — многие
локальные модели формируют некорректные вызовы инструментов. Включите его, когда
выберете модель, поддерживающую инструменты:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Переопределите эндпоинты переменными окружения `*_BASE_URL` (см.
[переменные окружения](environment-variables.md)).

## Делегирование CLI (`claude-cli`, `gemini-cli`)

Если у вас есть подписка на CLI Claude или Gemini, Veles может запускать бинарник
в режиме JSON-стриминга и выступать координатором — удерживая цикл local-first без
отдельного API-ключа. Инструменты Veles доходят до подпроцесса только при
настроенном мосте MCP.

## Статус мультимодальности (зрение / распознавание речи)

Veles определяет `VisionAdapter` и протокол STT-адаптера (`modules/vision.py`,
`modules/stt.py`) плюс глобальный для процесса реестр, **но ни одного конкретного
адаптера не поставляется и ни один не регистрируется при старте демона**. Поэтому
фото или голосовое сообщение, отправленное в канал, сейчас возвращает уведомление
«not configured», а не анализируется. Задача маршрутизации `vision` существует на
случай, когда адаптер будет подключён. См.
[подключение Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Выбор модели

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Чтобы использовать разные модели для разных задач (дешёвую для компрессии, сильную
для планирования), см. [маршрутизацию по задачам](../how-to/per-task-routing.md).
