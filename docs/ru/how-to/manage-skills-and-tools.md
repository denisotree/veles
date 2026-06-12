# Как управлять навыками, инструментами и модулями

> 🌐 **Языки:** [English](../../en/how-to/manage-skills-and-tools.md) · **Русский**

Veles накапливает возможности со временем. **Навыки** (skills) — это переиспользуемые
рабочие процессы, **инструменты** (tools) — исполняемые действия, **модули** (modules) —
опциональные плагины. Каждый существует в двух областях: проектной
(`<project>/.veles/`) и пользовательской глобальной (`~/.veles/`). О концепциях см.
[навыки и инструменты](../explanation/skills-and-tools.md).

## Навыки

Навык — это `SKILL.md` (frontmatter + тело промпта), который агент может вызывать
как инструмент.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Повышение / понижение между областями

Навык, доказавший пользу в одном проекте, можно перенести в пользовательскую область,
чтобы его видел каждый проект (или наоборот):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Поиск дубликатов и кандидатов на повышение

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Инструменты

Инструменты каталогизированы в `memory.db` проекта вместе с телеметрией
использования. Veles может писать собственные инструменты в процессе работы; вы
управляете ими через:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Чувствительные инструменты (`run_shell`, `write_file`, `fetch_url`, …)
регулируются [лестницей доверия](security-and-permissions.md).

## Модули

Модули добавляют опциональные возможности (embeddings, vision, STT), не раздувая
ядро. Установка по умолчанию требует подтверждения.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## Поиск новых

Просматривайте курируемые реестры:

```bash
veles browse skills [query]
veles browse modules [query]
```
