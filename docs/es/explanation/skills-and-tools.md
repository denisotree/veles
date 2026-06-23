# Skills y herramientas como capacidad acumulativa

> 🌐 **Idiomas:** [English](../../en/explanation/skills-and-tools.md) · [简体中文](../../zh-CN/explanation/skills-and-tools.md) · [繁體中文](../../zh-TW/explanation/skills-and-tools.md) · [日本語](../../ja/explanation/skills-and-tools.md) · [한국어](../../ko/explanation/skills-and-tools.md) · **Español** · [Français](../../fr/explanation/skills-and-tools.md) · [Italiano](../../it/explanation/skills-and-tools.md) · [Português (BR)](../../pt-BR/explanation/skills-and-tools.md) · [Português (PT)](../../pt-PT/explanation/skills-and-tools.md) · [Русский](../../ru/explanation/skills-and-tools.md) · [العربية](../../ar/explanation/skills-and-tools.md) · [हिन्दी](../../hi/explanation/skills-and-tools.md) · [বাংলা](../../bn/explanation/skills-and-tools.md) · [Tiếng Việt](../../vi/explanation/skills-and-tools.md)

Veles empieza con un conjunto mínimo de herramientas y skills y lo **hace crecer** a
medida que trabaja. Esta página explica la diferencia entre ambos y cómo se acumulan.
Para los comandos, consulta [gestionar skills y herramientas](../how-to/manage-skills-and-tools.md).

## Herramientas frente a skills

- Una **herramienta** es una única acción ejecutable: leer un archivo, ejecutar un
  comando de shell, obtener una URL, buscar en la web, escribir una página de wiki.
  Las herramientas son lo que el modelo invoca.
- Un **skill** es un *proceso* formalizado: un `SKILL.md` con un cuerpo de prompt y
  una lista de herramientas permitidas que se ejecuta como un sub-agente enfocado.
  Los skills componen herramientas en un flujo de trabajo repetible (p. ej. los
  `ingest`/`query`/`lint` de la LLM-Wiki).

## Arranque mínimo, expansión bajo demanda

Veles arranca con lo justo para ser útil, más un lugar conocido del que extraer más.
Instalar extras (un skill, una herramienta, un módulo) pide aprobación por defecto;
puedes conceder autonomía permanente. Esto mantiene ligero un proyecto nuevo a la
vez que permite que la capacidad crezca donde se necesita.

## Cómo se acumula la capacidad

1. **Veles escribe sus propias herramientas.** Cuando detecta una tarea repetitiva,
   puede crear una herramienta en Python limpia, tipada y reutilizable en
   `<project>/.veles/tools/` (con una pasada de revisión de código por el advisor).
   La herramienta se incorpora al registro con telemetría.
2. **Los procesos repetitivos se convierten en skills.** Un detector de patrones
   detecta secuencias de herramientas recurrentes y propone formalizarlas como un
   skill; los skills pueden `extends:` otro skill para heredar su cuerpo y
   herramientas.
3. **La telemetría guía el ranking.** Cada herramienta/skill lleva recuentos de
   uso/éxito/error. Estos alimentan la deduplicación (`veles skill dedup`) y las
   sugerencias de promoción.

## Dos ámbitos, con promoción

Tanto las herramientas como los skills existen en dos niveles:

- **Local del proyecto** (`<project>/.veles/`) — visible solo aquí.
- **Global del usuario** (`~/.veles/`) — disponible en todos los proyectos.

Una capacidad que demuestra su valía en un proyecto puede ser **promovida** al
ámbito de usuario para que todos los proyectos se beneficien (`veles skill promote`,
`veles tool promote`), o **degradada** de vuelta. Así es como Veles traslada entre
proyectos los flujos de trabajo ganados con esfuerzo.

## Por qué un registro y no solo archivos

Almacenar los skills/herramientas como archivos planos los mantiene inspeccionables
y editables; almacenar su *telemetría* en `memory.db` permite a Veles razonar sobre
cuáles funcionan de verdad. La combinación es lo que convierte "una carpeta de
scripts" en una capacidad acumulativa y autocurada.
