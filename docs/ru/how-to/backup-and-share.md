# Как сделать резервную копию и поделиться проектом

> 🌐 **Языки:** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · [Italiano](../../it/how-to/backup-and-share.md) · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · **Русский** · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · [বাংলা](../../bn/how-to/backup-and-share.md) · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

Проекты Veles портативны. Экспортируйте проект в единый архив `.tar.gz` для
резервной копии или миграции, либо в очищенный шаблон, чтобы поделиться им без
утечки ваших данных.

## Полная резервная копия

Упаковывает весь проект (`.veles/` + `AGENTS.md`), за вычетом эфемерных
рантайм-данных (блокировки, состояние бюджета):

```bash
veles export full ./my-project-backup.tar.gz
```

Восстановить где угодно:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

Полный архив включает ваш `memory.db` (сессии, инсайты), поэтому относитесь к нему
как к приватным данным.

## Шаблон для обмена

Упаковывает только переиспользуемый каркас — схему, навыки, модули и
несессионные страницы вики. Он **вырезает** `memory.db`, `sources/`, `sessions/`,
разрешения доверия и редактирует PII в тексте:

```bash
veles export template ./my-template.tar.gz
```

Передайте шаблон коллеге; он выполнит `veles import` и получит вашу структуру и
навыки без вашей истории переписки и исходных материалов.

## Что использовать

| Цель | Команда |
|---|---|
| Сделать копию / перенести проект целиком | `veles export full` |
| Поделиться структурой + навыками, без данных | `veles export template` |
