# Как работать с несколькими проектами и подпроектами

> 🌐 **Языки:** [English](../../en/how-to/multi-project-and-subprojects.md) · **Русский**

Veles запускает множество проектов в одном цикле агента. У каждого проекта своя
память, навыки и инструменты. **Подпроекты** — это вложенные проекты под
родительским; они полезны, чтобы разложить большой монорепозиторий или базу
знаний на изолированные по областям памяти.

## Проекты

Veles определяет активный проект, поднимаясь вверх от вашего cwd до каталога
`.veles/` (как `git`). Управление реестром:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` выводит путь, так что вы можете `cd` в проект:

```bash
cd "$(veles project switch web)"
```

Запустить команду для проекта в другом месте без `cd`:

```bash
veles run --project-root /path/to/project "..."
```

## Подпроекты

Подпроект — это дочерний проект Veles внутри родительского. Создать его:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Пусть Veles предложит разбиение

Когда вики проекта разрастается, Veles может обнаружить тематические кластеры и
предложить их в качестве подпроектов:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## Что когда использовать

- **Отдельные проекты** — несвязанные базы знаний / кодовые базы.
- **Подпроекты** — части одного большего целого, которым выгодна изолированная по
  областям память, но которые разделяют родительский контекст.

См. [архитектуру](../explanation/architecture.md), чтобы понять, как контекст
нескольких проектов загружается по требованию, а не одним монолитным дампом.
