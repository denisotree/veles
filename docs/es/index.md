# Documentación de Veles

> 🌐 **Idiomas:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · **Español** · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles es un framework de agentes de CLI minimalista y local-first. Lo apuntas a un
directorio de proyecto; mantiene una **memoria del proyecto** estructurada,
**aprende** de tus sesiones, ejecuta cualquier proveedor de LLM (en la nube o
local) y acumula **skills** y **herramientas** reutilizables a medida que trabaja.

Esta documentación sigue el modelo [Diátaxis](https://diataxis.fr/). Elige el
cuadrante que se ajuste a lo que necesitas ahora mismo.

## Empieza aquí

Si nunca has ejecutado Veles, haz los dos tutoriales en orden:

1. **[Primeros pasos](tutorials/getting-started.md)** — instala Veles, configura
   una clave API, crea tu primer proyecto y ejecuta tu primer prompt.
2. **[Construir una base de conocimiento](tutorials/building-a-knowledge-base.md)** — ingiere
   fuentes en la LLM-Wiki, haz preguntas y consolida sesiones.

## Tutoriales — aprende haciendo

- [Primeros pasos](tutorials/getting-started.md)
- [Construir una base de conocimiento](tutorials/building-a-knowledge-base.md)

## Guías prácticas — completa una tarea

- [Configurar proveedores (nube y local)](how-to/configure-providers.md)
- [Enrutar distintas tareas a distintos modelos](how-to/per-task-routing.md)
- [Ejecutar Veles como daemon](how-to/run-as-daemon.md)
- [Conectar un canal de Telegram](how-to/connect-telegram.md)
- [Gestionar skills, herramientas y módulos](how-to/manage-skills-and-tools.md)
- [Trabajar con múltiples proyectos y subproyectos](how-to/multi-project-and-subprojects.md)
- [Seguridad: confianza, autopilot, secretos](how-to/security-and-permissions.md)
- [Tareas de larga duración: goals, jobs, dreaming, research](how-to/long-running-tasks.md)
- [Conectar servidores MCP externos](how-to/external-mcp-servers.md)
- [Respaldar y compartir un proyecto](how-to/backup-and-share.md)

## Referencia — búscalo

- [Referencia de comandos de la CLI](reference/cli.md)
- [Configuración (`config.toml`)](reference/configuration.md)
- [Variables de entorno](reference/environment-variables.md)
- [Proveedores](reference/providers.md)
- [Atajos de teclado y comandos de barra de la TUI](reference/tui.md)
- [Layout y estado del proyecto](reference/project-layout.md)

## Explicación — comprende el diseño

- [Visión general de la arquitectura](explanation/architecture.md)
- [Memoria del proyecto y el bucle de aprendizaje](explanation/project-memory-and-learning-loop.md)
- [Skills y herramientas como capacidad acumulativa](explanation/skills-and-tools.md)
- [Modos de ejecución](explanation/modes.md)
- [Orquestación multiagente](explanation/multi-agent-orchestration.md)
- [Layout packs y la LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Confianza y el sandbox](explanation/trust-and-sandbox.md)

---

Para la visión del producto y la justificación del diseño consulta `VISION.md` (en
la raíz del repositorio); para el historial completo de implementación consulta
`MILESTONES.md`. Esos están orientados a desarrolladores — esta documentación es
para **usar** Veles.
