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

1. **[Getting started](tutorials/getting-started.md)** — instala Veles, configura
   una clave API, crea tu primer proyecto y ejecuta tu primer prompt.
2. **[Building a knowledge base](tutorials/building-a-knowledge-base.md)** — ingiere
   fuentes en la LLM-Wiki, haz preguntas y consolida sesiones.

## Tutoriales — aprende haciendo

- [Getting started](tutorials/getting-started.md)
- [Building a knowledge base](tutorials/building-a-knowledge-base.md)

## Guías prácticas — completa una tarea

- [Configure providers (cloud & local)](how-to/configure-providers.md)
- [Route different tasks to different models](how-to/per-task-routing.md)
- [Run Veles as a daemon](how-to/run-as-daemon.md)
- [Connect a Telegram channel](how-to/connect-telegram.md)
- [Manage skills, tools, and modules](how-to/manage-skills-and-tools.md)
- [Work with multiple projects and subprojects](how-to/multi-project-and-subprojects.md)
- [Security: trust, autopilot, secrets](how-to/security-and-permissions.md)
- [Long-running tasks: goals, jobs, dreaming, research](how-to/long-running-tasks.md)
- [Connect external MCP servers](how-to/external-mcp-servers.md)
- [Back up and share a project](how-to/backup-and-share.md)

## Referencia — búscalo

- [CLI command reference](reference/cli.md)
- [Configuration (`config.toml`)](reference/configuration.md)
- [Environment variables](reference/environment-variables.md)
- [Providers](reference/providers.md)
- [TUI keybindings & slash commands](reference/tui.md)
- [Project layout & state](reference/project-layout.md)

## Explicación — comprende el diseño

- [Architecture overview](explanation/architecture.md)
- [Project memory & the learning loop](explanation/project-memory-and-learning-loop.md)
- [Skills & tools as accumulating capability](explanation/skills-and-tools.md)
- [Run modes](explanation/modes.md)
- [Multi-agent orchestration](explanation/multi-agent-orchestration.md)
- [Layout packs & the LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Trust & the sandbox](explanation/trust-and-sandbox.md)

---

Para la visión del producto y la justificación del diseño consulta `VISION.md` (en
la raíz del repositorio); para el historial completo de implementación consulta
`MILESTONES.md`. Esos están orientados a desarrolladores — esta documentación es
para **usar** Veles.
