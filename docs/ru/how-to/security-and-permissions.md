# Как управлять безопасностью: доверие, autopilot, секреты

> 🌐 **Языки:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · **Русский** · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

Veles ограничивает опасные действия через **лестницу доверия**, изолирует доступ к
файлам в песочнице и хранит секреты в keychain ОС. Обоснование см. в
[доверие и песочница](../explanation/trust-and-sandbox.md).

## Лестница доверия

Чувствительные инструменты (`run_shell`, `write_file`, `fetch_url`, …) спрашивают
перед запуском. Вы выбираете: разрешить **один раз**, **всегда для этого проекта**,
**всегда везде** или **отказать**. Выданные разрешения сохраняются, поэтому вас не
спросят снова.

Управлять разрешениями, не дожидаясь запроса:

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

Некоторые действия **подтверждаются всегда**, даже при наличии разрешения, —
удаление файлов, загрузка URL, установка нового навыка/инструмента/модуля,
подключение канала и запись за пределами проекта.

## Autopilot — обход доверия с ограничением по времени

Для запуска без присмотра (ночной пакетный прогон) откройте окно, в котором
запросы доверия разрешаются автоматически:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Каждое действие в режиме autopilot логируется для последующего разбора.
Неинтерактивные контексты (daemon, batch) по умолчанию отказывают, если autopilot
не активен.

## Секреты

API-ключи и токены ботов хранятся в keychain ОС, никогда в конфигурационных файлах:

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # a key for one project only
```

Поиск откатывается к соответствующей [переменной окружения](../reference/environment-variables.md),
если вы не передали `--no-env-fallback`.

## Песочница

Инструменты могут читать внутри активного проекта, `~/.veles/skills/` и
`~/.veles/locales/`, а писать только внутри
проекта — или только в зоны записи раскладки, если раскладка их объявляет.
Переопределить корни для продвинутых конфигураций можно через `VELES_SANDBOX_ROOTS`
(разделитель `:`). Загрузка URL соблюдает SSRF-чёрный список;
`VELES_FETCH_ALLOW_PRIVATE=1` снимает блокировку приватной сети.

Внутри `.veles/` проекта файловые инструменты агента пишут только в `skills/`,
`tools/`, `tmp/`, `plans/`, `memory/` и `artifacts/`. Всё остальное там —
`trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`, `memory.db` —
меняется только командами `veles` и собственными инструментами Veles. Файловые
инструменты также отклоняют запись в любой другой каталог `.veles/` в проекте
(подпроекта или подброшенный агентом в `wiki/`) и в конфиги делегируемых CLI —
`.claude/`, `.gemini/` и `.mcp.json` — на любой глубине. Так что через файловые
инструменты агент не может выдать себе доверие или добавить код, который запустит Veles
или делегируемый CLI (инструмент, который он пишет в `.veles/tools/`, загружается только
после того, как вы одобрите его файл). Другие написания того же файла (регистр, `..`,
симлинк) тоже отклоняются.

Известные ограничения:

- С провайдером `claude-cli` или `gemini-cli` делегируемый CLI выполняет свои
  инструменты по своей модели разрешений, а не по лестнице доверия Veles (`gemini-cli`
  запускается с `--yolo`). Используйте эти провайдеры только в проектах, которые вы
  готовы отдать этому CLI на правку без присмотра.
- Одобрение MCP-сервера фиксирует его командную строку, но не файлы, которые он
  запускает из проекта (скрипт в `args`) — проверяйте и их.

Пути с управляющими символами (escape-последовательности терминала, bidi-override)
отклоняются, а подтверждения, запрос доверия и превью диффа показывают такие символы
экранированными — вызов инструмента не может подделать текст, который вы одобряете.

MCP-серверы из конфига запускаются только после вашего одобрения — см.
[внешние MCP-серверы](external-mcp-servers.md#одобрение-просмотр-и-проверка).
