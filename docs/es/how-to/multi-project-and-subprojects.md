# Cómo trabajar con varios proyectos y subproyectos

> 🌐 **Idiomas:** [English](../../en/how-to/multi-project-and-subprojects.md) · [简体中文](../../zh-CN/how-to/multi-project-and-subprojects.md) · [繁體中文](../../zh-TW/how-to/multi-project-and-subprojects.md) · [日本語](../../ja/how-to/multi-project-and-subprojects.md) · [한국어](../../ko/how-to/multi-project-and-subprojects.md) · **Español** · [Français](../../fr/how-to/multi-project-and-subprojects.md) · [Italiano](../../it/how-to/multi-project-and-subprojects.md) · [Português (BR)](../../pt-BR/how-to/multi-project-and-subprojects.md) · [Português (PT)](../../pt-PT/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · [العربية](../../ar/how-to/multi-project-and-subprojects.md) · [हिन्दी](../../hi/how-to/multi-project-and-subprojects.md) · [বাংলা](../../bn/how-to/multi-project-and-subprojects.md) · [Tiếng Việt](../../vi/how-to/multi-project-and-subprojects.md)

Veles ejecuta muchos proyectos en un solo bucle de agente. Cada proyecto tiene su
propia memoria, skills y herramientas. Los **subproyectos** son proyectos anidados
bajo un padre — útiles para descomponer un monorepo o una base de conocimiento
grande en memorias acotadas.

## Proyectos

Veles descubre el proyecto activo subiendo desde tu cwd hasta un directorio
`.veles/` (como `git`). Gestiona el registro:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` imprime una ruta, así que puedes hacer `cd` a un proyecto:

```bash
cd "$(veles project switch web)"
```

Ejecuta un comando contra un proyecto que esté en otro lugar sin hacer `cd`:

```bash
veles run --project-root /path/to/project "..."
```

## Subproyectos

Un subproyecto es un proyecto Veles hijo dentro de un padre. Crea uno:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Dejar que Veles sugiera una división

Cuando la wiki de un proyecto crece, Veles puede detectar clústeres temáticos y
proponerlos como subproyectos:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## Cuándo usar cada uno

- **Proyectos separados** — bases de conocimiento / bases de código no
  relacionadas.
- **Subproyectos** — partes de algo más grande que se benefician de una memoria
  acotada pero comparten un contexto padre.

Ver la [arquitectura](../explanation/architecture.md) para entender cómo el contexto
multiproyecto se carga bajo demanda en lugar de como un único volcado monolítico.
