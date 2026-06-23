# Cómo respaldar y compartir un proyecto

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/backup-and-share.md)

Los proyectos de Veles son portátiles. Exporta un proyecto a un único paquete
`.tar.gz` para respaldarlo o migrarlo, o a una plantilla saneada para compartirla
sin filtrar tus datos.

## Respaldo completo

Empaqueta el proyecto entero (`.veles/` + `AGENTS.md`), salvo los datos efímeros de
ejecución (locks, estado del presupuesto):

```bash
veles export full ./my-project-backup.tar.gz
```

Restáuralo donde sea:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

Un paquete completo incluye tu `memory.db` (sesiones, insights), así que trátalo
como datos privados.

## Plantilla para compartir

Empaqueta solo el andamiaje reutilizable — esquema, skills, módulos y páginas wiki
que no sean de sesión. **Elimina** `memory.db`, `sources/`, `sessions/`, las
concesiones de confianza, y redacta la información personal del texto:

```bash
veles export template ./my-template.tar.gz
```

Entrégale la plantilla a un colega; este la hace `veles import` y obtiene tu
estructura y tus skills sin tu historial de conversaciones ni tus fuentes en bruto.

## Cuál usar

| Objetivo | Comando |
|---|---|
| Respaldar / mover un proyecto intacto | `veles export full` |
| Compartir estructura + skills, no datos | `veles export template` |
