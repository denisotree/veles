# Провайдеры

> 🌐 **Языки:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · **Русский** · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles не привязан к конкретному провайдеру. Передайте `--provider <id>` любой
команде агента или задайте провайдер по умолчанию в конфиге. ID моделей
используют собственные имена провайдера.

## Каталог провайдеров

Все провайдеры, которые знает Veles, — записи одного каталога из трёх источников:

1. **Встроенные** — таблица ниже, поставляется с Veles.
2. **Ваши** — `~/.veles/providers.toml`: размещённый OpenAI-совместимый API или ваш
   собственный сервер добавляется записью (см.
   [добавить свой провайдер](../how-to/configure-providers.md#добавить-свой-провайдер)).
   Запись со встроенным id меняет настройки этого провайдера (например, `base_url`).
3. **Модули** — модуль из реестра добавляет провайдер (`antigravity-cli`). Если назвать
   его в `[engine] provider`, маршруте или `--provider`, он установится из подключённых
   реестров при следующем запуске — как объявленный канал.

`--provider`, `veles models`, мастера настройки, маршрутизация и `veles doctor` читают
каталог, поэтому провайдер из любого источника работает везде, где и встроенный.
Неизвестный id — однострочная ошибка со списком доступных; `veles doctor` проверяет и
`~/.veles/providers.toml`, и каждый провайдер, названный в ваших маршрутах.

| Провайдер | Тип | API-ключ | Примечания |
|---|---|---|---|
| `openrouter` | Облачный шлюз | `OPENROUTER_API_KEY` | **По умолчанию.** Ретранслирует сотни моделей; ID моделей вида `anthropic/claude-sonnet-4.6` |
| `anthropic` | Облачный прямой | `ANTHROPIC_API_KEY` | API Claude Messages, prompt caching |
| `openai` | Облачный прямой | `OPENAI_API_KEY` | Chat completions GPT |
| `gemini` | Облачный прямой | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI-делегат | — (сессия CLI) | Делегирует локальному CLI `claude` в режиме JSON-stream |
| `ollama` | Локальный | нет | `OLLAMA_BASE_URL` (по умолчанию `http://localhost:11434/v1`) |
| `llamacpp` | Локальный | нет | `LLAMACPP_BASE_URL` (по умолчанию `http://localhost:8080/v1`) |
| `openai-compat` | Локальный/кастомный | необязательный `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL` (обязателен, без значения по умолчанию) |

`gemini-cli` удалён в 1.2.6 — Google больше не выдаёт Gemini CLI личным аккаунтам.
Используйте `gemini` с API-ключом или модуль `antigravity-cli`.

Провайдер по умолчанию: `openrouter`. **Жёстко зашитой модели по умолчанию нет** —
задайте её через мастер настройки, `[engine] model` или `--model` (иначе агент
сообщит «no model configured»). Маршруты по задачам наследуют `[engine]` как
базу, если не переопределены в `[routing.tasks]` — см.
[маршрутизацию по задачам](../how-to/per-task-routing.md).

## Локальные провайдеры

`ollama`, `llamacpp` и `openai-compat` не требуют API-ключа. Получите список
установленных моделей командой `veles models <provider>` (для локальных
провайдеров всегда актуальные данные).

**Вызов инструментов определяется** по тому, что сообщает бэкенд: ollama — возможности
каждой модели, сервер llama.cpp — шаблон чата. `VELES_LOCAL_TOOLS=1` принудительно
включает инструменты, `=0` выключает; без переменной — автоопределение.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Переопределите эндпоинты переменными окружения `*_BASE_URL` (см.
[переменные окружения](environment-variables.md)).

## Делегирование CLI (`claude-cli`, `antigravity-cli`)

Если у вас есть подписка Claude или Google, Veles может запускать её CLI в headless-режиме
и выступать координатором — без отдельного API-ключа. `claude-cli` встроен;
`antigravity-cli` (CLI `agy`) — модуль из реестра, который ставится сам, когда вы его
называете.

Делегат — только модель: инструменты Veles доходят до него по мосту MCP, и каждый
вызов проходит через лестницу доверия Veles. Конфиг моста лежит в каталоге запущенного
процесса, `.veles/tmp/delegate-<pid>/`, и удаляется при выходе. `agy` работает там в
отдельной рабочей папке, а не в вашем проекте, за шлюзом, который запрещает его
собственные инструменты оболочки и файлов.

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
