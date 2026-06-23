# Construir una base de conocimiento

> 🌐 **Idiomas:** [English](../../en/tutorials/building-a-knowledge-base.md) · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · [日本語](../../ja/tutorials/building-a-knowledge-base.md) · [한국어](../../ko/tutorials/building-a-knowledge-base.md) · **Español** · [Français](../../fr/tutorials/building-a-knowledge-base.md) · [Italiano](../../it/tutorials/building-a-knowledge-base.md) · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · [Português (PT)](../../pt-PT/tutorials/building-a-knowledge-base.md) · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · [العربية](../../ar/tutorials/building-a-knowledge-base.md) · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · [বাংলা](../../bn/tutorials/building-a-knowledge-base.md) · [Tiếng Việt](../../vi/tutorials/building-a-knowledge-base.md)

En este tutorial conviertes un proyecto de Veles en una base de conocimiento viva:
ingieres unas cuantas fuentes, dejas que Veles escriba páginas de wiki, haces
preguntas y consolidas lo que aprendiste. Este es el flujo **LLM-Wiki** por
defecto. Unos 15 minutos.

Antes deberías haber terminado [Getting started](getting-started.md).

## La idea

Un proyecto de Veles tiene dos zonas de contenido:

- `sources/` — material en bruto e inmutable que le proporcionas (solo lectura
  para el agente).
- `wiki/` — el conocimiento propio del agente, generado por el LLM (la única zona
  en la que escribe contenido).

Le aportas fuentes; Veles las destila en páginas de wiki enlazadas; tú consultas la
wiki en lenguaje natural. Consulta [layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)
para el porqué.

## 1. Ingerir una fuente

`veles add` lee un archivo o una URL y escribe una página de wiki que la resume:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

Cada `add` produce una página bajo `wiki/` y la enlaza en el grafo de la wiki.

## 2. Ver crecer la wiki

Mira lo que se escribió:

```bash
ls wiki/concepts wiki/entities wiki/sources
```

Las páginas se referencian entre sí. El catálogo bajo demanda `wiki/INDEX.md`
mantiene un mapa que el agente carga cuando lo necesita (no un volcado monolítico
de contexto).

## 3. Hacer preguntas

Ahora consulta tu base de conocimiento en lenguaje natural:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles busca en la wiki, lee las páginas relevantes y responde — fundamentado en lo
que ingeriste y no solo en sus datos de entrenamiento.

Para una conversación interactiva de ida y vuelta, haz lo mismo en la TUI
(`veles tui`).

## 4. Consolidar sesiones

A medida que trabajas, las conversaciones se acumulan. Ejecuta el curador para
compactarlas en páginas de wiki duraderas y extraer lecciones:

```bash
veles curate
```

Esto escribe páginas en `wiki/sessions/` y actualiza los insights y las reglas del
proyecto. Veles también lo hace automáticamente con el tiempo — consulta
[project memory & the learning loop](../explanation/project-memory-and-learning-loop.md).

## 5. Mantener la wiki sana

Con el tiempo las páginas quedan obsoletas o huérfanas. La operación `lint` las
encuentra:

```bash
veles run "lint"
```

(`ingest`, `query` y `lint` son skills incluidos con el layout LLM-Wiki; los
invocas con `veles run "<operation>"` o dejas que el agente los llame.)

## Lo que construiste

Una base de conocimiento autoorganizada: entran fuentes, salen páginas de wiki
enlazadas, consultable en lenguaje natural, que se ordena mejor a medida que Veles
consolida. Desde aquí:

- **[Manage skills, tools, and modules](../how-to/manage-skills-and-tools.md)** —
  enseña a Veles flujos de trabajo reutilizables.
- **[Run as a daemon](../how-to/run-as-daemon.md)** + **[connect Telegram](../how-to/connect-telegram.md)** —
  habla con tu base de conocimiento desde el móvil.
- **[Multiple projects & subprojects](../how-to/multi-project-and-subprojects.md)** —
  escala a muchas bases de conocimiento.
