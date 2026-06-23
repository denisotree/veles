# Visión general de la arquitectura

> 🌐 **Idiomas:** [English](../../en/explanation/architecture.md) · [简体中文](../../zh-CN/explanation/architecture.md) · [繁體中文](../../zh-TW/explanation/architecture.md) · [日本語](../../ja/explanation/architecture.md) · [한국어](../../ko/explanation/architecture.md) · **Español** · [Français](../../fr/explanation/architecture.md) · [Italiano](../../it/explanation/architecture.md) · [Português (BR)](../../pt-BR/explanation/architecture.md) · [Português (PT)](../../pt-PT/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md) · [العربية](../../ar/explanation/architecture.md) · [हिन्दी](../../hi/explanation/architecture.md) · [বাংলা](../../bn/explanation/architecture.md) · [Tiếng Việt](../../vi/explanation/architecture.md)

Esta página explica qué *es* Veles y cómo encajan sus partes, para que el resto de
la documentación tenga sentido. Para conocer la visión de producto autorizada,
consulta `VISION.md` en la raíz del repositorio.

## La intención de diseño

Veles es deliberadamente **minimalista y limpiamente descompuesto**: módulos con
responsabilidad única, sin archivos monolíticos. Es **local-first**: lo ejecutas
sobre un directorio de tu máquina y mantiene allí su propia memoria estructurada.

## Los cinco pilares (el núcleo)

Todo lo que hay en el núcleo cumple uno de estos cinco cometidos:

1. **Memoria del proyecto** — un artefacto estructurado (separado de tu contenido)
   que guarda el registro de sesiones, las reglas/insights aprendidos, un mapa de
   archivos del proyecto y los registros de skills/herramientas con telemetría.
   Consulta [memoria del proyecto y el bucle de aprendizaje](project-memory-and-learning-loop.md).
2. **El bucle de aprendizaje** — el curator, el extractor de insights y el "soñar"
   (dreaming) que mantienen la memoria fresca y convierten la experiencia en reglas
   reutilizables.
3. **Orquestación multi-agente** — un manager que descompone una tarea y genera
   workers especializados. Consulta [orquestación multi-agente](multi-agent-orchestration.md).
4. **Un protocolo de proveedores** — una sola interfaz sobre muchos backends de LLM
   (nube, local, delegación a CLI). Consulta [proveedores](../reference/providers.md).
5. **Herramientas y skills mínimos** — un pequeño conjunto inicial que **se acumula**
   a medida que Veles escribe sus propias herramientas y formaliza procesos
   repetitivos en skills. Consulta [skills y herramientas](skills-and-tools.md).

## Todo lo demás es un módulo opcional

Las pasarelas/canales, el daemon, el planificador, la TUI, la visión/STT: todos
son **enchufables** y se cargan solo cuando se usan. Veles arranca con lo mínimo y
se expande bajo demanda, de modo que un simple `veles run` se mantiene simple.

## Cómo fluye un turno

```
your prompt
   │
   ▼
context: AGENTS.md (small) + on-demand recall from project memory
   │
   ▼
agent loop  ──►  provider (routed per task)  ──►  tool calls
   │                                               │
   │            (trust ladder gates sensitive tools)
   ▼
response  ──►  saved to memory  ──►  learning triggers (insights, curator)
```

El archivo de contexto (`AGENTS.md`) se mantiene pequeño a propósito; el
conocimiento auxiliar (páginas de la wiki, el mapa de archivos del proyecto, turnos
pasados relevantes) se incorpora **bajo demanda** en lugar de volcarse todo de
entrada.

## Dónde vive el estado

- `<project>/.veles/` — la memoria, la configuración y los skills/herramientas
  locales de este proyecto.
- `~/.veles/` — configuración global del usuario, skills/herramientas entre
  proyectos, cachés y confianza.
- `<project>/AGENTS.md`, `wiki/`, `sources/` — tu contenido (el layout LLM-Wiki).

Consulta [estructura del proyecto](../reference/project-layout.md).

## Multi-proyecto en un solo bucle

Un único bucle de agente sirve a muchos proyectos. Cada proyecto recibe su propio
directorio con su propio contexto y memoria; `AGENTS.md` se enlaza simbólicamente a
`CLAUDE.md`/`GEMINI.md` para que una CLI externa lanzada allí vea el mismo
contexto. Consulta [múltiples proyectos](../how-to/multi-project-and-subprojects.md).

## Las superficies

- **CLI** (`veles run`, `veles add`, …) — uso puntual y mediante scripts.
- **TUI** (`veles tui`) — REPL interactivo con [modos de ejecución](modes.md).
- **Daemon + canales** — API sin interfaz, Telegram, trabajos programados.

Las tres manejan el mismo bucle de agente central.
