# Провайдеры

> 🌐 **Языки:** [English](../../en/reference/providers.md) · **Русский**

Veles не привязан к провайдеру. Передайте `--provider <name>` любой команде агента
или задайте значение по умолчанию в конфигурации. ID моделей используют собственное
именование провайдера.

| Провайдер | Тип | API-ключ | Примечания |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **По умолчанию.** Ретранслирует сотни моделей; ID моделей вида `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API, кэширование промптов |
| `openai` | Cloud direct | `OPENAI_API_KEY` | Chat completions GPT |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocess | — (CLI session) | Делегирует локальному `claude` CLI в режиме JSON-stream |
| `gemini-cli` | Subprocess | — (CLI session) | Делегирует локальному `gemini` CLI |
| `ollama` | Local | none | `OLLAMA_BASE_URL` (по умолчанию `http://localhost:11434/v1`) |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL` (по умолчанию `http://localhost:8080/v1`) |
| `openai-compat` | Local/custom | none | `OPENAI_COMPAT_BASE_URL` (обязателен, без значения по умолчанию) |

По умолчанию: провайдер `openrouter`, модель `anthropic/claude-sonnet-4.6`, компрессор
`anthropic/claude-haiku-4.5`.

## Локальные провайдеры

`ollama`, `llamacpp` и `openai-compat` не требуют API-ключа. Список установленных
моделей — `veles models <provider>` (всегда живой для локальных провайдеров).

**Вызов инструментов выключен по умолчанию** на локальных провайдерах — многие локальные
модели выдают некорректные вызовы инструментов. Включите его, как только выбрали
модель, способную к вызову инструментов:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Переопределяйте эндпоинты через env-переменные `*_BASE_URL` (см.
[переменные окружения](environment-variables.md)).

## Делегирование CLI (`claude-cli`, `gemini-cli`)

Если у вас есть подписка на Claude или Gemini CLI, Veles может запускать бинарник в
режиме JSON-стриминга и действовать как координатор — сохраняя цикл local-first без
отдельного API-ключа. Инструменты Veles достигают подпроцесса только при настроенном
MCP-мосте.

## Статус мультимодальности (vision / speech-to-text)

Veles определяет `VisionAdapter` и протокол STT-адаптера (`modules/vision.py`,
`modules/stt.py`) плюс глобальный реестр процесса, **но ни один конкретный адаптер не
поставляется и ничего не регистрируется при старте демона**. Поэтому фото или голосовое
сообщение, отправленное в канал, сейчас возвращает уведомление «не настроено», а не
анализируется. Задача маршрутизации `vision` существует на случай, когда адаптер будет
подключён. См. [подключение Telegram](../how-to/connect-telegram.md).

## Выбор модели

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Чтобы использовать разные модели для разных задач (дешёвую для компрессии, сильную для
планирования), см. [маршрутизацию по задачам](../how-to/per-task-routing.md).
