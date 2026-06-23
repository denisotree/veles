# Cómo gestionar skills, herramientas y módulos

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/manage-skills-and-tools.md)

Veles acumula capacidad con el tiempo. Las **skills** son flujos de trabajo
reutilizables, las **herramientas** son acciones ejecutables y los **módulos** son
plug-ins opcionales. Cada uno vive en dos ámbitos: local del proyecto
(`<project>/.veles/`) y global del usuario (`~/.veles/`). Para los conceptos, ver
[skills y herramientas](../explanation/skills-and-tools.md).

## Skills

Una skill es un `SKILL.md` (frontmatter + cuerpo del prompt) que el agente puede
invocar como una herramienta.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Promover / degradar entre ámbitos

Una skill que demuestra ser útil en un proyecto puede pasar al ámbito de usuario
para que todos los proyectos la vean (o al revés):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Encontrar duplicados y candidatos a promoción

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Herramientas

Las herramientas se catalogan en el `memory.db` del proyecto con telemetría de uso.
Veles puede escribir sus propias herramientas mientras trabaja; tú las gestionas
con:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Las herramientas sensibles (`run_shell`, `write_file`, `fetch_url`, …) están
controladas por la [escala de confianza](security-and-permissions.md).

## Módulos

Los módulos añaden capacidades opcionales (embeddings, visión, STT) sin inflar el
núcleo. Instalar uno requiere confirmación por defecto.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## Descubrir más

Explora los registros curados:

```bash
veles browse skills [query]
veles browse modules [query]
```
